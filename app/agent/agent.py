# ruff: noqa

#  from langchain_google_genai import GoogleGenerativeAI
# from langgraph.graph import START, END, StateGraph
# from langgraph.prebuilt import ToolNode, tools_condition
# from typing import TypedDict, Annotated, List

# locations_matrix = {
#     "Muir": [("Sixth", 2)],
#     "Sixth": [("Muir", 2), ("ERC", 3)],
#     "ERC": [("Sixth", 3), ("Seventh", 2)], # Assuming ERC to Seventh is 2
#     "Seventh": [("ERC", 2), ("Warren", 5), ("Innovation", 5)],
#     "Warren": [("Seventh", 5), ("Rita", 10), ("Innovation", 1)],
#     "Rita": [("Warren", 10), ("Innovation", 10)],
#     "Innovation": [("Warren", 1), ("Rita", 10), ("Seventh", 5)],
# }


# import heapq

# def find_shortest_path(location1: str, location2: str, locations_matrix: dict) -> tuple[int, list[str]]:
#     """
#     Gets the time it takes to drive between `location1` and `location2` using Dijkstra's algorithm.
#     Assume `location1` and `location2` are in `locations_matrix`.

#     Args:
#         location1 (str): The starting location.
#         location2 (str): The destination location.
#         locations_matrix (dict): A dictionary representing the graph of locations and travel times.

#     Returns:
#         tuple(int, list[str]): A tuple containing the shortest time (integer) to get
#         from `location1` to `location2` and a list of the locations passed through (including start and end).
#         Returns (float('inf'), []) if no path is found.
#     """
#     # Priority queue to store (time, current_location)
#     # We use a min-heap to always explore the path with the shortest time so far.
#     priority_queue = [(0, location1)]

#     # Dictionary to store the shortest time from location1 to every other location
#     # We initialize all times to infinity.
#     times = {location: float('inf') for location in locations_matrix}
#     times[location1] = 0

#     # Dictionary to store the predecessor of each location in the shortest path.
#     # This is crucial for reconstructing the final path.
#     previous_locations = {location: None for location in locations_matrix}

#     while priority_queue:
#         # Get the location with the smallest time from the priority queue
#         current_time, current_location = heapq.heappop(priority_queue)

#         # If we have already found a shorter path to this location, skip it.
#         if current_time > times[current_location]:
#             continue

#         # If we've reached the destination, we can reconstruct the path and return.
#         if current_location == location2:
#             break

#         # Explore neighbors of the current location
#         for neighbor, time_to_neighbor in locations_matrix.get(current_location, []):
#             new_time = current_time + time_to_neighbor

#             # If we found a shorter path to the neighbor, update it.
#             if new_time < times[neighbor]:
#                 times[neighbor] = new_time
#                 previous_locations[neighbor] = current_location
#                 heapq.heappush(priority_queue, (new_time, neighbor))

#     # --- Path Reconstruction ---
#     # If we couldn't reach location2, its time will still be infinity.
#     if times[location2] == float('inf'):
#         return float('inf'), []

#     path = []
#     step = location2
#     # Work backwards from the destination to the start using the predecessors map
#     while step is not None:
#         path.append(step)
#         step = previous_locations[step]

#     # The path is constructed backwards, so we reverse it.
#     path.reverse()

#     return times[location2], path

# llm = GoogleGenerativeAI()
# llm_with_tools = llm.bind_tools([find_shortest_path])


# def AgentState(TypedDict):
#     drivers: list[str]

#     pickups: list[str]

# def tool_calling_llm(state: AgentState):
#     return llm_with_tools(state)


import heapq
import json
import operator
import os
from typing import Annotated, Dict, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

# --- 1. Set up your Google API Key ---
# Make sure to set your GOOGLE_API_KEY environment variable
# For example:
# os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY"

# --- 2. Define the Tool for Pathfinding ---
# This is your Dijkstra's algorithm implementation, now decorated as a LangChain tool.

locations_matrix = {
    "Muir": [("Sixth", 2)],
    "Sixth": [("Muir", 2), ("ERC", 3)],
    "ERC": [("Sixth", 3), ("Seventh", 2)],
    "Seventh": [("ERC", 2), ("Warren", 5), ("Innovation", 5)],
    "Warren": [("Seventh", 5), ("Rita", 10), ("Innovation", 1)],
    "Rita": [("Warren", 10), ("Innovation", 10)],
    "Innovation": [("Warren", 1), ("Rita", 10), ("Seventh", 5)],
}


@tool
def find_shortest_path(location1: str, location2: str) -> str:
    """
    Finds the shortest driving time and path between two locations. The driver's starting point
    is considered to be the first pickup location in their route.

    Args:
        location1 (str): The starting location (e.g., 'Muir', 'Warren').
        location2 (str): The destination location (e.g., 'Rita', 'ERC').

    Returns:
        str: A string describing the shortest time and the path.
             For example: "The shortest time from Muir to ERC is 5 minutes, via the path: ['Muir', 'Sixth', 'ERC']".
             Returns an error message if a location is not found or no path exists.
    """
    # Validate that locations exist in the matrix
    if location1 not in locations_matrix or location2 not in locations_matrix:
        return f"Error: One or both locations ('{location1}', '{location2}') are not recognized. Valid locations are: {list(locations_matrix.keys())}"

    # Priority queue to store (time, current_location, path_list)
    priority_queue = [(0, location1, [location1])]

    # Dictionary to store the shortest time to each location to avoid redundant paths
    visited_times = {location: float("inf") for location in locations_matrix}
    visited_times[location1] = 0

    while priority_queue:
        current_time, current_location, path = heapq.heappop(priority_queue)

        # If we reached the destination, we are done
        if current_location == location2:
            return f"The shortest time from {location1} to {location2} is {current_time} minutes, via the path: {path}"

        # If we have found a longer path to this node already, skip
        if current_time > visited_times[current_location]:
            continue

        # Explore neighbors
        for neighbor, time_to_neighbor in locations_matrix.get(current_location, []):
            new_time = current_time + time_to_neighbor

            # If we found a shorter path to the neighbor, update it and push to queue
            if new_time < visited_times[neighbor]:
                visited_times[neighbor] = new_time
                new_path = path + [neighbor]
                heapq.heappush(priority_queue, (new_time, neighbor, new_path))

    return f"No path found from {location1} to {location2}."


# --- 3. Define the Agent's State ---
# This class represents the data that will be passed between nodes in our graph.
class AgentState(TypedDict):
    # A list to store the conversation history. `operator.add` makes sure new messages are appended.
    messages: Annotated[list, operator.add]
    # A dictionary mapping driver names to their capacity (max number of people they can transport)
    drivers: Dict[str, int]
    # A dictionary mapping pickup locations to the number of people needing a ride.
    pickups: Dict[str, int]


# --- 4. Define the Graph Nodes ---
# These are the functions that will do the work in our graph.


def agent_node(state: AgentState, llm, tools):
    """
    The primary node that calls the LLM. It decides whether to call a tool or respond to the user.
    """
    # On the first turn, we construct a detailed prompt from the initial state
    if len(state["messages"]) == 0:
        # Format drivers and their capacities for the prompt
        drivers_str = "\n".join(
            [f"- {name}: capacity of {cap} people" for name, cap in state["drivers"].items()]
        )
        pickups_str = "\n".join([f"- {loc}: {num} people" for loc, num in state["pickups"].items()])

        prompt = f"""
You are an expert logistics coordinator for a delivery service. Your job is to create the most efficient routes for your drivers to handle a list of pickups.

Your objectives are, in order of priority:
1. Ensure all pickups are assigned.
2. Do not exceed any driver's capacity. The capacity is the total number of PEOPLE a driver can transport.
3. Minimize the total driving time across all drivers.
4. Use the minimum number of drivers required.

Here is the current situation:

<pickups_to_be_made>
{pickups_str}
</pickups_to_be_made>

<available_drivers_and_capacities>
{drivers_str}
</available_drivers_and_capacities>

<instructions>
1.  First, use the `find_shortest_path` tool to calculate the travel time between ALL pairs of pickup locations. This will form a complete distance matrix.
2.  Analyze the distances, driver capacities, and the number of people at each pickup location.
3.  Create routes for the drivers. A route is an ordered sequence of pickup locations for a single driver.
4.  The total number of people from all locations in a single driver's route cannot exceed that driver's capacity.
5.  The travel time for a single driver's route is the sum of the travel times between consecutive pickups in their assigned sequence. The starting point of a route is the first pickup location (no travel time to get there).
6.  Your final answer should be ONLY the assignment in a single JSON object. The keys should be driver names, and the values should be a list of the pickup locations they are assigned to visit (in order).
</instructions>

Example of a final answer:
{{
  "DriverA": ["Rita", "ERC"],
  "DriverB": ["Innovation"]
}}
"""
        # Add the constructed prompt as the first message
        messages = [HumanMessage(content=prompt)]
    else:
        # On subsequent turns, just use the existing message history
        messages = state["messages"]

    # Invoke the LLM with the messages and available tools
    llm_with_tools = llm.bind(tools=tools)
    response = llm_with_tools.invoke(messages)

    # Return the LLM's response to be added to the state
    return {"messages": [response]}


# The tool node is pre-built in LangGraph.
tool_node = ToolNode([find_shortest_path])


# --- 5. Define Conditional Logic for Edges ---
# This function decides which node to go to next.
def should_continue(state: AgentState):
    """
    Determines the next step. If the LLM made a tool call, we go to the tool node.
    Otherwise, we end the graph execution.
    """
    last_message = state["messages"][-1]
    # If the last message has tool calls, we route to the 'tools' node
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    # Otherwise, we're done.
    return END


# --- 6. Construct and Compile the Graph ---
def main():
    """
    Main function to set up and run the LangGraph agent.
    """
    # Check for API key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("🔴 Error: GOOGLE_API_KEY environment variable not set.")
        print("Please set your API key to run the agent.")
        return

    print("🔵 Setting up the agent...")
    llm = GoogleGenerativeAI(model="gemini-2.0-flash")
    tools = [find_shortest_path]

    # Create the state graph
    workflow = StateGraph(AgentState)

    # Add the nodes to the graph
    # The `agent_node` needs access to the llm and tools, so we pass them in using a lambda
    workflow.add_node("agent", lambda state: agent_node(state, llm, tools))
    workflow.add_node("tools", tool_node)

    # Set the entry point of the graph
    workflow.set_entry_point("agent")

    # Add the conditional edge. After the 'agent' node, it will check `should_continue`.
    # If it returns "tools", it goes to the 'tools' node. If it returns END, it finishes.
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})

    # Add a normal edge from the 'tools' node back to the 'agent' node.
    # This creates the loop: Agent -> Tools -> Agent
    workflow.add_edge("tools", "agent")

    # Compile the graph into a runnable application
    app = workflow.compile()
    print("✅ Agent setup complete. Ready to run.")

    # --- 7. Run the Agent ---
    # Define the initial problem for the agent to solve
    initial_drivers = {"DriverA": 4, "DriverB": 2}
    initial_pickups = {"Rita": 1, "ERC": 2, "Innovation": 2, "Muir": 1}

    # The input to the app is a dictionary that matches the AgentState structure
    inputs = {
        "drivers": initial_drivers,
        "pickups": initial_pickups,
        "messages": [],  # Start with an empty message history
    }

    print("\n🚀 Invoking agent with the following task:")
    print(f"   Drivers & Capacities: {initial_drivers}")
    print(f"   Pickups & # of People: {initial_pickups}")
    print("\n...Agent is thinking and using tools...\n")

    # The invoke method runs the graph until it reaches an END state
    final_state = app.invoke(inputs)

    # The final answer from the LLM is in the last message
    final_answer_str = final_state["messages"][-1]

    print(final_state)

    print("--- AGENT'S FINAL PLAN ---")
    try:
        # Pretty-print the JSON output
        final_json = json.loads(final_answer_str)
        print(json.dumps(final_json, indent=2))
    except (json.JSONDecodeError, TypeError):
        # If the output isn't valid JSON, print it as is
        print(final_answer_str)
    print("--------------------------")


if __name__ == "__main__":
    main()
