"""
Cog for the #general thread-maker agent.

A lightweight agent exposed only in the rides-general channel. Its single capability is
turning a message into a tracked event thread: a user mentions the bot while replying to a
message ("@ridebot make this a thread") or refers to the message above
("@ridebot make the message above a thread"), and the bot creates/registers an event thread
and pulls in everyone who reacted. If the bot can't tell which message is meant, it asks the
user to reply to the target message.
"""

import asyncio
import logging
import re

import discord
from discord.ext import commands

from agent.thread_intent import (
    SOURCE_ABOVE,
    SOURCE_REPLIED,
    classify_thread_intent,
)
from bot.core.database import AsyncSessionLocal
from bot.core.enums import ChannelIds, FeatureFlagNames
from bot.repositories.feature_flags_repository import FeatureFlagsRepository
from bot.services.thread_service import StarterMessageError, ThreadService

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"<@!?\d+>")
_THREAD_NAME_MAX = 100
_HISTORY_LOOKBACK = 10
_ALLOWED_CHANNEL_IDS: frozenset[int] = frozenset(
    {
        int(ChannelIds.REFERENCES__RIDES_GENERAL),
        int(ChannelIds.BOT_STUFF__BOTS),
    }
)
_CLARIFY_FALLBACK = "Reply to the message you want me to turn into a thread, then @ me."


class ThreadAgent(commands.Cog):
    """Conversational thread-maker for the rides-general channel."""

    def __init__(self, bot: commands.Bot, thread_service: ThreadService):
        """Initialize the ThreadAgent cog."""
        self.bot = bot
        self.thread_service = thread_service

    # --- Helpers -----------------------------------------------------------

    def _strip_mention(self, content: str) -> str:
        return _MENTION_RE.sub("", content).strip()

    def _thread_name(self, source: discord.Message) -> str:
        author = source.author.display_name
        snippet = self._strip_mention(source.content)
        summary = " ".join(snippet.split()[:6])
        name = f"{author} – {summary}" if summary else f"{author}'s thread"
        return name[:_THREAD_NAME_MAX]

    async def _is_feature_enabled(self) -> bool:
        async with AsyncSessionLocal() as session:
            return (
                await FeatureFlagsRepository.get_feature_flag_status(
                    session, FeatureFlagNames.THREAD_AGENT
                )
                or False
            )

    async def _resolve_replied_message(self, message: discord.Message) -> discord.Message | None:
        """Return the message this command is replying to, or None."""
        ref = message.reference
        if ref is None or ref.message_id is None:
            return None
        resolved = ref.resolved
        if isinstance(resolved, discord.Message):
            return resolved
        # resolved may be a DeletedReferencedMessage or not cached — fetch it.
        try:
            return await message.channel.fetch_message(ref.message_id)
        except (discord.NotFound, discord.Forbidden):
            logger.warning(f"ThreadAgent: could not fetch replied message {ref.message_id}")
            return None

    async def _resolve_message_above(self, message: discord.Message) -> discord.Message | None:
        """Return the most recent message before the command, skipping the bot's own."""
        bot_user_id = self.bot.user.id if self.bot.user else None
        async for prev in message.channel.history(limit=_HISTORY_LOOKBACK, before=message):
            if prev.author.id == bot_user_id:
                continue
            return prev
        return None

    # --- Event listener ----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle thread-maker requests in the rides-general channel."""
        if message.author.bot:
            return
        if message.channel.id not in _ALLOWED_CHANNEL_IDS:
            return
        if self.bot.user not in message.mentions:
            return

        prompt = self._strip_mention(message.content)
        if not prompt:
            logger.debug("ThreadAgent: empty prompt after stripping mention, ignoring")
            return

        if not await self._is_feature_enabled():
            logger.debug("ThreadAgent: feature flag disabled, ignoring")
            return

        logger.info(
            f"ThreadAgent: request from {message.author} reply={message.reference is not None} "
            f"prompt={prompt!r}"
        )

        is_reply = message.reference is not None
        source, clarification = await asyncio.to_thread(classify_thread_intent, prompt, is_reply)

        if source == SOURCE_REPLIED:
            target = await self._resolve_replied_message(message)
        elif source == SOURCE_ABOVE:
            target = await self._resolve_message_above(message)
        else:
            target = None

        if target is None:
            await message.reply(clarification or _CLARIFY_FALLBACK, mention_author=False)
            return

        await self._make_event_thread(message, target)

    async def _make_event_thread(
        self, command_message: discord.Message, target: discord.Message
    ) -> None:
        """Create/register the event thread for target and acknowledge with a reaction."""
        try:
            await self.thread_service.create_event_thread_from_message(
                target, self._thread_name(target)
            )
            await command_message.add_reaction("✅")
        except StarterMessageError:
            logger.exception("ThreadAgent: could not read starter message")
            await command_message.add_reaction("❌")
            await command_message.reply(
                "I couldn't read that message to set up the thread.", mention_author=False
            )
        except discord.Forbidden:
            logger.exception("ThreadAgent: missing permissions to create/manage thread")
            await command_message.add_reaction("❌")
            await command_message.reply(
                "I don't have permission to create a thread on that message.",
                mention_author=False,
            )
        except Exception:
            logger.exception("ThreadAgent: unexpected error creating event thread")
            await command_message.add_reaction("❌")
            await command_message.reply(
                "Sorry, something went wrong creating the thread.", mention_author=False
            )


async def setup(bot: commands.Bot):
    """Set up the ThreadAgent cog."""
    await bot.add_cog(ThreadAgent(bot, thread_service=ThreadService()))
