"""
Service layer for the scheduled pickup-list summaries posted to ride coordinators.

Owns the unit of work (opens its own sessions) and the fallback logic: DB
customizations are merged over `DEFAULT_SUMMARY_SCHEDULE`, and any DB failure
falls back to the hardcoded defaults so a scheduled job is never left
unscheduled.
"""

import logging
import os
from dataclasses import dataclass

import discord
from discord.ext import commands
from sqlalchemy.exc import OperationalError

from ridebot.core.scheduler_control import reschedule_job
from ridebot.repositories.message_schedule_repository import MessageScheduleRepository
from ridebot.repositories.pickup_summary_settings_repository import (
    PickupSummarySettingsRepository,
)
from ridebot.services.ask_rides_schedule_service import AskRidesScheduleService
from ridebot.services.fellowship_season_service import FellowshipSeasonService
from ridebot.services.locations_service import LocationsService
from ridebot.utils.cache import invalidate_namespace
from ridebot.utils.custom_exceptions import NoMatchingMessageFoundError
from ridebot.utils.pickup_summary_defaults import (
    DEFAULT_SUMMARY_SCHEDULE,
    SUMMARY_ALLOWED_DAYS,
    SUMMARY_MAX_HOUR,
    SUMMARY_MAX_MINUTE,
    SUMMARY_MIN_HOUR,
    SUMMARY_MIN_MINUTE,
    SUMMARY_SLOT_TO_JOB_ID,
    SUMMARY_SLOT_TO_JOB_NAME,
    SUMMARY_SLOT_TO_RIDE_OPTION,
    ScheduleDefault,
)
from shared.core.database import AsyncSessionLocal
from shared.core.enums import CacheNamespace, ChannelIds, FellowshipSeason, PickupSummarySlot
from shared.core.error_reporter import send_error_to_discord
from shared.utils.constants import FRONTEND_BASE_URL_LOCAL

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectivePickupSummarySetting:
    """A pickup-summary schedule/toggle for one slot plus whether it's a saved customization."""

    enabled: bool
    day_of_week: int
    hour: int
    minute: int
    is_customized: bool


def _to_effective(
    default: ScheduleDefault, *, enabled: bool, is_customized: bool
) -> EffectivePickupSummarySetting:
    return EffectivePickupSummarySetting(
        enabled=enabled,
        day_of_week=default.day_of_week,
        hour=default.hour,
        minute=default.minute,
        is_customized=is_customized,
    )


class PickupSummaryService:
    """Handles reads/writes/live-rescheduling and sending of pickup-list summaries."""

    def __init__(self, bot: commands.Bot | None = None):
        """Initialize the service. `bot` is only needed to call `send_summary`."""
        self.bot = bot

    @staticmethod
    async def get_effective_setting(slot: PickupSummarySlot) -> EffectivePickupSummarySetting:
        """
        Return the effective setting for one slot.

        Never raises — any DB failure (including a missing table) falls back
        to the hardcoded default (enabled) and logs the exception. Job
        startup wiring depends on this never failing.
        """
        default = _to_effective(DEFAULT_SUMMARY_SCHEDULE[slot], enabled=True, is_customized=False)
        try:
            async with AsyncSessionLocal() as session:
                row = await PickupSummarySettingsRepository.get(session, slot)
        except OperationalError:
            logger.exception(
                "DB error (likely missing table) fetching pickup summary setting for %s; "
                "falling back to default",
                slot,
            )
            return default
        except Exception:
            logger.exception(
                "Unexpected error fetching pickup summary setting for %s; falling back to default",
                slot,
            )
            return default

        if row is None:
            return default

        return EffectivePickupSummarySetting(
            enabled=row.enabled,
            day_of_week=row.day_of_week,
            hour=row.hour,
            minute=row.minute,
            is_customized=True,
        )

    @staticmethod
    async def get_effective_settings() -> dict[PickupSummarySlot, EffectivePickupSummarySetting]:
        """Return the effective setting for every slot at once. Never raises."""
        defaults = {
            slot: _to_effective(default, enabled=True, is_customized=False)
            for slot, default in DEFAULT_SUMMARY_SCHEDULE.items()
        }

        try:
            async with AsyncSessionLocal() as session:
                rows = await PickupSummarySettingsRepository.get_all(session)
        except Exception:
            logger.exception("Failed to load pickup summary settings; using defaults")
            return defaults

        effective = dict(defaults)
        for row in rows:
            try:
                slot = PickupSummarySlot(row.slot)
            except ValueError:
                logger.warning("Unknown pickup summary slot in DB: %s", row.slot)
                continue
            effective[slot] = EffectivePickupSummarySetting(
                enabled=row.enabled,
                day_of_week=row.day_of_week,
                hour=row.hour,
                minute=row.minute,
                is_customized=True,
            )
        return effective

    @staticmethod
    def _validate(slot: PickupSummarySlot, day_of_week: int, hour: int, minute: int) -> None:
        """Validate a schedule before saving. Raises ValueError on any violation."""
        if day_of_week not in SUMMARY_ALLOWED_DAYS[slot]:
            allowed_names = sorted(SUMMARY_ALLOWED_DAYS[slot])
            raise ValueError(
                f"day_of_week must be one of {allowed_names} for {slot.value}, got {day_of_week}"
            )

        if not (0 <= hour <= 23):
            raise ValueError(f"hour must be between 0 and 23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"minute must be between 0 and 59, got {minute}")

        time_minutes = hour * 60 + minute
        min_minutes = SUMMARY_MIN_HOUR * 60 + SUMMARY_MIN_MINUTE
        max_minutes = SUMMARY_MAX_HOUR * 60 + SUMMARY_MAX_MINUTE
        if not (min_minutes <= time_minutes <= max_minutes):
            raise ValueError(
                f"time must be between {SUMMARY_MIN_HOUR:02d}:{SUMMARY_MIN_MINUTE:02d} and "
                f"{SUMMARY_MAX_HOUR:02d}:{SUMMARY_MAX_MINUTE:02d}, got {hour:02d}:{minute:02d}"
            )

    @staticmethod
    async def update_setting(
        slot: PickupSummarySlot,
        enabled: bool,
        day_of_week: int,
        hour: int,
        minute: int,
        updated_by: str,
    ) -> tuple[EffectivePickupSummarySetting, bool]:
        """
        Validate and save a customized setting, and apply it live.

        Raises ValueError on validation failure (caller should turn this into a 422).

        Returns:
            A tuple of (effective setting, whether the live reschedule was applied).
        """
        PickupSummaryService._validate(slot, day_of_week, hour, minute)

        async with AsyncSessionLocal() as session:
            row = await PickupSummarySettingsRepository.upsert(
                session, slot, enabled, day_of_week, hour, minute, updated_by
            )

        applied = reschedule_job(
            SUMMARY_SLOT_TO_JOB_ID[slot], day_of_week=day_of_week, hour=hour, minute=minute
        )

        return (
            EffectivePickupSummarySetting(
                enabled=row.enabled,
                day_of_week=row.day_of_week,
                hour=row.hour,
                minute=row.minute,
                is_customized=True,
            ),
            applied,
        )

    @staticmethod
    async def reset_setting(slot: PickupSummarySlot) -> tuple[EffectivePickupSummarySetting, bool]:
        """
        Delete the saved customization for a slot and reschedule to the default.

        Returns:
            A tuple of (effective setting, whether the live reschedule was applied).
        """
        async with AsyncSessionLocal() as session:
            await PickupSummarySettingsRepository.delete(session, slot)

        default = DEFAULT_SUMMARY_SCHEDULE[slot]
        applied = reschedule_job(
            SUMMARY_SLOT_TO_JOB_ID[slot],
            day_of_week=default.day_of_week,
            hour=default.hour,
            minute=default.minute,
        )

        return _to_effective(default, enabled=True, is_customized=False), applied

    @staticmethod
    def build_dashboard_link(slot: PickupSummarySlot) -> str | None:
        """
        Build the admin dashboard deep link for a slot, or None if unavailable.

        Reads `FRONTEND_BASE_URL` at call time so it always reflects the
        current environment/config rather than a value captured at import time.
        """
        base = os.getenv("FRONTEND_BASE_URL", "").strip().rstrip("/")
        if not base:
            if os.getenv("APP_ENV", "local") == "local":
                base = FRONTEND_BASE_URL_LOCAL.rstrip("/")
            else:
                logger.warning(
                    "FRONTEND_BASE_URL is not set; sending pickup summary for %s without a link",
                    slot,
                )
                return None

        return f"{base}/?overview={slot.value}#reactions"

    async def send_summary(
        self,
        slot: PickupSummarySlot,
        channel_id: int = ChannelIds.SERVING__RIDE_COORDINATORS,
        *,
        respect_toggle: bool = True,
    ) -> bool:
        """
        Build and send the pickup-list summary for a slot to the ride coordinators channel.

        Returns:
            True if a message was sent, False if the send was skipped or failed.
            Never raises.
        """
        try:
            if respect_toggle:
                setting = await PickupSummaryService.get_effective_setting(slot)
                if not setting.enabled:
                    logger.info("Skipping pickup summary for %s - toggle is off", slot)
                    return False

            if slot == PickupSummarySlot.FRIDAY:
                season = await FellowshipSeasonService.get_season()
                if season != FellowshipSeason.FRIDAY:
                    logger.info(
                        "Skipping pickup summary for %s - fellowship season is %s", slot, season
                    )
                    return False

            job_name = SUMMARY_SLOT_TO_JOB_NAME[slot]
            send_day_of_week = await AskRidesScheduleService.get_send_day_for_job(job_name)
            async with AsyncSessionLocal() as session:
                paused = await MessageScheduleRepository.is_job_paused(
                    session, job_name, send_day_of_week
                )
            if paused:
                logger.info("Skipping pickup summary for %s - ask-rides job is paused", slot)
                return False

            if self.bot is None:
                logger.warning("Skipping pickup summary for %s - no bot instance available", slot)
                return False

            # The reaction cache is keyed on channel/message, so a stale entry from an
            # earlier lookup this week would otherwise be served here. Invalidate first
            # so the summary always reflects the latest reactions.
            await invalidate_namespace(CacheNamespace.ASK_RIDES_REACTIONS)

            try:
                embeds = await LocationsService(self.bot).build_pickups_embeds(
                    job_name, SUMMARY_SLOT_TO_RIDE_OPTION[slot]
                )
            except NoMatchingMessageFoundError:
                logger.info("Skipping pickup summary for %s - no matching message found", slot)
                return False

            raw_channel = self.bot.get_channel(channel_id)
            if not isinstance(raw_channel, (discord.TextChannel, discord.Thread)):
                logger.warning("Channel not found with ID: %s", channel_id)
                return False

            link = PickupSummaryService.build_dashboard_link(slot)
            content = f"[Open in dashboard](<{link}>)" if link else None
            await raw_channel.send(content=content, embeds=embeds)
            return True
        except Exception:
            logger.exception("Unexpected error sending pickup summary for %s", slot)
            await send_error_to_discord(f"**Unexpected Error** sending pickup summary for {slot}")
            return False
