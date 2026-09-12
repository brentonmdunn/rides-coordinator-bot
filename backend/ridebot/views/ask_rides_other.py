"""Discord UI for the "Something else" button on ask-rides announcements."""

import logging

import discord

from ridebot.utils.constants import ASK_RIDES_OTHER_BUTTON_LABEL, ask_rides_other_custom_id
from shared.core.enums import AskRidesMessageType, Emoji

logger = logging.getLogger(__name__)


class AskRidesOtherModal(discord.ui.Modal):
    """Modal asking a rider what they need when no reaction option fits."""

    def __init__(self, message_type: AskRidesMessageType, announcement: discord.Message) -> None:
        """
        Build the modal.

        Args:
            message_type: Which announcement type the button belonged to.
            announcement: The announcement message the button was on.
        """
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Forward the request to the ride coordinators and confirm to the rider."""
        raise NotImplementedError

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Report an unexpected failure and tell the rider it didn't go through."""
        raise NotImplementedError


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
        raise NotImplementedError
