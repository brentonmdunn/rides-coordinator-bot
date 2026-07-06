"""
Service layer for editable ask-rides message templates.

Owns the unit of work (opens its own sessions) and the fallback logic: DB
customizations are merged over `DEFAULT_TEMPLATES`, and any DB failure falls
back to the hardcoded defaults so the scheduled job never fails to send.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy.exc import OperationalError

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AskRidesMessageType, EmbedColorChoice
from bot.core.messages_broadcaster import publish
from bot.repositories.ask_rides_messages_repository import AskRidesMessagesRepository
from bot.utils.ask_rides_defaults import ALLOWED_PLACEHOLDERS, DEFAULT_TEMPLATES, MessageTemplate

logger = logging.getLogger(__name__)

TITLE_MAX_LEN = 256
BODY_MAX_LEN = 4096

_PLACEHOLDER_RE = re.compile(r"{(\w*)}")


@dataclass(frozen=True)
class EffectiveTemplate:
    """A title/body/color template plus whether it's a saved customization."""

    title: str
    body: str
    color: str
    is_customized: bool


class _SafeFormatDict(dict):
    """
    A dict for str.format_map that never raises KeyError.

    Unknown keys render back as the literal `{key}` token so a stray
    placeholder can't crash the scheduled job.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _to_effective(template: MessageTemplate, *, is_customized: bool) -> EffectiveTemplate:
    return EffectiveTemplate(
        title=template.title,
        body=template.body,
        color=str(template.color),
        is_customized=is_customized,
    )


class AskRidesMessagesService:
    """Handles reads/writes/rendering of editable ask-rides message templates."""

    @staticmethod
    async def get_effective_templates() -> dict[AskRidesMessageType, EffectiveTemplate]:
        """Return the effective (DB-customized or default) template for every message type."""
        defaults = {
            message_type: _to_effective(template, is_customized=False)
            for message_type, template in DEFAULT_TEMPLATES.items()
        }

        try:
            async with AsyncSessionLocal() as session:
                rows = await AskRidesMessagesRepository.get_all(session)
        except Exception:
            logger.exception("Failed to load ask-rides message templates; using defaults")
            return defaults

        effective = dict(defaults)
        for row in rows:
            try:
                message_type = AskRidesMessageType(row.message_type)
            except ValueError:
                logger.warning("Unknown ask-rides message_type in DB: %s", row.message_type)
                continue
            effective[message_type] = EffectiveTemplate(
                title=row.title,
                body=row.body,
                color=row.color,
                is_customized=True,
            )
        return effective

    @staticmethod
    async def get_effective_template(message_type: AskRidesMessageType) -> EffectiveTemplate:
        """
        Return the effective template for one message type.

        Never raises — any DB failure (including a missing table) falls back
        to the hardcoded default and logs the exception. The scheduled job
        depends on this never failing.
        """
        default = _to_effective(DEFAULT_TEMPLATES[message_type], is_customized=False)
        try:
            async with AsyncSessionLocal() as session:
                row = await AskRidesMessagesRepository.get(session, message_type)
        except OperationalError:
            logger.exception(
                "DB error (likely missing table) fetching ask-rides template for %s; "
                "falling back to default",
                message_type,
            )
            return default
        except Exception:
            logger.exception(
                "Unexpected error fetching ask-rides template for %s; falling back to default",
                message_type,
            )
            return default

        if row is None:
            return default

        return EffectiveTemplate(
            title=row.title,
            body=row.body,
            color=row.color,
            is_customized=True,
        )

    @staticmethod
    def _validate(message_type: AskRidesMessageType, title: str, body: str, color: str) -> None:
        """Validate a template before saving. Raises ValueError on any violation."""
        if not title or not title.strip():
            raise ValueError("Title must not be empty")
        if len(title) > TITLE_MAX_LEN:
            raise ValueError(f"Title must be at most {TITLE_MAX_LEN} characters")

        if not body or not body.strip():
            raise ValueError("Body must not be empty")
        if len(body) > BODY_MAX_LEN:
            raise ValueError(f"Body must be at most {BODY_MAX_LEN} characters")

        try:
            EmbedColorChoice(color)
        except ValueError as exc:
            raise ValueError(f"Invalid color: {color!r}") from exc

        allowed = ALLOWED_PLACEHOLDERS[message_type]
        found_tokens = set(_PLACEHOLDER_RE.findall(title)) | set(_PLACEHOLDER_RE.findall(body))
        unknown_tokens = found_tokens - allowed
        if unknown_tokens:
            raise ValueError(
                f"Unsupported placeholder(s) {sorted(unknown_tokens)} for {message_type.value}; "
                f"allowed: {sorted(allowed)}"
            )

    @staticmethod
    async def update_template(
        message_type: AskRidesMessageType,
        title: str,
        body: str,
        color: str,
        updated_by: str,
    ) -> EffectiveTemplate:
        """
        Validate and save a customized template, then broadcast an SSE update.

        Raises ValueError on validation failure (caller should turn this
        into a 422).
        """
        AskRidesMessagesService._validate(message_type, title, body, color)

        async with AsyncSessionLocal() as session:
            row = await AskRidesMessagesRepository.upsert(
                session, message_type, title, body, color, updated_by
            )

        await publish({"type": "templates_updated", "message_type": message_type.value})

        return EffectiveTemplate(
            title=row.title,
            body=row.body,
            color=row.color,
            is_customized=True,
        )

    @staticmethod
    async def reset_template(message_type: AskRidesMessageType) -> None:
        """Delete the saved customization for a message type and broadcast an SSE update."""
        async with AsyncSessionLocal() as session:
            await AskRidesMessagesRepository.delete(session, message_type)

        await publish({"type": "templates_updated", "message_type": message_type.value})

    @staticmethod
    def render(
        template: EffectiveTemplate | MessageTemplate,
        message_type: AskRidesMessageType,
        *,
        date_str: str,
        ping_text: str = "",
    ) -> tuple[str, str]:
        """
        Fill `{date}` (and `{ping}` for Sunday service) into title/body.

        Uses `format_map` with a defaulting dict so an unknown/stray
        placeholder never raises.
        """
        values = _SafeFormatDict(date=date_str)
        if message_type == AskRidesMessageType.SUNDAY_SERVICE:
            values["ping"] = ping_text

        title = template.title.format_map(values)
        body = template.body.format_map(values)
        return title, body
