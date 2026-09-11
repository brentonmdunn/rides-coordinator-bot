"""Discord UI for self-service roster registration."""

import logging

import discord

from ridebot.services.roster_service import Person, RosterService
from ridebot.utils.channels import resolve_channel_id
from ridebot.utils.constants import ROSTER_REGISTER_BUTTON_CUSTOM_ID
from ridebot.utils.custom_exceptions import RosterConflictError, RosterValidationError
from shared.core.bots import get_spec
from shared.core.database import AsyncSessionLocal
from shared.core.enums import (
    BotName,
    CampusLivingLocations,
    ChannelIds,
    ClassYear,
    FeatureFlagNames,
)
from shared.core.error_reporter import send_error_to_discord
from shared.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)

_REGISTRATION_UNAVAILABLE_MESSAGE = (
    "Registration is unavailable right now. Please message a ride coordinator."
)

# Sentinel option value for riders who don't live in one of the campus areas.
_OTHER_LOCATION_VALUE = "__other__"
_OTHER_LOCATION_LABEL = "Other (off campus)"


async def _is_flag_enabled(feature: FeatureFlagNames) -> bool:
    """
    Return whether a feature flag is enabled, checking the cache before the DB.

    Args:
        feature: The feature flag to check.

    Returns:
        True if the flag is enabled; False if disabled or missing.
    """
    if feature.value in FeatureFlagsRepository._cache:
        return FeatureFlagsRepository._cache[feature.value]
    async with AsyncSessionLocal() as session:
        status = await FeatureFlagsRepository.get_feature_flag_status(session, feature)
    return bool(status)


def _coordinator_message(interaction: discord.Interaction, person: Person, created: bool) -> str:
    """
    Build the ride-coordinator copy of a registration notice.

    Unlike the rider's confirmation, this names the Discord account, flags an
    off-campus location as needing a pickup spot, and links the channel it came
    from so coordinators can follow up there.

    Args:
        interaction: The modal-submit interaction.
        person: The roster entry that was created or updated.
        created: Whether this was a new registration.

    Returns:
        The message to post in the ride coordinators channel.
    """
    headline = "📝 New rider registered" if created else "📝 Roster updated"

    campus_values = {location.value for location in CampusLivingLocations}
    if person.location is None:
        location = "no location given"
    elif person.location in campus_values:
        location = person.location
    else:
        location = f"{person.location} (off campus — needs a pickup spot)"

    year = f"{person.year} year" if person.year else "year unknown"
    return (
        f"{headline}: **{person.name}** (`@{interaction.user.name}`) — "
        f"{location}, {year} · <#{interaction.channel_id}>"
    )


async def _notify_ride_coordinators(interaction: discord.Interaction, message: str) -> None:
    """
    Mirror a registration confirmation into the ride coordinators channel.

    Never raises: the rider is already registered by this point, so a failure to
    post the notice must not surface as a registration error.

    Args:
        interaction: The modal-submit interaction, used for its bot client.
        message: The same confirmation text the rider was shown.
    """
    try:
        channel = interaction.client.get_channel(
            resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)
        )
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logger.warning(
                f"Ride coordinators channel {ChannelIds.SERVING__RIDE_COORDINATORS} "
                "unavailable; skipping roster registration notice"
            )
            return
        await channel.send(message)
    except Exception:
        logger.exception("Failed to post roster registration notice to ride coordinators")


async def _registration_enabled() -> bool:
    """Return whether RideBot's kill switch and NEW_RIDES_MSG are both enabled."""
    kill_switch_flag = get_spec(BotName.RIDEBOT).kill_switch_flag
    return await _is_flag_enabled(kill_switch_flag) and await _is_flag_enabled(
        FeatureFlagNames.NEW_RIDES_MSG
    )


class RegistrationView(discord.ui.View):
    """Persistent view with a single "Register" button for self-service roster sign-up."""

    def __init__(self) -> None:
        """Initialize the view with no timeout so it survives bot restarts."""
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Register",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id=ROSTER_REGISTER_BUTTON_CUSTOM_ID,
    )
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """
        Open the registration modal, refusing ephemerally when registration is disabled.

        Args:
            interaction: The button-press interaction.
            button: The button that was pressed.
        """
        if not await _registration_enabled():
            logger.info(
                "Roster registration is disabled; refusing button press from %s",
                interaction.user,
            )
            await interaction.response.send_message(
                _REGISTRATION_UNAVAILABLE_MESSAGE, ephemeral=True
            )
            return

        existing = await RosterService.find_member(
            discord_user_id=interaction.user.id, discord_username=interaction.user.name
        )
        await interaction.response.send_modal(RegistrationModal(existing, interaction.user))


class RegistrationModal(discord.ui.Modal, title="Ride registration"):
    """Modal collecting a rider's name, class year, and living location."""

    def __init__(self, existing: Person | None, user: discord.User | discord.Member) -> None:
        """
        Build the modal, pre-filled from an existing roster entry if there is one.

        Args:
            existing: The rider's current roster entry, or None if unregistered.
            user: The Discord user filling out the form.
        """
        super().__init__()

        default_name = (existing.name if existing else None) or user.display_name
        self.name_input = discord.ui.TextInput(default=default_name, required=True, max_length=100)
        self.add_item(discord.ui.Label(text="Name", component=self.name_input))

        existing_year = existing.year if existing else None
        self.year_select = discord.ui.Select(
            options=[
                discord.SelectOption(
                    label=year.value, value=year.value, default=year.value == existing_year
                )
                for year in ClassYear
            ],
            required=True,
        )
        self.add_item(discord.ui.Label(text="Year", component=self.year_select))

        existing_location = existing.location if existing else None
        campus_values = {location.value for location in CampusLivingLocations}
        existing_is_off_campus = (
            existing_location is not None and existing_location not in campus_values
        )
        self.location_select = discord.ui.Select(
            options=[
                *(
                    discord.SelectOption(
                        label=location.value,
                        value=location.value,
                        default=location.value == existing_location,
                    )
                    for location in CampusLivingLocations
                ),
                discord.SelectOption(
                    label=_OTHER_LOCATION_LABEL,
                    value=_OTHER_LOCATION_VALUE,
                    default=existing_is_off_campus,
                ),
            ],
            required=True,
        )
        self.add_item(discord.ui.Label(text="Where do you live?", component=self.location_select))

        self.other_location_input = discord.ui.TextInput(
            default=existing_location if existing_is_off_campus else None,
            required=False,
            max_length=100,
            placeholder="e.g. Costa Verde, or a street address",
        )
        self.add_item(
            discord.ui.Label(
                text="If you picked Other, where do you live?",
                component=self.other_location_input,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Register or update the submitter's roster entry.

        Args:
            interaction: The modal-submit interaction.
        """
        name = self.name_input.value
        year = self.year_select.values[0]
        location = self.location_select.values[0]

        if location == _OTHER_LOCATION_VALUE:
            location = (self.other_location_input.value or "").strip()
            if not location:
                await interaction.response.send_message(
                    f"Please tap **Register** again and, with **{_OTHER_LOCATION_LABEL}** "
                    "selected, type where you live in the last box.",
                    ephemeral=True,
                )
                return

        try:
            person, created = await RosterService.register_from_discord(
                discord_user_id=interaction.user.id,
                discord_username=interaction.user.name,
                name=name,
                year=year,
                location=location,
            )
        except (RosterValidationError, RosterConflictError) as e:
            await interaction.response.send_message(
                f"Couldn't register: {e}. Please message a ride coordinator.",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Unexpected error registering %s via roster modal", interaction.user)
            await send_error_to_discord("**Unexpected Error** in roster registration")
            await interaction.response.send_message(
                "Something went wrong. Please message a ride coordinator.",
                ephemeral=True,
            )
            return

        base_message = f"✅ Registered **{person.name}**: {person.location}, {person.year} year"
        message = base_message if created else f"Updated: {base_message}"
        logger.info("Roster registration submitted for %s (created=%s)", interaction.user, created)
        await interaction.response.send_message(message)
        await _notify_ride_coordinators(
            interaction, _coordinator_message(interaction, person, created)
        )
