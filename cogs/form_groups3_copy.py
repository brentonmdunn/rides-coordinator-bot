import heapq
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Set

Location = str
Graph = Dict[Location, List[Tuple[Location, int]]]
Population = Dict[Location, int]
GroupSizeList = List[int]
Group = Dict[Location, int]


def compute_all_pairs_shortest_paths(
    graph: Graph,
) -> Dict[Tuple[Location, Location], int]:
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


def assign_groups(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[Tuple[int, Group]]:
    # print(group_sizes)
    # print(graph)
    # print(population)

    if sum(population.values()) > sum(group_sizes):
        raise ValueError("Too many people for available spots.")

    pop = population.copy()
    group_sizes.sort(reverse=True)
    result = []

    for size in group_sizes:
        best_group = None
        best_group_size = 0
        best_cost = float("inf")

        for start in [loc for loc in pop if pop[loc] > 0]:
            group = find_group(start, size, pop, graph)
            group_size = sum(group.values())
            if group_size > 0:
                group_locations = set(group.keys())
                cost = mst_cost(group_locations, graph)

                # Prefer larger group size, then lower cost
                if (group_size > best_group_size) or (
                    group_size == best_group_size and cost < best_cost
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


def assign_groups_export(
    group_sizes: GroupSizeList, graph: Graph, population: Population
) -> List[Tuple[int, Group]]:
    if sum(population.values()) > sum(group_sizes):
        raise ValueError("Too many people for available spots.")

    pop = population.copy()
    group_sizes.sort(reverse=True)
    result = []

    for size in group_sizes:
        best_group = None
        best_group_size = 0
        best_cost = float("inf")

        for start in [loc for loc in pop if pop[loc] > 0]:
            group = find_group(start, size, pop, graph)
            group_size = sum(group.values())
            if group_size > 0:
                group_locations = set(group.keys())
                cost = mst_cost(group_locations, graph)

                # Prefer larger group size, then lower cost
                if (group_size > best_group_size) or (
                    group_size == best_group_size and cost < best_cost
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

    print(f"<><><><><><>{result}")
    return result


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


def rebalance_groups_export(
    grouping: List[Tuple[int, Group]],
) -> List[Tuple[int, Group]]:
    """Grouping is pass by reference"""
    # print(f"====\n{grouping}\n====")

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

    # print(f"====\n{grouping}\n====")

    ret = {}
    for i, (_, val) in enumerate(grouping):
        ret[i] = val

    # print(f"====\n{ret}\n====")
    return ret
    print(f"3 grouping: {grouping}")

    return grouping


def print_groups(groups):
    print("11 Originally created group:")
    for i, g in enumerate(groups):
        print(f"Group {i + 1}: {g}")
    print("==============================")
    print("Rebalance:")
    rebalance_groups(groups)
    for i, g in enumerate(groups):
        print(f"Group {i + 1}: {g}")


if __name__ == "__main__":
    group_sizes = [3, 4, 4, 4]
    # group_sizes = [4, 2, 4]
    graph = {
        "Muir": [("Sixth", 2)],
        "Sixth": [("Muir", 2), ("ERC", 3)],
        "ERC": [("Sixth", 3)],
        "Seventh": [("ERC", 2), ("Warren", 50), ("Innovation", 50)],
        "Warren": [("Seventh", 50), ("Rita", 100), ("Innovation", 1)],
        "Rita": [("Warren", 100), ("Innovation", 95)],
        "Innovation": [("Warren", 1), ("Rita", 95), ("Seventh", 50)],
    }
    population = {"Muir": 4, "Sixth": 2, "ERC": 3, "Seventh": 1}
    # population = {"Muir": 1, "Sixth": 1, "ERC": 1}
    # population = {"Muir": 3, "Sixth": 2, "ERC": 4}
    # population = {"Muir": 4, "Sixth": 4, "ERC": 2}
    # population = {"Muir": 2,"ERC": 2}
    # population = {"Seventh": 2,"Muir": 2, "Rita": 1, "Warren": 2}
    # population = {"Seventh": 1,"Muir": 1, "Rita": 2, "Warren": 3}
    # population = {"Warren": 5, "Seventh": 1, "ERC": 2, "Muir": 1, "Sixth": 2, "Rita": 2}

    # testcase = ([4, 2, 4], {"Muir": 1, "Sixth": 1, "ERC": 1})
    # testcase = ([4, 2, 4], {"Muir": 3, "Sixth": 2, "ERC": 4})
    # testcase = ([4, 4, 4], {"Muir": 1, "ERC": 1, "Seventh": 1, "Warren": 1})
    # testcase = ([4, 4, 4], {"Muir": 4, "Sixth": 4, "ERC": 2})
    testcase = (
        [4, 4, 4],
        {
            "Rita": 2,
            "Warren": 3,
            "Seventh": 1,
            "Muir": 1,
        },
    )
    # testcase = ([4, 4, 4], {"Seventh": 3,"Muir": 1, "Warren": 3})
    # testcase = ([4, 4], {"Seventh": 3, "Muir": 2, "Warren": 3})
    # testcase = ([4, 4], {"Warren": 1, "Innovation": 1, "Rita": 1, "Muir": 2, "Seventh": 2})

    groups = assign_groups(testcase[0], graph, testcase[1])
    print_groups(groups)
