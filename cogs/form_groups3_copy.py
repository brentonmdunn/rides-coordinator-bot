import heapq
from collections import defaultdict, deque
from typing import Dict, List, Tuple

Location = str
Graph = Dict[Location, List[Tuple[Location, int]]]
Population = Dict[Location, int]
GroupSizeList = List[int]
Group = Dict[Location, int]

def compute_all_pairs_shortest_paths(graph: Graph) -> Dict[Tuple[Location, Location], int]:
    def dijkstra(start):
        dist = {start: 0}
        heap = [(0, start)]
        while heap:
            d, u = heapq.heappop(heap)
            for v, w in graph.get(u, []):
                if v not in dist or dist[v] > d + w:
                    dist[v] = d + w
                    heapq.heappush(heap, (dist[v], v))
        return dist

    all_dist = {}
    for node in graph:
        dist = dijkstra(node)
        for other, d in dist.items():
            all_dist[(node, other)] = d
    return all_dist

def find_group(start: Location, needed: int, pop: Population, graph: Graph, dist_map: Dict[Tuple[str, str], int]) -> Tuple[Group, int]:
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

    total_dist = sum(dist_map[(start, node)] * count for node, count in group.items())
    return group, total_dist

# def assign_groups(group_sizes: GroupSizeList, graph: Graph, population: Population) -> List[Group]:
#     dist_map = compute_all_pairs_shortest_paths(graph)
#     pop = population.copy()
#     group_sizes.sort(reverse=True)
#     result = []

#     for size in group_sizes:
#         candidates = sorted([loc for loc in pop if pop[loc] > 0], key=lambda x: -pop[x])
#         best_group = None
#         best_cost = float('inf')

#         for start in candidates:
#             group, cost = find_group(start, size, pop, graph, dist_map)
#             if sum(group.values()) == size and cost < best_cost:
#                 best_group = group
#                 best_cost = cost

#         if best_group:
#             for loc, count in best_group.items():
#                 pop[loc] -= count
#             result.append(dict(best_group))
#         else:
#             # Not enough people or not possible—return empty group
#             result.append({})

#     return result


def assign_groups(group_sizes: GroupSizeList, graph: Graph, population: Population) -> List[Group]:
    dist_map = compute_all_pairs_shortest_paths(graph)
    pop = population.copy()
    group_sizes.sort(reverse=True)
    result = []

    for size in group_sizes:
        candidates = sorted([loc for loc in pop if pop[loc] > 0], key=lambda x: -pop[x])
        exact_match = None
        exact_cost = float('inf')
        best_partial = None
        best_people = 0
        best_partial_cost = float('inf')

        for start in candidates:
            group, cost = find_group(start, size, pop, graph, dist_map)
            total = sum(group.values())
            if total == size and cost < exact_cost:
                exact_match = group
                exact_cost = cost
            elif 0 < total < size:
                if total > best_people or (total == best_people and cost < best_partial_cost):
                    best_partial = group
                    best_people = total
                    best_partial_cost = cost

        chosen = exact_match if exact_match else best_partial

        if chosen:
            for loc, count in chosen.items():
                pop[loc] -= count
            result.append((size, dict(chosen)))
        else:
            result.append((size, {}))

    return result


group_sizes = [2, 4, 4]
graph = {
    "Muir": [("Sixth", 2)],
    "Sixth": [("Muir", 2), ("ERC", 3)],
    "ERC": [("Sixth", 3)],
    "Seventh": [("ERC", 2)],
}
# population = {"Muir": 4, "Sixth": 2, "ERC": 3, "Seventh": 1}
# population = {"Muir": 1, "Sixth": 1, "ERC": 1}
population = {"Muir": 4, "Sixth": 4, "ERC": 2}

groups = assign_groups(group_sizes, graph, population)
# print(groups)
for i, g in enumerate(groups):
    print(f"Group {i+1}: {g}")
