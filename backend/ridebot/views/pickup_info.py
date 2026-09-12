"""Discord UI for self-service pickup info."""

import logging
from collections.abc import Callable

import discord

from ridebot.services.roster_service import Person, RosterService
from ridebot.utils.channels import resolve_channel_id
from ridebot.utils.constants import (
    ROSTER_PICKUP_OFF_CAMPUS_CUSTOM_ID,
    ROSTER_PICKUP_ON_CAMPUS_CUSTOM_ID,
    ROSTER_PICKUP_SDSU_CUSTOM_ID,
)
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

_PICKUP_INFO_UNAVAILABLE_MESSAGE = (
    "Sorry, this isn't available right now. Message a ride coordinator "
    "and they'll add your pickup info for you."
)

# Appended to the on-campus dropdown when the modal is built. Deliberately not a
# CampusLivingLocations member: it isn't a real place, so it must never reach ride
# grouping or the pickup-location mappings. Picking it stores no location at all.
_NEEDS_FOLLOWUP_VALUE = "__needs_followup__"
_NEEDS_FOLLOWUP_LABEL = "Other - ride coordinators will reach out"

# SDSU riders think in class names, not UCSD's ordinal years, and SDSU has no 5th
# year. Only the label differs: the stored value stays the ordinal so the roster and
# ride grouping see one vocabulary.
_SDSU_YEAR_LABELS: dict[str, str] = {
    ClassYear.FIRST.value: "Freshman",
    ClassYear.SECOND.value: "Sophomore",
    ClassYear.THIRD.value: "Junior",
    ClassYear.FOURTH.value: "Senior",
}


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


async def _pickup_info_enabled() -> bool:
    """Return whether RideBot's kill switch and NEW_RIDES_MSG are both enabled."""
    kill_switch_flag = get_spec(BotName.RIDEBOT).kill_switch_flag
    return await _is_flag_enabled(kill_switch_flag) and await _is_flag_enabled(
        FeatureFlagNames.NEW_RIDES_MSG
    )


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
    year = f"{person.year} year" if person.year else "year unknown"
    who = f"**{person.name}** (`@{interaction.user.name}`)"

    # Picking the on-campus catch-all stores no location, so nobody knows where to
    # collect this rider yet. Lead with that instead of burying it mid-sentence.
    if person.location is None:
        return (
            f"🚨 **ACTION NEEDED, no pickup spot**: {who}, {year}, picked **Other** "
            f"on the form. Someone needs to ask where they live and add it to the "
            f"roster. In <#{interaction.channel_id}>"
        )

    headline = "📝 New rider registered" if created else "📝 Roster updated"
    campus_values = {location.value for location in CampusLivingLocations}
    location = (
        person.location
        if person.location in campus_values
        else f"{person.location} (off campus, needs a pickup spot)"
    )
    return f"{headline}: {who}, {location}, {year}. In <#{interaction.channel_id}>"


async def _notify_ride_coordinators(interaction: discord.Interaction, message: str) -> None:
    """
    Mirror a registration confirmation into the ride coordinators channel.

    Never raises: the rider is already registered by this point, so a failure to
    post the notice must not surface as a registration error.

    Args:
        interaction: The modal-submit interaction, used for its bot client.
        message: The notice to post.
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


class _BasePickupModal(discord.ui.Modal):
    """
    Shared Name and Year fields for every registration modal.

    Subclasses add whatever location input suits their button and implement
    ``_resolve_location``. Splitting by button is what lets each form ask only
    the questions that apply, since Discord modals can't hide fields.
    """

    def __init__(
        self, existing: Person | None, user: discord.User | discord.Member, *, title: str
    ) -> None:
        """
        Build the shared fields, pre-filled from an existing roster entry.

        Args:
            existing: The rider's current roster entry, or None if unregistered.
            user: The Discord user filling out the form.
            title: The modal's title bar text.
        """
        super().__init__(title=title)
        self.existing = existing

        default_name = (existing.name if existing else None) or user.display_name
        self.name_input = discord.ui.TextInput(default=default_name, required=True, max_length=100)
        self.add_item(discord.ui.Label(text="Name", component=self.name_input))

        existing_year = existing.year if existing else None
        self.year_select = discord.ui.Select(
            options=self._year_options(existing_year), required=True
        )
        self.add_item(discord.ui.Label(text="Year", component=self.year_select))

    def _year_options(self, existing_year: str | None) -> list[discord.SelectOption]:
        """
        Return the Year choices for this form.

        Subclasses may relabel the choices for their own school, but the value stays
        a ``ClassYear`` so everything downstream reads one vocabulary.

        Args:
            existing_year: The rider's stored year, pre-selected when it matches.
        """
        return [
            discord.SelectOption(
                label=year.value, value=year.value, default=year.value == existing_year
            )
            for year in ClassYear
        ]

    def _resolve_location(self) -> str | None:
        """Return the submitted location, or None when a coordinator must follow up."""
        raise NotImplementedError

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Register or update the submitter's roster entry.

        Args:
            interaction: The modal-submit interaction.
        """
        name = self.name_input.value
        year = self.year_select.values[0]
        location = self._resolve_location()

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
                f"Couldn't save that: {e}. Message a ride coordinator and they'll sort it out.",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception("Unexpected error registering %s via roster modal", interaction.user)
            await send_error_to_discord("**Unexpected Error** in roster registration")
            await interaction.response.send_message(
                "Something went wrong on our end, sorry! Message a ride coordinator "
                "and they'll add you.",
                ephemeral=True,
            )
            return

        opener = f"✅ Thanks **{person.name}**!" if created else f"✅ Updated, **{person.name}**!"
        if person.location is None:
            message = f"{opener} A ride coordinator will reach out about where to pick you up."
        else:
            message = f"{opener} We've got you at {person.location}."

        logger.info("Roster registration submitted for %s (created=%s)", interaction.user, created)
        await interaction.response.send_message(message)
        await _notify_ride_coordinators(
            interaction, _coordinator_message(interaction, person, created)
        )


class CampusPickupModal(_BasePickupModal):
    """Modal for riders living in a campus living area."""

    def __init__(self, existing: Person | None, user: discord.User | discord.Member) -> None:
        """Add a campus-area dropdown, plus an option for anything not listed."""
        super().__init__(existing, user, title="UCSD on campus pickup")

        # SDSU is a living location, but it has its own button, so offering it here
        # too would be a second route to the same answer.
        campus_options = [
            location
            for location in CampusLivingLocations
            if location is not CampusLivingLocations.SDSU
        ]
        campus_values = {location.value for location in campus_options}
        existing_location = existing.location if existing else None
        existing_is_campus = existing_location in campus_values

        options = [
            discord.SelectOption(
                label=location.value,
                value=location.value,
                default=existing_is_campus and location.value == existing_location,
            )
            for location in campus_options
        ]
        options.append(
            discord.SelectOption(label=_NEEDS_FOLLOWUP_LABEL, value=_NEEDS_FOLLOWUP_VALUE)
        )

        self.location_select = discord.ui.Select(options=options, required=True)
        self.add_item(discord.ui.Label(text="Where do you live?", component=self.location_select))

    def _resolve_location(self) -> str | None:
        """Return the chosen campus area, or None when they picked the catch-all."""
        value = self.location_select.values[0]
        return None if value == _NEEDS_FOLLOWUP_VALUE else value


class OffCampusPickupModal(_BasePickupModal):
    """Modal for riders living off campus, who type their own address."""

    def __init__(self, existing: Person | None, user: discord.User | discord.Member) -> None:
        """Add a free-text address box, pre-filled from an existing off-campus entry."""
        super().__init__(existing, user, title="UCSD off campus pickup")

        campus_values = {location.value for location in CampusLivingLocations}
        existing_location = existing.location if existing else None
        existing_is_off_campus = (
            existing_location is not None and existing_location not in campus_values
        )

        self.address_input = discord.ui.TextInput(
            default=existing_location if existing_is_off_campus else None,
            required=True,
            max_length=100,
            placeholder="Apartment name or street address",
        )
        self.add_item(discord.ui.Label(text="Where do you live?", component=self.address_input))

    def _resolve_location(self) -> str | None:
        """Return the typed address; Discord enforces that it isn't blank."""
        return (self.address_input.value or "").strip()


class SdsuPickupModal(_BasePickupModal):
    """Modal for SDSU riders, whose location is implied by the button."""

    def __init__(self, existing: Person | None, user: discord.User | discord.Member) -> None:
        """Ask only for name and year; the button already answered the location."""
        super().__init__(existing, user, title="SDSU pickup")

    def _year_options(self, existing_year: str | None) -> list[discord.SelectOption]:
        """Return SDSU's class names, each still carrying its ordinal value."""
        return [
            discord.SelectOption(label=label, value=value, default=value == existing_year)
            for value, label in _SDSU_YEAR_LABELS.items()
        ]

    def _resolve_location(self) -> str | None:
        """Return the SDSU living location."""
        return CampusLivingLocations.SDSU.value


class PickupInfoView(discord.ui.View):
    """Persistent view whose buttons each open a registration form for one situation."""

    def __init__(self) -> None:
        """Initialize the view with no timeout so it survives bot restarts."""
        super().__init__(timeout=None)

    async def _open_modal(
        self,
        interaction: discord.Interaction,
        modal_cls: Callable[[Person | None, discord.User | discord.Member], _BasePickupModal],
    ) -> None:
        """
        Open one of the registration modals, refusing when registration is disabled.

        Args:
            interaction: The button-press interaction.
            modal_cls: The modal subclass matching the button that was pressed. Typed as a
                callable because each subclass supplies its own title to the base class.
        """
        if not await _pickup_info_enabled():
            logger.info(
                "Roster registration is disabled; refusing button press from %s",
                interaction.user,
            )
            await interaction.response.send_message(
                _PICKUP_INFO_UNAVAILABLE_MESSAGE, ephemeral=True
            )
            return

        existing = await RosterService.find_member(
            discord_user_id=interaction.user.id, discord_username=interaction.user.name
        )
        await interaction.response.send_modal(modal_cls(existing, interaction.user))

    @discord.ui.button(
        label="UCSD on campus",
        style=discord.ButtonStyle.primary,
        custom_id=ROSTER_PICKUP_ON_CAMPUS_CUSTOM_ID,
    )
    async def on_campus(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the campus-area form."""
        await self._open_modal(interaction, CampusPickupModal)

    @discord.ui.button(
        label="UCSD off campus",
        style=discord.ButtonStyle.primary,
        custom_id=ROSTER_PICKUP_OFF_CAMPUS_CUSTOM_ID,
    )
    async def off_campus(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the off-campus address form."""
        await self._open_modal(interaction, OffCampusPickupModal)

    @discord.ui.button(
        label="SDSU",
        style=discord.ButtonStyle.primary,
        custom_id=ROSTER_PICKUP_SDSU_CUSTOM_ID,
    )
    async def sdsu(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the SDSU form."""
        await self._open_modal(interaction, SdsuPickupModal)
