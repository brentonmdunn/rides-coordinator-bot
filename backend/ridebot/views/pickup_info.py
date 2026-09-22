"""Discord UI for self-service pickup info."""

import logging
from collections.abc import Callable

import discord

from ridebot.services.pickup_info_service import Person, PickupInfoService
from ridebot.services.pickup_locations_service import PickupLocationsService, PickupSpot
from ridebot.utils.constants import (
    MAX_PHONE_INPUT_LENGTH,
    PICKUP_INFO_OFF_CAMPUS_CUSTOM_ID,
    PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,
    PICKUP_INFO_PAGE_URL,
    PICKUP_INFO_SDSU_CUSTOM_ID,
)
from ridebot.utils.custom_exceptions import PickupInfoConflictError, PickupInfoValidationError
from ridebot.utils.feature_flags import is_flag_enabled
from ridebot.utils.phone import format_phone, phone_status
from shared.core.bots import get_spec
from shared.core.enums import (
    BotName,
    CampusLivingLocations,
    ChannelIds,
    ClassYear,
    FeatureFlagNames,
)
from shared.core.error_reporter import send_error_to_discord
from shared.utils.channels import resolve_channel_id

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
# year. Only the label differs: the stored value stays the ordinal so pickup info and
# ride grouping see one vocabulary.
_SDSU_YEAR_LABELS: dict[str, str] = {
    ClassYear.FIRST.value: "Freshman",
    ClassYear.SECOND.value: "Sophomore",
    ClassYear.THIRD.value: "Junior",
    ClassYear.FOURTH.value: "Senior",
}


async def _pickup_info_enabled() -> bool:
    """Return whether RideBot's kill switch and NEW_RIDES_MSG are both enabled."""
    kill_switch_flag = get_spec(BotName.RIDEBOT).kill_switch_flag
    return await is_flag_enabled(kill_switch_flag) and await is_flag_enabled(
        FeatureFlagNames.NEW_RIDES_MSG
    )


def _coordinator_message(interaction: discord.Interaction, person: Person, created: bool) -> str:
    """
    Build the ride-coordinator copy of a registration notice.

    Unlike the rider's confirmation, this names the Discord account, leads with
    ACTION NEEDED when a rider still has no pickup spot, and links the channel it
    came from so coordinators can follow up there.

    Args:
        interaction: The modal-submit interaction.
        person: The pickup info entry that was created or updated.
        created: Whether this was a new registration.

    Returns:
        The message to post in the ride coordinators channel.
    """
    year = f"{person.year} year" if person.year else "year unknown"
    who = f"**{person.name}** (`@{interaction.user.name}`)"

    # Picking the on-campus catch-all stores no location, so nobody knows where to
    # collect this rider yet. Lead with that instead of burying it mid-sentence.
    if person.location is None:
        message = (
            f"🚨 **ACTION NEEDED, no pickup spot**: {who}, {year}, picked **Other** "
            f"on the form. Someone needs to ask where they live and add it on the "
            f"Pickup Info page ([link]({PICKUP_INFO_PAGE_URL})) · <#{interaction.channel_id}>"
        )
    # SDSU saves cleanly but has no pickup spot mapped, so grouping can't place
    # these riders on its own.
    elif person.location == CampusLivingLocations.SDSU.value:
        message = f"🚨 **ACTION NEEDED, SDSU**: {who}, {year} · <#{interaction.channel_id}>"
    else:
        headline = "📝 New hooman" if created else "📝 Updated"
        message = f"{headline}: {who}, {person.location}, {year} · <#{interaction.channel_id}>"

    # Discord accepts invalid numbers as typed, so flag them here for coordinators
    # to fix rather than silently losing the rider's contact info.
    if phone_status(person.phone) == "invalid":
        message = (
            f"{message}\n"
            f"⚠️ Phone looks invalid: `{person.phone}` — fix it on the Pickup Info "
            f"page ([link]({PICKUP_INFO_PAGE_URL}))"
        )

    return message


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
                "unavailable; skipping pickup info notice"
            )
            return
        # The Pickup Info link would otherwise unfurl into a preview card.
        await channel.send(message, suppress_embeds=True)
    except Exception:
        logger.exception("Failed to post pickup info notice to ride coordinators")


async def _pickup_spots(living_location: str) -> list[PickupSpot]:
    """
    Return a living location's pickup spots, or none if they can't be loaded.

    The rider is already saved by the time this runs, so a lookup failure should
    cost them the pickup hint, not their confirmation.

    Args:
        living_location: The rider's stored living location.
    """
    try:
        return await PickupLocationsService.pickup_spots_for_living(living_location)
    except Exception:
        logger.exception(f"Couldn't load pickup spots for {living_location!r}")
        return []


def _pickup_sentence(spots: list[PickupSpot]) -> str:
    """
    Describe where a rider is usually collected, with a map link for each spot.

    Args:
        spots: The usual spot first, then any alternates. Must not be empty.

    Returns:
        A sentence naming each spot and pointing riders at the announcements channel.
    """
    named_spots = " or ".join(f"**{spot.name}** ([Google Maps]({spot.maps_url}))" for spot in spots)
    return (
        f"The usual pickup spot is {named_spots}, although always make sure to check "
        f"<#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}> for the latest updates."
    )


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
        Build the shared fields, pre-filled from an existing pickup info entry.

        Args:
            existing: The rider's current pickup info entry, or None if unregistered.
            user: The Discord user filling out the form.
            title: The modal's title bar text.
        """
        super().__init__(title=title)
        self.existing = existing

        # Only pre-fill when updating; new riders start blank rather than getting
        # their Discord display name.
        default_name = existing.name if existing else None
        self.name_input = discord.ui.TextInput(default=default_name, required=True, max_length=100)
        self.add_item(discord.ui.Label(text="Name", component=self.name_input))

        existing_year = existing.year if existing else None
        self.year_select = discord.ui.Select(
            options=self._year_options(existing_year), required=True
        )
        self.add_item(discord.ui.Label(text="Year", component=self.year_select))

        default_phone = format_phone(existing.phone) if existing else None
        self.phone_input = discord.ui.TextInput(
            default=default_phone,
            required=True,
            max_length=MAX_PHONE_INPUT_LENGTH,
            placeholder="(858) 555-1234",
        )
        self.add_item(discord.ui.Label(text="Phone number", component=self.phone_input))

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
        Register or update the submitter's pickup info entry.

        Args:
            interaction: The modal-submit interaction.
        """
        name = self.name_input.value
        year = self.year_select.values[0]
        location = self._resolve_location()

        try:
            person, created = await PickupInfoService.register_from_discord(
                discord_user_id=interaction.user.id,
                discord_username=interaction.user.name,
                name=name,
                year=year,
                location=location,
                phone=self.phone_input.value,
            )
        except (PickupInfoValidationError, PickupInfoConflictError) as e:
            await interaction.response.send_message(
                f"Couldn't save that: {e}. Message a ride coordinator and they'll sort it out.",
                ephemeral=True,
            )
            return
        except Exception:
            logger.exception(
                "Unexpected error registering %s via pickup info modal", interaction.user
            )
            await send_error_to_discord("**Unexpected Error** in the pickup info form")
            await interaction.response.send_message(
                "Something went wrong on our end, sorry! Message a ride coordinator "
                "and they'll add you.",
                ephemeral=True,
            )
            return

        opener = f"✅ Thanks **{person.name}**!" if created else f"✅ Updated, **{person.name}**!"
        reach_out = "A ride coordinator will reach out about where to pick you up."
        if person.location is None:
            message = f"{opener} {reach_out}"
        elif person.location == CampusLivingLocations.SDSU.value:
            # Saved, but SDSU has no pickup spot, so promise the follow-up too.
            message = f"{opener} We've got you at {person.location}. {reach_out}"
        else:
            message = f"{opener} We've got you at {person.location}."
            spots = await _pickup_spots(person.location)
            if spots:
                message = f"{message} {_pickup_sentence(spots)}"

        logger.info("Pickup info submitted for %s (created=%s)", interaction.user, created)
        # Maps links would otherwise unfurl into large previews under the message.
        await interaction.response.send_message(message, suppress_embeds=True)
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
                "Pickup info is disabled; refusing button press from %s",
                interaction.user,
            )
            await interaction.response.send_message(
                _PICKUP_INFO_UNAVAILABLE_MESSAGE, ephemeral=True
            )
            return

        existing = await PickupInfoService.find_member(
            discord_user_id=interaction.user.id, discord_username=interaction.user.name
        )
        await interaction.response.send_modal(modal_cls(existing, interaction.user))

    @discord.ui.button(
        label="UCSD on campus",
        style=discord.ButtonStyle.primary,
        custom_id=PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,
    )
    async def on_campus(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the campus-area form."""
        await self._open_modal(interaction, CampusPickupModal)

    @discord.ui.button(
        label="UCSD off campus",
        style=discord.ButtonStyle.primary,
        custom_id=PICKUP_INFO_OFF_CAMPUS_CUSTOM_ID,
    )
    async def off_campus(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the off-campus address form."""
        await self._open_modal(interaction, OffCampusPickupModal)

    @discord.ui.button(
        label="SDSU",
        style=discord.ButtonStyle.primary,
        custom_id=PICKUP_INFO_SDSU_CUSTOM_ID,
    )
    async def sdsu(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Open the SDSU form."""
        await self._open_modal(interaction, SdsuPickupModal)
