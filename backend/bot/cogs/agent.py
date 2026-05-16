"""Cog for the AI ridebot agent."""

import asyncio
import logging
import re
from dataclasses import dataclass, field

import discord
from discord.ext import commands
from langchain_core.messages import AIMessage, HumanMessage

from agent.ridebot_agent import run_agent
from bot.core.database import AsyncSessionLocal
from bot.core.enums import ChannelIds, FeatureFlagNames, RoleIds
from bot.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"<@!?\d+>")
_THREAD_NAME_MAX = 100
_DEBOUNCE_SECONDS = 3


@dataclass
class _ThreadBuffer:
    """Pending messages and debounce task for a single thread."""

    messages: list[str] = field(default_factory=list)
    task: asyncio.Task | None = None


class Agent(commands.Cog):
    """Cog for the conversational AI ridebot agent."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Agent cog."""
        self.bot = bot
        # thread_id -> _ThreadBuffer
        self._buffers: dict[int, _ThreadBuffer] = {}

    # --- Helpers -----------------------------------------------------------

    def _strip_mention(self, content: str) -> str:
        return _MENTION_RE.sub("", content).strip()

    def _thread_name(self, display_name: str, prompt: str) -> str:
        words = prompt.split()[:5]
        summary = " ".join(words)
        name = f"{display_name} – {summary}"
        return name[:_THREAD_NAME_MAX]

    def _has_coordinator_role(self, member: discord.Member) -> bool:
        return any(r.id == int(RoleIds.RIDE_COORDINATOR) for r in member.roles)

    async def _is_feature_enabled(self) -> bool:
        async with AsyncSessionLocal() as session:
            return (
                await FeatureFlagsRepository.get_feature_flag_status(
                    session, FeatureFlagNames.AGENT
                )
                or False
            )

    async def _build_history(
        self, thread: discord.Thread, exclude_id: int
    ) -> list[AIMessage | HumanMessage]:
        history = []
        async for msg in thread.history(limit=15, oldest_first=True):
            if msg.id == exclude_id:
                continue
            content = msg.content
            if msg.author.bot:
                history.append(AIMessage(content=content))
            else:
                history.append(HumanMessage(content=self._strip_mention(content)))
        return history

    # --- Debounced thread response ------------------------------------------

    def _schedule_reply(
        self, thread: discord.Thread, author: discord.Member, message_id: int
    ) -> None:
        buf = self._buffers.setdefault(thread.id, _ThreadBuffer())

        if buf.task and not buf.task.done():
            buf.task.cancel()
            logger.debug(f"Agent: debounce reset for thread {thread.id}")

        buf.task = asyncio.create_task(self._debounced_reply(thread, author, message_id))

    async def _debounced_reply(
        self, thread: discord.Thread, author: discord.Member, message_id: int
    ) -> None:
        await asyncio.sleep(_DEBOUNCE_SECONDS)

        buf = self._buffers.get(thread.id)
        if not buf or not buf.messages:
            logger.debug(f"Agent: debounce fired but buffer empty for thread {thread.id}")
            return

        combined = "\n".join(buf.messages)
        buf.messages.clear()
        logger.debug(f"Agent: debounce fired for thread {thread.id}, prompt={combined!r}")

        history = await self._build_history(thread, exclude_id=message_id)
        logger.debug(f"Agent: history has {len(history)} messages")

        async with thread.typing():
            try:
                reply, _ = await asyncio.to_thread(run_agent, combined, history)
            except Exception:
                logger.exception("Agent: error during run_agent in thread reply")
                await thread.send("Sorry, something went wrong. Please try again.")
                return

        await thread.send(reply)

    # --- Event listener ----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages in the bots channel and its threads."""
        if message.author.bot:
            return

        logger.debug(
            f"Agent: on_message channel={message.channel.id} "
            f"author={message.author} content={message.content!r}"
        )

        in_bots_channel = isinstance(
            message.channel, discord.TextChannel
        ) and message.channel.id == int(ChannelIds.BOT_STUFF__BOTS)
        in_bots_thread = isinstance(
            message.channel, discord.Thread
        ) and message.channel.parent_id == int(ChannelIds.BOT_STUFF__BOTS)

        if not in_bots_channel and not in_bots_thread:
            logger.debug("Agent: message not in bots channel/thread, ignoring")
            return

        if not isinstance(message.author, discord.Member):
            logger.debug("Agent: author is not a Member, ignoring")
            return

        if not self._has_coordinator_role(message.author):
            logger.debug(f"Agent: {message.author} lacks ride coordinator role, ignoring")
            return

        if not await self._is_feature_enabled():
            logger.debug("Agent: feature flag disabled, ignoring")
            return

        # Main channel: require @mention to open a new thread
        if in_bots_channel:
            if self.bot.user not in message.mentions:
                logger.debug("Agent: main channel message without @mention, ignoring")
                return
            prompt = self._strip_mention(message.content)
            if not prompt:
                logger.debug("Agent: empty prompt after stripping mention, ignoring")
                return
            await self._handle_new_thread(message, prompt)
            return

        # Thread: buffer every message and debounce
        prompt = self._strip_mention(message.content)
        if not prompt:
            logger.debug("Agent: empty message in thread, ignoring")
            return

        assert isinstance(message.channel, discord.Thread)
        buf = self._buffers.setdefault(message.channel.id, _ThreadBuffer())
        buf.messages.append(prompt)
        logger.debug(
            f"Agent: buffered message for thread {message.channel.id}, "
            f"buffer size={len(buf.messages)}"
        )
        self._schedule_reply(message.channel, message.author, message.id)

    async def _handle_new_thread(self, message: discord.Message, prompt: str) -> None:
        thread_name = self._thread_name(message.author.display_name, prompt)
        thread = await message.create_thread(name=thread_name)
        logger.info(f"Agent: created thread '{thread_name}' for {message.author}")

        async with thread.typing():
            try:
                reply, _ = await asyncio.to_thread(run_agent, prompt, [])
            except Exception:
                logger.exception("Agent: error during run_agent in new thread")
                await thread.send("Sorry, something went wrong. Please try again.")
                return

        await thread.send(reply)


async def setup(bot: commands.Bot):
    """Sets up the Agent cog."""
    await bot.add_cog(Agent(bot))
