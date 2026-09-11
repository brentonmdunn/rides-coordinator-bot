"""Service for message schedule pause operations."""

import logging
from datetime import date

from bot.core.database import AsyncSessionLocal
from bot.core.models import MessageSchedulePause
from bot.repositories.message_schedule_repository import MessageScheduleRepository

logger = logging.getLogger(__name__)


class MessageScheduleService:
    """Handles pause scheduling for ask-rides jobs."""

    @staticmethod
    async def get_all_pauses() -> list[MessageSchedulePause]:
        """Return pause status for all jobs."""
        async with AsyncSessionLocal() as session:
            return await MessageScheduleRepository.get_all_pause_statuses(session)

    @staticmethod
    async def set_pause(
        job_name: str,
        is_paused: bool,
        resume_after_date: date | None = None,
    ) -> MessageSchedulePause | None:
        """Set the pause state for a job. Returns the updated row, or None if job not found."""
        async with AsyncSessionLocal() as session:
            return await MessageScheduleRepository.set_pause(
                session, job_name, is_paused, resume_after_date
            )

    @staticmethod
    async def clear_pause(job_name: str) -> None:
        """Clear the pause for a job (resume immediately)."""
        async with AsyncSessionLocal() as session:
            await MessageScheduleRepository.clear_pause(session, job_name)
