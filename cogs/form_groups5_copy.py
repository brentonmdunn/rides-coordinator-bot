import heapq
from collections import defaultdict
from itertools import permutations
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


def assign_groups_global_min_cost(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[Tuple[int, Group]]:
    if sum(population.values()) > sum(group_sizes):
        raise ValueError("Too many people for available spots.")

    group_sizes = sorted(group_sizes, reverse=True)
    best_assignment = None
    min_total_cost = float("inf")

    # Try permutations of group sizes to explore different group fill orders
    for size_perm in permutations(group_sizes):
        pop_copy = population.copy()
        result = []
        total_cost = 0

        for size in size_perm:
            best_group = None
            best_cost = float("inf")
            for start in [loc for loc in pop_copy if pop_copy[loc] > 0]:
                group = find_group(start, size, pop_copy, graph)
                if not group:
                    continue
                group_locations = set(group.keys())
                cost = mst_cost(group_locations, graph)
                if sum(group.values()) > 0 and cost < best_cost:
                    best_group = group
                    best_cost = cost

            if best_group:
                for loc, count in best_group.items():
                    pop_copy[loc] -= count
                result.append((size, dict(best_group)))
                total_cost += best_cost
            else:
                result.append((size, {}))

        if (
            sum(sum(g.values()) for _, g in result) == sum(population.values())
            and total_cost < min_total_cost
        ):
            best_assignment = result
            min_total_cost = total_cost

    if best_assignment is None:
        raise ValueError("No valid assignment found that includes all people.")

    return best_assignment


def print_groups(groups):
    print("Group assignments:")
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

testcase = ([4, 4], {"Warren": 1, "Innovation": 1, "Rita": 1, "Muir": 2, "Seventh": 2})

groups = assign_groups_global_min_cost(testcase[0], graph, testcase[1])
print_groups(groups)
