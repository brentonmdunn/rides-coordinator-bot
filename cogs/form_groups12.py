import itertools
import heapq
from collections import defaultdict, deque
from typing import Dict, List, Tuple

# Types for clarity
Location = str
Graph = Dict[Location, List[Tuple[Location, int]]]
Population = Dict[Location, int]
GroupSizeList = List[int]


def dijkstra(graph: Graph, start: Location) -> Dict[Location, int]:
    """Returns shortest distances from `start` to all other nodes."""
    dist = {node: float("inf") for node in graph}
    dist[start] = 0
    heap = [(0, start)]

    while heap:
        curr_dist, u = heapq.heappop(heap)
        if curr_dist > dist[u]:
            continue
        for v, weight in graph[u]:
            if dist[v] > curr_dist + weight:
                dist[v] = curr_dist + weight
                heapq.heappush(heap, (dist[v], v))

    return dist


def get_all_pair_distances(graph: Graph) -> Dict[Location, Dict[Location, int]]:
    """Precompute all-pairs shortest paths using Dijkstra."""
    return {node: dijkstra(graph, node) for node in graph}


def connected_subgraphs(graph: Graph, population: Population, max_people: int):
    """Generate all connected subgraphs with up to `max_people` people."""
    visited = set()
    result = []

    for start in graph:
        queue = deque()
        queue.append(([start], set([start]), population[start]))

        while queue:
            nodes, seen, count = queue.popleft()
            if count > max_people:
                continue
            result.append((nodes.copy(), count))
            for node in nodes:
                for neighbor, _ in graph[node]:
                    if neighbor not in seen:
                        new_seen = seen | {neighbor}
                        queue.append(
                            (nodes + [neighbor], new_seen, count + population[neighbor])
                        )
    return result


def total_internal_distance(
    group: List[Location], distances: Dict[Location, Dict[Location, int]]
) -> int:
    """Sum of shortest distances between all nodes in the group."""
    return sum(distances[a][b] for i, a in enumerate(group) for b in group[i + 1 :])


def form_groups(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[List[Tuple[Location, int]]]:
    all_distances = get_all_pair_distances(graph)
    remaining_population = population.copy()
    result = []

    for group_size in group_sizes:
        candidates = connected_subgraphs(graph, remaining_population, group_size)
        best_group = None
        best_cost = float("inf")

        for nodes, total_people in candidates:
            if total_people < group_size:
                continue
            # Try all ways to allocate exact number of people from these nodes
            allocations = []

            def dfs(idx, acc, left, alloc):
                if left == 0:
                    allocations.append(list(alloc))
                    return
                if idx == len(nodes) or left < 0:
                    return
                node = nodes[idx]
                max_here = min(left, remaining_population[node])
                for i in range(max_here + 1):
                    alloc.append((node, i))
                    dfs(idx + 1, acc + i, left - i, alloc)
                    alloc.pop()

            dfs(0, 0, group_size, [])

            for alloc in allocations:
                used_nodes = [loc for loc, amt in alloc if amt > 0]
                if not used_nodes:
                    continue
                cost = total_internal_distance(used_nodes, all_distances)
                if cost < best_cost:
                    best_cost = cost
                    best_group = alloc

        if not best_group:
            raise ValueError(f"Unable to form group of size {group_size}")

        for loc, amt in best_group:
            remaining_population[loc] -= amt
        result.append([(loc, amt) for loc, amt in best_group if amt > 0])

    return result


def form_groups_flexible(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[List[Tuple[Location, int]]]:
    all_distances = get_all_pair_distances(graph)
    remaining_population = population.copy()
    result = []

    for group_cap in group_sizes:
        candidates = connected_subgraphs(graph, remaining_population, group_cap)
        best_group = None
        best_cost = float("inf")

        for nodes, total_people in candidates:
            if total_people == 0:
                continue
            max_group_size = min(group_cap, total_people)

            # Try all combinations of people from these nodes totaling up to max_group_size
            allocations = []

            def dfs(idx, left, alloc):
                if left == 0:
                    allocations.append(list(alloc))
                    return
                if idx == len(nodes) or left < 0:
                    return
                node = nodes[idx]
                max_here = min(left, remaining_population[node])
                for i in range(max_here + 1):
                    alloc.append((node, i))
                    dfs(idx + 1, left - i, alloc)
                    alloc.pop()

            dfs(0, max_group_size, [])

            for alloc in allocations:
                used_nodes = [loc for loc, amt in alloc if amt > 0]
                if not used_nodes:
                    continue
                cost = total_internal_distance(used_nodes, all_distances)
                if cost < best_cost:
                    best_cost = cost
                    best_group = alloc

        if not best_group:
            raise ValueError(f"Unable to form group of size ≤ {group_cap}")

        for loc, amt in best_group:
            remaining_population[loc] -= amt
        result.append([(loc, amt) for loc, amt in best_group if amt > 0])

    return result


# group_sizes = [2, 4, 4]
# graph = {
#     "Alpha": [("Bravo", 2), ("Charlie", 1), ("Delta", 10)],
#     "Bravo": [("Alpha", 2), ("Charlie", 5)],
#     "Charlie": [("Alpha", 1), ("Bravo", 5)],
#     "Delta": [("Alpha", 10)]
# }
# population = {"Alpha": 2, "Bravo": 1, "Charlie": 4, "Delta": 1}

# groups = form_groups_flexible(group_sizes, graph, population)
# print(groups)


def form_groups_min_distance_and_full_coverage(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[List[Tuple[Location, int]]]:
    all_distances = get_all_pair_distances(graph)
    remaining_population = population.copy()
    result = []

    # Sort group sizes from largest to smallest
    group_sizes_remaining = sorted(group_sizes, reverse=True)

    # Track unassigned people
    unassigned_locations = {loc for loc, count in population.items() if count > 0}

    for group_cap in group_sizes_remaining:
        best_group = None
        best_cost = float("inf")

        # Step 1: Prefer single-location group
        for loc in unassigned_locations:
            if remaining_population[loc] >= group_cap:
                best_group = [(loc, group_cap)]
                best_cost = 0
                break

        # Step 2: Try multi-location groups minimizing distance, include unassigned locations
        if not best_group:
            candidates = connected_subgraphs(graph, remaining_population, group_cap)

            for nodes, total_people_in_nodes in candidates:
                if total_people_in_nodes < 1:
                    continue
                max_group_size = min(group_cap, total_people_in_nodes)
                allocations = []

                def dfs(idx, left, alloc):
                    if left == 0:
                        allocations.append(list(alloc))
                        return
                    if idx == len(nodes) or left < 0:
                        return
                    node = nodes[idx]
                    max_here = min(left, remaining_population[node])
                    for i in range(max_here + 1):
                        alloc.append((node, i))
                        dfs(idx + 1, left - i, alloc)
                        alloc.pop()

                dfs(0, max_group_size, [])

                for alloc in allocations:
                    used_nodes = [loc for loc, amt in alloc if amt > 0]
                    if not used_nodes:
                        continue
                    covers_unassigned = any(
                        loc in unassigned_locations for loc, amt in alloc if amt > 0
                    )
                    internal_cost = total_internal_distance(used_nodes, all_distances)

                    # Strongly prefer using unassigned locations
                    cost = internal_cost - (1000 if covers_unassigned else 0)

                    if cost < best_cost:
                        best_cost = cost
                        best_group = alloc

        if not best_group:
            raise ValueError(f"Unable to form group of size ≤ {group_cap}")

        for loc, amt in best_group:
            remaining_population[loc] -= amt
            if remaining_population[loc] == 0:
                unassigned_locations.discard(loc)
        result.append([(loc, amt) for loc, amt in best_group if amt > 0])

    return result


# Run improved function
group_sizes = [2, 4, 4]
graph = {
    "Alpha": [("Bravo", 2), ("Charlie", 1), ("Delta", 10)],
    "Bravo": [("Alpha", 2), ("Charlie", 5)],
    "Charlie": [("Alpha", 1), ("Bravo", 5)],
    "Delta": [("Alpha", 10)],
}
population = {"Alpha": 2, "Bravo": 1, "Charlie": 4, "Delta": 1}

groups = form_groups_min_distance_and_full_coverage(group_sizes, graph, population)
print(groups)
