"""Pure domain functions for ride grouping, capacity checks, and output formatting."""

import logging
from datetime import datetime, timedelta

from bot.core.enums import PickupLocations
from bot.core.schemas import LocationQuery, Passenger
from bot.utils.constants import get_map_url
from bot.utils.locations import lookup_time

logger = logging.getLogger(__name__)

PICKUP_ADJUSTMENT = 1

LocationsPeopleType = dict[str, list[tuple[str, str]]]
PassengersByLocation = dict[PickupLocations, list[Passenger]]


def _normalize_location_string(raw: str) -> str:
    """Lowercase + collapse whitespace for forgiving location string comparison."""
    return " ".join(raw.lower().split())


def resolve_chosen_pickup(chosen_raw: str, passenger: Passenger) -> PickupLocations:
    """
    Map the LLM's chosen location string to one of the passenger's allowed pickup enums.

    The LLM may output either the full enum value ("Marshall uppers") or a
    short form ("Marshall" / "GeiselLoop" / "Geisel Loop"). We accept any form
    that resolves to one of ``passenger.allowed_pickup_locations``. If nothing
    matches we fall back to the passenger's primary pickup so downstream code
    doesn't crash on a typo — the validator will have already raised for the
    mismatch at this point, so reaching here implies the validator also
    accepted the input.
    """

    def forms(raw: str) -> tuple[str, str, str]:
        full = _normalize_location_string(raw)
        short = full.split()[0] if full else full
        compressed = full.replace(" ", "")
        return full, short, compressed

    chosen_full, chosen_short, chosen_compressed = forms(chosen_raw)
    chosen_forms = {chosen_full, chosen_short, chosen_compressed}

    for candidate in passenger.allowed_pickup_locations:
        cand_full, cand_short, cand_compressed = forms(str(candidate))
        if chosen_forms & {cand_full, cand_short, cand_compressed}:
            return candidate

    logger.warning(
        f"Could not resolve chosen location '{chosen_raw}' for {passenger.identity.name}; "
        f"falling back to primary pickup {passenger.pickup_location}."
    )
    return passenger.pickup_location


def parse_numbers(s: str) -> list[int]:
    """
    Parses a string of single-digit numbers and returns a list of integers.

    The input string can have numbers separated by spaces or no spaces at all.
    Each number in the input string must be a single digit from 0 to 9.

    Example input: "4 4 4" or "444"

    Args:
        s (str): The input string.

    Returns:
        list[int]: A list of integers.
    """
    cleaned_string = s.replace(" ", "")
    return [int(char) for char in cleaned_string]


def find_passenger(locations_people: PassengersByLocation, person: str, location: str) -> Passenger:
    """
    Finds a passenger object by name and location.

    Args:
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.
        person (str): The name of the person to find.
        location (str): The location key to search in.

    Returns:
        Passenger: The Passenger object if found, otherwise None.
    """
    if location in locations_people:
        for p in locations_people[location]:
            if p.identity.name == person:
                return p
    logger.warning(f"None was returned for {locations_people=} {person=}")
    return None


def count_tuples(data_dict: PassengersByLocation) -> int:
    """
    Counts the total number of passengers across all locations.

    Args:
        data_dict (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        int: The total count of passengers.
    """
    return sum(len(people_list) for people_list in data_dict.values())


def is_enough_capacity(
    driver_capacity_list: list[int], locations_people: PassengersByLocation
) -> bool:
    """
    Checks if there is enough driver capacity for all passengers.

    Args:
        driver_capacity_list (list[int]): List of capacities for each driver.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        bool: True if total capacity is greater than or equal to passenger count, False otherwise.
    """
    rider_count = count_tuples(locations_people)
    return sum(driver_capacity_list) >= rider_count


def calculate_pickup_time(
    curr_leave_time: datetime.time, grouped_by_location, location: str, offset: int
) -> datetime.time:
    """
    Calculates the pickup time based on the previous location and travel time.

    Args:
        curr_leave_time (datetime.time): The leave time from the previous location.
        grouped_by_location (list): List of passenger groups.
        location (str): The current pickup location.
        offset (int): The offset index for the previous location.

    Returns:
        datetime.time: The calculated pickup time.
    """
    time_between = PICKUP_ADJUSTMENT + lookup_time(
        LocationQuery(
            start_location=grouped_by_location[len(grouped_by_location) - offset][
                0
            ].pickup_location,
            end_location=location,
        )
    )
    dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
    new_datetime = dummy_datetime - timedelta(minutes=time_between)
    return new_datetime.time()


def llm_input_drivers(driver_capacity: list[int]) -> str:
    """
    Formats driver capacity data for LLM input.

    Args:
        driver_capacity (list[int]): List of driver capacities.

    Returns:
        str: A formatted string describing driver capacities.
    """
    return ", ".join(
        f"Driver{i} has capacity {capacity}" for i, capacity in enumerate(driver_capacity)
    )


def llm_input_pickups(locations_people: PassengersByLocation) -> str:
    """
    Formats pickup location data for LLM input.

    Passengers with a single allowed pickup location are listed grouped by that
    location in the usual ``"<Location>: name1, name2"`` format. Passengers with
    multiple allowed pickup locations (flex pickups, e.g. Marshall residents
    who can also be picked up at Geisel Loop) are listed one-per-line under a
    "Flex pickups" section with an ``[allowed: A, B]`` tag so the LLM can pick
    a location per passenger.

    Args:
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        str: A formatted string describing pickup locations and passengers.
    """
    if not locations_people:
        return ""

    fixed_lines: list[str] = []
    flex_lines: list[str] = []

    for location, passengers in locations_people.items():
        fixed_names = [p.identity.name for p in passengers if not p.is_flex]
        if fixed_names:
            fixed_lines.append(f"{location}: {', '.join(fixed_names)}")
        for passenger in passengers:
            if not passenger.is_flex:
                continue
            allowed = ", ".join(str(loc) for loc in passenger.allowed_pickup_locations)
            flex_lines.append(f"- {passenger.identity.name} [allowed: {allowed}]")

    sections: list[str] = []
    if fixed_lines:
        sections.append("\n".join(fixed_lines))
    if flex_lines:
        sections.append("Flex pickups (assign each passenger to exactly one allowed location):")
        sections.append("\n".join(flex_lines))

    return "\n".join(sections) + "\n"


def create_output(
    llm_result: dict[str, list[dict[str, str]]],
    locations_people: PassengersByLocation,
    end_leave_time: datetime.time,
    off_campus: LocationsPeopleType,
) -> list[str]:
    """
    Creates the final output messages based on the LLM result.

    Args:
        llm_result (dict[str, list[dict[str, str]]]): The result from the LLM.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.
        end_leave_time (datetime.time): The target arrival time.
        off_campus (LocationsPeopleType): Dictionary of off-campus passengers.

    Returns:
        list[str]: A list of formatted output strings.
    """
    overall_summary = "==== summary ====\n"

    passenger_lookup = {
        passenger.identity.name: passenger
        for passengers in locations_people.values()
        for passenger in passengers
    }
    output_list = []

    for driver_id in llm_result:
        curr_leave_time = end_leave_time
        grouped_by_location: list[list[Passenger]] = []
        curr_location: list[Passenger] = []

        for obj in llm_result[driver_id]:
            person_name = obj["name"]
            location = obj["location"]

            original = passenger_lookup.get(person_name)
            if not original:
                logger.warning(f"Passenger {person_name} not found in lookup map")
                continue

            # Resolve the LLM's chosen location to one of the passenger's allowed
            # pickup enums, then project that choice onto the Passenger so every
            # downstream consumer (grouping, pickup-time math, formatted output)
            # sees the same location. Required for Marshall-flex where the
            # chosen location can differ from ``original.pickup_location``.
            chosen = resolve_chosen_pickup(location, original)
            passenger = original.model_copy(update={"pickup_location": chosen})

            if len(curr_location) == 0 or chosen == curr_location[-1].pickup_location:
                curr_location.append(passenger)
            else:
                grouped_by_location.append(curr_location)
                curr_location = [passenger]

        grouped_by_location.append(curr_location)

        drive_formatted = []
        drive_summary = []

        for idx, users_at_location in enumerate(reversed(grouped_by_location)):
            usernames_at_location = [
                p.identity.username if p.identity.username is not None else p.identity.name
                for p in users_at_location
            ]
            names_at_location = [p.identity.name for p in users_at_location]

            pickup_location = users_at_location[0].pickup_location

            if idx != 0:
                curr_leave_time = calculate_pickup_time(
                    curr_leave_time, grouped_by_location, pickup_location, idx
                )

            base_string = (
                f"{' '.join(usernames_at_location)} "
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} "
                f"{pickup_location}"
            )

            map_url = get_map_url(pickup_location)
            if map_url:
                formatted_string = f"{base_string} ([Google Maps]({map_url}))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)
            drive_summary.append(
                f"[{len(names_at_location)}] "
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} "
                f"{pickup_location.split()[0]}"
            )

        overall_summary += f"- {' > '.join(reversed(drive_summary))}\n"

        copy_str = f"drive: {', '.join(reversed(drive_formatted))}\n"
        output_list.append(copy_str)
        output_list.append(f"```\n{copy_str}\n```")

    if len(off_campus) != 0:
        overall_summary += "- TODO: off campus\n"
        for key in off_campus:
            overall_summary += f"""  - {key}: {", ".join([f"{person[0]} (`@{person[1]}`)" for person in off_campus[key]])}\n"""

    overall_summary += "================="
    output_list.insert(0, overall_summary)
    return output_list
