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
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.services.route_service import RouteService  # noqa: E402

# --- LLM -------------------------------------------------------------------

llm = ChatOpenAI(
    model="api-gpt-oss-120b",
    base_url="https://tritonai-api.ucsd.edu/v1",
    api_key=os.environ["TRITON_API_KEY"],
)

BACKEND_URL = "http://localhost:8000"

SYSTEM_PROMPT = """You are a ride coordinator assistant for a UCSD college fellowship.
You help plan pickup routes for drivers and list who needs rides.

When a user asks you to make a route, call the make_route tool.
When a user asks who needs a ride on Sunday, call the list_pickups_sunday tool.

Valid location tokens for make_route (case-insensitive, fuzzy matching supported):
  SEVENTH, ERC, MARSHALL, SIXTH, MUIR, WARREN_EQL, WARREN_JST,
  RITA, INNOVATION, EIGHTH, PANGEA, VILLAS_OF_RENAISSANCE,
  GEISEL_LOOP, PCYN_LOOP

For list_pickups_sunday, format the result as a clean readable summary grouped by
housing area, showing each person's name and pickup location."""

# --- Tools -----------------------------------------------------------------

@tool
def make_route(locations: str, leave_time: str) -> str:
    """Build a pickup route with staggered departure times for each stop.

    Args:
        locations: Space-separated pickup location tokens in pickup order (e.g. 'revelle muir eighth').
        leave_time: Departure time from the final stop (e.g. '5:30pm').

    Returns:
        Formatted string with pickup times and Google Maps links.
    """
    return RouteService.make_route(locations, leave_time)


@tool
def list_pickups_sunday() -> str:
    """Fetch who needs a ride on Sunday, grouped by housing area.

    Returns:
        JSON string with housing groups and the people in each group.
    """
    response = httpx.post(
        f"{BACKEND_URL}/api/list-pickups",
        json={"ride_type": "sunday"},
        timeout=10.0,
    )
    response.raise_for_status()
    return json.dumps(response.json(), indent=2)


TOOLS = [make_route, list_pickups_sunday]
TOOL_MAP = {t.name: t for t in TOOLS}

# Tools that return raw output directly without LLM reformatting
RAW_OUTPUT_TOOLS = {"make_route"}

llm_with_tools = llm.bind_tools(TOOLS)

# --- Agent loop ------------------------------------------------------------

def run_agent(user_message: str, history: list) -> tuple[str, list]:
    """Run one conversational turn. Returns (reply, updated_history)."""
    history.append(HumanMessage(content=user_message))

    while True:
        response = llm_with_tools.invoke(
            [SystemMessage(content=SYSTEM_PROMPT)] + history
        )
        history.append(response)

        if not response.tool_calls:
            return response.content, history

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
    print("Ridebot agent ready. Type 'quit' to exit.\n")
    history = []
    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() in {"quit", "exit"}:
            break
        answer, history = run_agent(user_input, history)
        print(f"Bot: {answer}\n")
