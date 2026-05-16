"""Cog for the AI ridebot agent."""

import asyncio
import logging
import re

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


class Agent(commands.Cog):
    """Cog for the conversational AI ridebot agent."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Agent cog."""
        self.bot = bot

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

    # --- Event listener ----------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle @mentions in the bots channel and its threads."""
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return

        in_bots_channel = isinstance(
            message.channel, discord.TextChannel
        ) and message.channel.id == int(ChannelIds.BOT_STUFF__BOTS)
        in_bots_thread = isinstance(
            message.channel, discord.Thread
        ) and message.channel.parent_id == int(ChannelIds.BOT_STUFF__BOTS)

        if not in_bots_channel and not in_bots_thread:
            return

        if not isinstance(message.author, discord.Member):
            return
        if not self._has_coordinator_role(message.author):
            return

        if not await self._is_feature_enabled():
            return

        prompt = self._strip_mention(message.content)
        if not prompt:
            return

        if in_bots_channel:
            await self._handle_new_thread(message, prompt)
        else:
            await self._handle_thread_reply(message, prompt)

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

    async def _handle_thread_reply(self, message: discord.Message, prompt: str) -> None:
        thread = message.channel
        assert isinstance(thread, discord.Thread)
        history = await self._build_history(thread, exclude_id=message.id)
        logger.info(f"Agent: thread reply from {message.author}, history={len(history)} msgs")

        async with thread.typing():
            try:
                reply, _ = await asyncio.to_thread(run_agent, prompt, history)
            except Exception:
                logger.exception("Agent: error during run_agent in thread reply")
                await thread.send("Sorry, something went wrong. Please try again.")
                return

        await thread.send(reply)


async def setup(bot: commands.Bot):
    """Sets up the Agent cog."""
    await bot.add_cog(Agent(bot))
