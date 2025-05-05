import heapq
from collections import defaultdict
from typing import Dict, List, Tuple, Set

Location = str
Graph = Dict[Location, List[Tuple[Location, int]]]
Population = Dict[Location, int]
GroupSizeList = List[int]
Group = Dict[Location, int]


def find_group(start: Location, needed: int, pop: Population, graph: Graph) -> Group:
    visited = set()
    group = defaultdict(int)
    total_collected = 0
    heap = [(0, start)]

    while heap and total_collected < needed:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        available = pop.get(u, 0)
        if available > 0:
            take = min(needed - total_collected, available)
            group[u] += take
            total_collected += take
        for v, w in graph.get(u, []):
            if v not in visited:
                heapq.heappush(heap, (d + w, v))
    return group


def mst_cost(locations: Set[Location], graph: Graph) -> int:
    if len(locations) <= 1:
        return 0
    visited = set()
    start = next(iter(locations))
    heap = []
    for neighbor, weight in graph.get(start, []):
        if neighbor in locations:
            heapq.heappush(heap, (weight, start, neighbor))
    visited.add(start)
    total_cost = 0
    while heap and len(visited) < len(locations):
        weight, u, v = heapq.heappop(heap)
        if v in visited:
            continue
        visited.add(v)
        total_cost += weight
        for neighbor, w in graph.get(v, []):
            if neighbor in locations and neighbor not in visited:
                heapq.heappush(heap, (w, v, neighbor))
    return total_cost if len(visited) == len(locations) else float("inf")


def assign_groups_with_condensing(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[Tuple[int, Group]]:
    if sum(population.values()) > sum(group_sizes):
        raise ValueError("Too many people for available spots.")
    pop = population.copy()
    group_sizes = sorted(group_sizes, reverse=True)
    result = []
    max_allowed_cost = 70
    for size in group_sizes:
        best_group = None
        best_group_size = 0
        best_cost = float("inf")
        candidates = [loc for loc in pop if pop[loc] > 0]
        for start in candidates:
            group = find_group(start, size, pop, graph)
            group_size = sum(group.values())
            if group_size > 0:
                group_locations = set(group.keys())
                cost = mst_cost(group_locations, graph)
                if (group_size == size and cost < best_cost) or (
                    group_size < size
                    and cost <= max_allowed_cost
                    and group_size > best_group_size
                ):
                    best_group = group
                    best_group_size = group_size
                    best_cost = cost
        if best_group:
            for loc, count in best_group.items():
                pop[loc] -= count
            result.append((size, dict(best_group)))
        else:
            result.append((size, {}))
    return result


def rebalance_groups(grouping: List[Tuple[int, Group]]) -> List[Tuple[int, Group]]:
    """Grouping is pass by reference"""

    colleges_mentioned = set()
    split_colleges = set()
    split_colleges_details = defaultdict(list)

    for _, riders in grouping:
        for college, _ in riders.items():
            if college in colleges_mentioned:
                split_colleges.add(college)
            else:
                colleges_mentioned.add(college)

    for idx, (num_spots, riders) in enumerate(grouping):
        for college, num_people in riders.items():
            if college in split_colleges:
                split_colleges_details[college].append(
                    {
                        "open spots": num_spots - sum(riders.values()),
                        "num people": num_people,
                        "group idx": idx,
                    }
                )

    for college, details in split_colleges_details.items():
        max_open_spots = 0
        total_from_college = 0
        # can_move = False
        max_idx = 0
        for car in details:
            if max_open_spots < car["open spots"] + car["num people"]:
                max_open_spots = car["open spots"] + car["num people"]
                max_idx = car["group idx"]
            total_from_college += car["num people"]

        if total_from_college <= max_open_spots:
            # can_move = True

            for idx, (_, riders) in enumerate(grouping):
                if college in riders and idx != max_idx:
                    del riders[college]
                elif college in riders and idx == max_idx:
                    riders[college] = total_from_college
    # print(f"3 grouping: {grouping}")


def print_groups(groups):
    print("Originally created group:")
    for i, g in enumerate(groups):
        print(f"Group {i + 1}: {g}")
    print("==============================")
    print("Rebalance:")
    rebalance_groups(groups)
    for i, g in enumerate(groups):
        print(f"Group {i + 1}: {g}")


# Example usage
graph = {
    "Muir": [("Sixth", 2)],
    "Sixth": [("Muir", 2), ("ERC", 3)],
    "ERC": [("Sixth", 3)],
    "Seventh": [("ERC", 2), ("Warren", 50), ("Innovation", 50)],
    "Warren": [("Seventh", 50), ("Rita", 100), ("Innovation", 1)],
    "Rita": [("Warren", 100), ("Innovation", 95)],
    "Innovation": [("Warren", 1), ("Rita", 95), ("Seventh", 50)],
}


# testcase = ([4, 2, 4], {"Muir": 1, "Sixth": 1, "ERC": 1})
# testcase = ([4, 2, 4], {"Muir": 3, "Sixth": 2, "ERC": 4})
# testcase = ([4, 4, 4], {"Muir": 1, "ERC": 1, "Seventh": 1, "Warren": 1})
# testcase = ([4, 4, 4], {"Muir": 4, "Sixth": 4, "ERC": 2})
# testcase = ([4, 4, 4], {"Seventh": 1,"Muir": 1, "Rita": 2, "Warren": 3})
testcase = ([4, 4], {"Warren": 1, "Innovation": 1, "Rita": 1, "Muir": 2, "Seventh": 2})

# Run and print result
groups = assign_groups_with_condensing(testcase[0], graph, testcase[1])
print_groups(groups)
