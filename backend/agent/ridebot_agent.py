"""
Ridebot agent using LangChain.

To switch providers, swap the `llm` definition below:

  TritonAI (current):
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="api-gpt-oss-120b", base_url=..., api_key=...)

  Gemini:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

  OpenAI:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    load_dotenv(Path(__file__).parent.parent / ".env")
    sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.services.pickup_locations_service import PickupLocationsService  # noqa: E402
from bot.services.route_service import RouteService  # noqa: E402
from bot.utils.parsing import parse_time  # noqa: E402
from bot.utils.time_helpers import is_in_ride_day_window  # noqa: E402

# --- LLM -------------------------------------------------------------------

llm = ChatOpenAI(
    model="api-gpt-oss-120b",
    base_url="https://tritonai-api.ucsd.edu/v1",
    api_key=SecretStr(os.environ["TRITON_API_KEY"]),
)

BACKEND_URL = "http://localhost:8000"
_INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")
_INTERNAL_HEADERS = {"X-Internal-Secret": _INTERNAL_SECRET} if _INTERNAL_SECRET else {}

SYSTEM_PROMPT = """You are a ride coordinator assistant for a UCSD college fellowship.
You help plan pickup routes for drivers and list who needs rides.

When a user asks you to make a route, prefer make_route_with_riders over make_route.
Omit the day argument unless the user explicitly specifies a day — the tool auto-detects friday or sunday from the current time window.
When a user asks who needs a ride on Sunday, call the list_pickups_sunday tool.
When a user asks who needs a ride on Friday, call the list_pickups_friday tool.
When a user asks where someone gets picked up, call the pickup_location tool.
When a user asks for map links or Google Maps URLs, call the map_links tool.
When a user asks to add someone as a driver or ride coordinator, call the add_role tool with role='driver' or role='ride coordinator'.
When a user asks to remove someone from the driver or ride coordinator role, call the remove_role tool with role='driver' or role='ride coordinator'.

Valid location tokens (case-insensitive, fuzzy matching supported):
  SEVENTH, ERC, MARSHALL, SIXTH, MUIR, WARREN_EQL, WARREN_JST,
  RITA, INNOVATION, EIGHTH, PANGEA, VILLAS_OF_RENAISSANCE,
  GEISEL_LOOP, PCYN_LOOP

For make_route_with_riders, the tool returns: route, rider_count, riders_by_stop, route_with_riders.

When rider_count <= 4:
- If the user's message already signals they want names (e.g. "with people", "with names",
  "with usernames", "with riders", "include names"): output route_with_riders exactly as-is.
- Otherwise show the plain route, then ask if they want usernames included.
- If they say yes, output route_with_riders exactly as-is.

When rider_count > 4:
- Show the plain route.
- List riders grouped by stop from riders_by_stop, showing each person's name and count.
- Ask the user which riders to include (e.g. "all from Seventh", "2 from Marshall").
- When the user replies, select the appropriate people (pick randomly if count given but
  no names specified), then format the route yourself using this exact pattern:
  @username1 @username2 HH:MMam Stop name ([Google Maps](<url>)), @username3 HH:MMam Stop name ([Google Maps](<url>))
  Use the times and URLs from the route field. Output this string with no extra commentary.

For list_pickups_sunday, format the result as a clean readable summary grouped by
housing area, showing each person's name and pickup location."""

# --- Tools -----------------------------------------------------------------


@tool
def make_route(locations: str, leave_time: str) -> str:
    """
    Build a pickup route with staggered departure times for each stop.

    Args:
        locations: Space-separated pickup location tokens in pickup order (e.g. 'revelle muir eighth').
        leave_time: Departure time from the final stop (e.g. '5:30pm').

    Returns:
        Formatted string with pickup times and Google Maps links.
    """
    logger.info(f"Tool: make_route locations={locations!r} leave_time={leave_time!r}")
    routing = PickupLocationsService.get_routing_context_sync()
    return RouteService.make_route(routing, locations, leave_time)


@tool
def list_pickups_sunday() -> str:
    """
    Fetch who needs a ride on Sunday, grouped by housing area.

    Returns:
        JSON string with housing groups and the people in each group.
    """
    logger.info("Tool: list_pickups_sunday")
    response = httpx.post(
        f"{BACKEND_URL}/api/list-pickups",
        json={"ride_type": "sunday"},
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    return json.dumps(response.json(), indent=2)


@tool
def list_pickups_friday() -> str:
    """
    Fetch who needs a ride on Friday, grouped by housing area.

    Returns:
        JSON string with housing groups and the people in each group.
    """
    logger.info("Tool: list_pickups_friday")
    response = httpx.post(
        f"{BACKEND_URL}/api/list-pickups",
        json={"ride_type": "friday"},
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    return json.dumps(response.json(), indent=2)


@tool
def pickup_location(name: str) -> str:
    """
    Look up the pickup location for a person by name or Discord username.

    Args:
        name: The person's name or Discord username to search for.

    Returns:
        JSON string with a list of matches, each containing name and location.
    """
    logger.info(f"Tool: pickup_location name={name!r}")
    response = httpx.get(
        f"{BACKEND_URL}/api/locations/pickup-location",
        params={"name": name},
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    response.raise_for_status()
    return json.dumps(response.json(), indent=2)


@tool
def map_links(location: str | None = None) -> str:
    """
    Get Google Maps links for pickup locations.

    Args:
        location: Optional location name to filter by (e.g. 'seventh', 'muir').
                  If omitted, returns links for all pickup locations.

    Returns:
        Formatted string with location names and their Google Maps URLs.
    """
    logger.info(f"Tool: map_links location={location!r}")
    routing = PickupLocationsService.get_routing_context_sync()
    links = routing.map_links()
    if location:
        term = location.lower()
        links = {name: url for name, url in links.items() if term in name.lower()}
    if not links:
        return "No matching locations found."
    return "\n".join(f"{name}: {url}" for name, url in links.items())


# Keywords that appear in raw DB location strings for each pickup location name.
# DB stores free-form strings (e.g. "seventh", "warren") not full pickup names.
_LOCATION_KEYWORDS: dict[str, list[str]] = {
    "Seventh mail room": ["seventh"],
    "ERC across from bamboo": ["erc"],
    "Marshall uppers": ["marshall"],
    "Sixth loop": ["sixth"],
    "Muir tennis courts": ["muir"],
    "Warren Equality Ln": ["warren"],
    "Warren Justice Ln": ["warren"],
    "Rita": ["rita"],
    "Innovation": ["innovation"],
    "Eighth basketball courts": ["eighth"],
    "Geisel Loop": ["geisel"],
    "Pepper Canyon Loop": ["pcyn", "pepper canyon"],
}


def _people_for_stop(location: str, loc_to_people: dict[str, list[dict]]) -> list[dict]:
    """Return all people whose raw DB location string matches this stop's keywords."""
    keywords = _LOCATION_KEYWORDS.get(location, [location.split()[0].lower()])
    matched: list[dict] = []
    for raw_loc, people in loc_to_people.items():
        if any(kw in raw_loc.lower() for kw in keywords):
            matched.extend(people)
    return matched


def _format_route_with_riders(stops_with_people: list[dict]) -> str:
    """Build the @mention route string from structured stop+people data."""
    parts = []
    for stop in stops_with_people:
        mentions = " ".join(
            f"@{p['discord_username']}" if p["discord_username"] else p["name"]
            for p in stop["people"]
        )
        time_loc = f"{stop['time']} {stop['location']}"
        if stop["maps_url"]:
            time_loc += f" ([Google Maps](<{stop['maps_url']}>))"
        parts.append(f"{mentions} {time_loc}" if mentions else time_loc)
    return ", ".join(parts)


def _build_route_stops(locations_str: str, leave_time_str: str) -> list[dict]:
    """Return structured route stops: [{time, location, maps_url}] in pickup order."""
    curr_leave_time = parse_time(leave_time_str)
    routing = PickupLocationsService.get_routing_context_sync()
    locations_list: list[str] = []
    for token in locations_str.split():
        match = routing.fuzzy_match(token)
        if match:
            locations_list.append(match)

    stops: list[dict] = []
    reversed_locs = list(reversed(locations_list))
    for idx, location in enumerate(reversed_locs):
        if idx != 0:
            time_between = routing.pickup_adjustment + routing.lookup_time(
                location, reversed_locs[idx - 1]
            )
            dummy_dt = datetime.combine(datetime.today(), curr_leave_time)
            curr_leave_time = (dummy_dt - timedelta(minutes=time_between)).time()
        stops.append(
            {
                "time": curr_leave_time.strftime("%I:%M%p").lstrip("0").lower(),
                "location": location,
                "maps_url": routing.map_url(location),
            }
        )

    return list(reversed(stops))


@tool
def make_route_with_riders(locations: str, leave_time: str, day: str = "auto") -> str:
    """
    Build a pickup route and check how many riders need each stop on the given day.

    Returns JSON with:
      - route: plain formatted route string
      - rider_count: total riders across all stops
      - route_with_riders: route string with Discord @mentions prepended to each stop
                           (only populated when rider_count <= 4, else null)

    Args:
        locations: Space-separated pickup location tokens in pickup order.
        leave_time: Departure time from the final stop (e.g. '5:30pm').
        day: Which day's pickups to use — 'sunday', 'friday', or 'auto' (default).
             'auto' picks friday if currently in the Friday ride window, else sunday.
    """
    if day.lower() == "auto":
        day = "friday" if is_in_ride_day_window("Friday") else "sunday"

    logger.info(
        f"Tool: make_route_with_riders locations={locations!r} leave_time={leave_time!r} day={day!r}"
    )
    routing = PickupLocationsService.get_routing_context_sync()
    route = RouteService.make_route(routing, locations, leave_time)

    fetch_tool = list_pickups_friday if day.lower() == "friday" else list_pickups_sunday

    try:
        stops = _build_route_stops(locations, leave_time)
        pickups_raw = json.loads(fetch_tool.invoke({}))
        if not pickups_raw.get("success") or not pickups_raw.get("data"):
            raise ValueError("Pickups API returned no data")
    except Exception:
        return json.dumps({"route": route, "rider_count": 0, "route_with_riders": None})

    # Flatten location_name -> people across all housing groups
    loc_to_people: dict[str, list[dict]] = {}
    for group in pickups_raw["data"]["housing_groups"].values():
        for loc_name, people in group["locations"].items():
            loc_to_people.setdefault(loc_name, []).extend(people)

    # Match stops to people via keyword matching (DB stores raw strings like "seventh")
    total = 0
    stops_with_people = []
    for stop in stops:
        people = _people_for_stop(stop["location"], loc_to_people)
        total += len(people)
        stops_with_people.append({**stop, "people": people})

    # Always build riders_by_stop so the LLM can present or filter it
    riders_by_stop = {
        stop["location"]: [
            {"name": p["name"], "discord_username": p["discord_username"]} for p in stop["people"]
        ]
        for stop in stops_with_people
        if stop["people"]
    }

    route_with_riders: str | None = None
    if total <= 4:
        route_with_riders = _format_route_with_riders(stops_with_people)

    return json.dumps(
        {
            "route": route,
            "rider_count": total,
            "riders_by_stop": riders_by_stop,
            "route_with_riders": route_with_riders,
        }
    )


_ROLE_ENDPOINTS: dict[str, str] = {
    "driver": f"{BACKEND_URL}/api/drivers",
    "ride coordinator": f"{BACKEND_URL}/api/ride-coordinators",
}


def _fuzzy_resolve_member(query: str, members: list[dict]) -> tuple[dict | None, str | None]:
    """
    Fuzzy-match query against a list of members (each with discord_username + display_name).
    Returns (matched_member, error_message). Exactly one of them will be None.
    """

    def _score(member: dict) -> float:
        username = member["discord_username"].lower()
        display = member["display_name"].lower()
        return max(
            SequenceMatcher(None, query, username).ratio(),
            SequenceMatcher(None, query, display).ratio(),
        )

    exact = [
        m
        for m in members
        if m["discord_username"].lower() == query or m["display_name"].lower() == query
    ]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        names = ", ".join(f"@{m['discord_username']} ({m['display_name']})" for m in exact)
        return None, f"Multiple exact matches: {names}. Please specify which one."

    scored = sorted(((m, _score(m)) for m in members), key=lambda x: x[1], reverse=True)
    candidates = [(m, s) for m, s in scored if s >= 0.6]
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0][0], None
    names = ", ".join(f"@{m['discord_username']} ({m['display_name']})" for m, _ in candidates)
    return None, f"Multiple possible matches: {names}. Which one did you mean?"


@tool
def add_role(role: str, discord_username: str) -> str:
    """
    Add the Driver or Ride Coordinator role to a Discord member.

    Args:
        role: The role to assign — either 'driver' or 'ride coordinator'.
        discord_username: The Discord username of the member to add the role to.

    Returns:
        JSON string with the updated member info, or an error message.
    """
    logger.info(f"Tool: add_role role={role!r} discord_username={discord_username!r}")
    endpoint = _ROLE_ENDPOINTS.get(role.lower())
    if endpoint is None:
        return f"Unknown role {role!r}. Must be 'driver' or 'ride coordinator'."

    query = discord_username.strip().lower().lstrip("@")

    # Search non-role members to resolve the username via fuzzy match
    search_response = httpx.get(
        f"{endpoint}/search",
        params={"q": query},
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    search_response.raise_for_status()
    candidates: list[dict] = (search_response.json() or {}).get("members", [])

    resolved, err = _fuzzy_resolve_member(query, candidates)
    if err:
        return err
    if resolved is None:
        return f"No member matching '{discord_username}' found (they may already have the {role} role)."

    response = httpx.post(
        endpoint,
        json={"discord_username": resolved["discord_username"]},
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    if response.status_code == 400:
        return f"Error: {response.json().get('detail', response.text)}"
    response.raise_for_status()
    member = response.json()
    return f"Successfully added the {role} role to @{member['discord_username']} ({member['display_name']})."


@tool
def remove_role(role: str, discord_username: str) -> str:
    """
    Remove the Driver or Ride Coordinator role from a Discord member.

    Args:
        role: The role to remove — either 'driver' or 'ride coordinator'.
        discord_username: The Discord username of the member to remove the role from.

    Returns:
        A confirmation message, or an error message if the member was not found.
    """
    logger.info(f"Tool: remove_role role={role!r} discord_username={discord_username!r}")
    endpoint = _ROLE_ENDPOINTS.get(role.lower())
    if endpoint is None:
        return f"Unknown role {role!r}. Must be 'driver' or 'ride coordinator'."

    list_response = httpx.get(endpoint, headers=_INTERNAL_HEADERS, timeout=10.0)
    list_response.raise_for_status()
    members: list[dict] = (list_response.json() or {}).get("members", [])

    query = discord_username.strip().lower().lstrip("@")
    target, err = _fuzzy_resolve_member(query, members)
    if err:
        return err
    if target is None:
        return f"No member matching '{discord_username}' found in the {role} role."

    del_response = httpx.delete(
        f"{endpoint}/{target['discord_user_id']}",
        headers=_INTERNAL_HEADERS,
        timeout=10.0,
    )
    if del_response.status_code == 400:
        return f"Error: {del_response.json().get('detail', del_response.text)}"
    del_response.raise_for_status()
    return f"Successfully removed the {role} role from @{target['discord_username']} ({target['display_name']})."


TOOLS = [
    make_route,
    make_route_with_riders,
    list_pickups_sunday,
    list_pickups_friday,
    pickup_location,
    map_links,
    add_role,
    remove_role,
]
TOOL_MAP = {t.name: t for t in TOOLS}

# Tools that return raw output directly without LLM reformatting
RAW_OUTPUT_TOOLS = {"make_route"}

llm_with_tools = llm.bind_tools(TOOLS)

# --- Agent loop ------------------------------------------------------------


def run_agent(user_message: str, history: list) -> tuple[str, list]:
    """Run one conversational turn. Returns (reply, updated_history)."""
    history.append(HumanMessage(content=user_message))

    while True:
        response = llm_with_tools.invoke([SystemMessage(content=SYSTEM_PROMPT), *history])
        history.append(response)

        if not response.tool_calls:
            return str(response.content), history

        for call in response.tool_calls:
            fn_name = call["name"]
            args = call["args"]

            tool_fn = TOOL_MAP.get(fn_name)
            if tool_fn is None:
                result = f"Unknown tool: {fn_name}"
            else:
                try:
                    result = tool_fn.invoke(args)
                except Exception as e:
                    result = f"Error: {e}"

            history.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

            if fn_name in RAW_OUTPUT_TOOLS:
                return str(result), history


# --- Entry point -----------------------------------------------------------

if __name__ == "__main__":
    print("Ridebot agent ready. Type 'quit' to exit.\n")  # noqa: T201
    history = []
    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() in {"quit", "exit"}:
            break
        answer, history = run_agent(user_input, history)
        print(f"Bot: {answer}\n")  # noqa: T201
