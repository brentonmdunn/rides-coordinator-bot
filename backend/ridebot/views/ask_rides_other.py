"""Discord UI for the "Something else" button on ask-rides announcements."""

import logging

import discord

from ridebot.services.ask_rides_other_service import AskRidesOtherService
from ridebot.utils.constants import (
    ASK_RIDES_OTHER_BUTTON_LABEL,
    ASK_RIDES_OTHER_MAX_LEN,
    ask_rides_other_custom_id,
)
from shared.core.enums import AskRidesMessageType, Emoji
from shared.core.error_reporter import send_error_to_discord

logger = logging.getLogger(__name__)

_UNAVAILABLE = "Sorry, this isn't available right now. Please DM a ride coordinator."
_STALE = "This announcement is from a past week. Please react to or use the latest one."
_COOLDOWN = "You just sent one. Please wait a minute before sending another."
_SENT = "✅ Sent to the ride coordinators. Someone will reach out soon."
_FAILED = "Sorry, that didn't go through. Please DM a ride coordinator."


class AskRidesOtherModal(discord.ui.Modal):
    """Modal asking a rider what they need when no reaction option fits."""

    def __init__(self, message_type: AskRidesMessageType, announcement: discord.Message) -> None:
        """
        Build the modal.

        Args:
            message_type: Which announcement type the button belonged to.
            announcement: The announcement message the button was on.
        """
        super().__init__(title="Something else")
        self.message_type = message_type
        self.announcement = announcement

        self.text_input = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=ASK_RIDES_OTHER_MAX_LEN,
            placeholder="e.g. I need a ride from Pepper Canyon but have to leave early",
        )
        self.add_item(discord.ui.Label(text="What do you need?", component=self.text_input))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Forward the request to the ride coordinators and confirm to the rider."""
        await interaction.response.defer(ephemeral=True)
        ok = await AskRidesOtherService.submit(
            client=interaction.client,
            user=interaction.user,
            message_type=self.message_type,
            announcement=self.announcement,
            text=self.text_input.value,
        )
        await interaction.followup.send(_SENT if ok else _FAILED, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Report an unexpected failure and tell the rider it didn't go through."""
        logger.exception("Unexpected error in ask-rides Something else modal")
        await send_error_to_discord("**Unexpected Error** in ask-rides Something else modal")
        if interaction.response.is_done():
            await interaction.followup.send(_FAILED, ephemeral=True)
        else:
            await interaction.response.send_message(_FAILED, ephemeral=True)


class _SomethingElseButton(discord.ui.Button["AskRidesOtherView"]):
    """The view's single button; delegates clicks to the view."""

    async def callback(self, interaction: discord.Interaction) -> None:
        """Hand the click to the owning view."""
        if self.view is not None:
            await self.view._on_click(interaction)


class AskRidesOtherView(discord.ui.View):
    """Persistent view with one "Something else" button for a single announcement type."""

    def __init__(self, message_type: AskRidesMessageType) -> None:
        """
        Initialize the view with no timeout so it survives bot restarts.

        Args:
            message_type: Which announcement type this view is attached to. It's
                encoded in the button's custom_id, so clicks know their type.
        """
        super().__init__(timeout=None)
        self.message_type = message_type
        self.add_item(
            _SomethingElseButton(
                label=ASK_RIDES_OTHER_BUTTON_LABEL,
                emoji=Emoji.SOMETHING_ELSE.value,
                style=discord.ButtonStyle.secondary,
                custom_id=ask_rides_other_custom_id(message_type),
            )
        )

    async def _on_click(self, interaction: discord.Interaction) -> None:
        """Open the modal, or refuse ephemerally when disabled, stale, or on cooldown."""
        if not await AskRidesOtherService.is_enabled():
            logger.info("Ask-rides Something else button disabled; refusing click")
            await interaction.response.send_message(_UNAVAILABLE, ephemeral=True)
            return

        if interaction.message is None or not AskRidesOtherService.is_current(
            interaction.message.created_at
        ):
            await interaction.response.send_message(_STALE, ephemeral=True)
            return

        if AskRidesOtherService.is_on_cooldown(interaction.user.id):
            await interaction.response.send_message(_COOLDOWN, ephemeral=True)
            return

        await interaction.response.send_modal(
            AskRidesOtherModal(self.message_type, interaction.message)
        )
