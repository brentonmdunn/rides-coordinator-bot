"""Helper functions for group rides logic."""

from datetime import datetime, timedelta

from app.core.logger import logger
from app.core.schemas import LocationQuery, Passenger
from app.core.enums import PickupLocations
from app.utils.constants import MAP_LINKS
from app.utils.locations import lookup_time

PICKUP_ADJUSTMENT = 1
PassengersByLocation = dict[PickupLocations, list[Passenger]]
LocationsPeopleType = dict[str, list[tuple[str, str]]]


def parse_numbers(s: str) -> list[int]:
    """Parses a string of single-digit numbers and returns a list of integers.

    The input string can have numbers separated by spaces or no spaces at all.
    Each number in the input string must be a single digit from 0 to 9.

    Example input: "4 4 4" or "444"

    Args:
        s (str): The input string.

    Returns:
        list[int]: A list of integers.
    """
    # Remove all spaces from the string
    cleaned_string = s.replace(" ", "")

    return [int(char) for char in cleaned_string]


def find_passenger(locations_people: PassengersByLocation, person: str, location: str) -> Passenger | None:
    """Finds a passenger object by name and location.

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
    """Counts the total number of passengers across all locations.

    Args:
        data_dict (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        int: The total count of passengers.
    """
    return sum(len(people_list) for people_list in data_dict.values())


def is_enough_capacity(
    driver_capacity_list: list[int], locations_people: PassengersByLocation
) -> bool:
    """Checks if there is enough driver capacity for all passengers.

    Args:
        driver_capacity_list (list[int]): List of capacities for each driver.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        bool: True if total capacity is greater than or equal to passenger count, False otherwise.
    """
    rider_count = count_tuples(locations_people)
    return sum(driver_capacity_list) >= rider_count


def calculate_pickup_time(
    curr_leave_time: datetime.time, grouped_by_location: list[list[Passenger]], location: str, offset: int
) -> datetime.time:
    """Calculates the pickup time based on the previous location and travel time.

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
    """Formats driver capacity data for LLM input.

    Args:
        driver_capacity (list[int]): List of driver capacities.

    Returns:
        str: A formatted string describing driver capacities.
    """
    return ", ".join(
        f"Driver{i} has capacity {capacity}" for i, capacity in enumerate(driver_capacity)
    )


def llm_input_pickups(locations_people: PassengersByLocation) -> str:
    """Formats pickup location data for LLM input.

    Args:
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        str: A formatted string describing pickup locations and passengers.
    """
    return "\n".join(
        f"{location}: {', '.join(person.identity.name for person in locations_people[location])}"
        for location in locations_people
    ) + ("\n" if locations_people else "")


def create_output(
    llm_result: dict[str, list[dict[str, str]]],
    locations_people: PassengersByLocation,
    end_leave_time: datetime.time,
    off_campus: LocationsPeopleType,
) -> list[str]:
    """Creates the final output messages based on the LLM result.

    Args:
        llm_result (dict[str, list[dict[str, str]]]): The result from the LLM.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.
        end_leave_time (datetime.time): The target arrival time.
        off_campus (LocationsPeopleType): Dictionary of off-campus passengers.

    Returns:
        list[str]: A list of formatted output strings.
    """
    overall_summary = "==== summary ====\n"

    # Create O(1) lookup map for passengers by name to avoid repeated O(N) searches
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

            passenger = passenger_lookup.get(person_name)
            if not passenger:
                logger.warning(f"Passenger {person_name} not found in lookup map")
                continue

            # New group or part of same group as prev
            if len(curr_location) == 0 or location == curr_location[-1].pickup_location:
                curr_location.append(passenger)
            # Need to end curr group and create new group
            else:
                grouped_by_location.append(curr_location)
                curr_location: list[Passenger] = []
                curr_location.append(passenger)

        grouped_by_location.append(curr_location)

        drive_formatted = []
        drive_summary = []

        # grouped_by_location is in order by who to pickup first. Need it
        # reversed so can calculate pickup time backwards from goal leave time
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

            # Add google maps link if we have it
            if pickup_location in MAP_LINKS:
                formatted_string = f"{base_string} ([Google Maps]({MAP_LINKS[pickup_location]}))"
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
            overall_summary += f"""  - {key}: {", ".join([f"{person[0]} (`@{person[1]}`)" for person in off_campus[key]])}\n"""  # noqa: E501

    overall_summary += "================="
    output_list.insert(0, overall_summary)
    return output_list
