"""
cogs/form_groups.py
"""

from collections import defaultdict
from enum import StrEnum
from datetime import datetime, timedelta
import heapq
from itertools import combinations, permutations
from typing import Dict, List, Tuple, Set


class Housing(StrEnum):
    SIXTH = "Sixth"
    SEVENTH = "Seventh"
    EIGHTH = "Eighth"
    MUIR = "Muir"
    REVELLE = "Revelle"
    MARSHALL = "Marshall"
    ERC = "ERC"
    WARREN = "Warren"
    PCYN_W = "Peppercanyon West"
    PCYN_E = "Peppercanyon East"
    RITA = "Rita"


Location = str
Graph = Dict[Location, List[Tuple[Location, int]]]
Population = Dict[Location, int]
GroupSizeList = List[int]
Group = Dict[Location, int]

TIME_THRESH = 11
LATEST_ARRIVAL = datetime.strptime("19:10", "%H:%M")  # 7:10 PM
PREFERENCE_ORDER = ["Seventh", "Warren", Housing.PCYN_E, "ERC", "Sixth", "Muir", "Rita"]


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


def compute_all_pairwise_shortest_paths(
    graph: Dict[str, List[Tuple[str, int]]],
) -> Dict[Tuple[str, str], int]:
    # Dijkstra for each node
    def dijkstra(source: str) -> Dict[str, int]:
        dist = {source: 0}
        heap = [(0, source)]
        while heap:
            cost, node = heapq.heappop(heap)
            if cost > dist[node]:
                continue
            for neighbor, weight in graph.get(node, []):
                new_cost = cost + weight
                if neighbor not in dist or new_cost < dist[neighbor]:
                    dist[neighbor] = new_cost
                    heapq.heappush(heap, (new_cost, neighbor))
        return dist

    all_pairs = {}
    for node in graph:
        dists = dijkstra(node)
        for other, cost in dists.items():
            all_pairs[(node, other)] = cost
    return all_pairs


def create_driver_routes(
    capacities: List[int],
    college_demands: Dict[str, int],
    edge_weights: Dict[Tuple[str, str], int],
    graph,
    driver_preferences: Dict[int, set] = None,  # driver_id -> set of preferred colleges
) -> Dict[int, List[str]]:
    colleges = list(college_demands.keys())
    N = len(colleges)
    ALL = set(colleges)

    # print(college_demands)
    # print("::::::::::::::")

    # 1) Precompute all feasible (subset, vehicle, best_time, best_order)
    feasible = []
    for r in range(1, N + 1):
        for subset in combinations(colleges, r):
            dem = sum(college_demands[c] for c in subset)
            for vidx, cap in enumerate(capacities):
                if dem <= cap:
                    if r == 1:
                        best_time = 0
                        best_order = [subset[0]]
                    else:
                        best_time = float("inf")
                        best_order = None
                        for perm in permutations(subset):
                            try:
                                t = sum(
                                    edge_weights[(perm[i], perm[i + 1])]
                                    for i in range(r - 1)
                                )
                            except KeyError:
                                continue  # skip incomplete paths
                            if t < best_time:
                                best_time = t
                                best_order = list(perm)
                    if best_order is not None:
                        feasible.append((set(subset), vidx, best_time, best_order))

    # 2) Backtrack to cover ALL without reusing vehicles
    best = {"routes": None, "num": float("inf"), "time": float("inf")}

    def backtrack(
        covered: set,
        used_vids: set,
        chosen: List[Tuple[set, int, int, List[str]]],
        time_sum: int,
    ):
        if len(chosen) > best["num"]:
            return
        if len(chosen) == best["num"] and time_sum >= best["time"]:
            return
        if covered == ALL:
            # Enforce: driver must have visited preferred location
            if driver_preferences:
                for vidx, required_stops in driver_preferences.items():
                    # Find what this driver covered
                    assigned_subset = next(
                        (subset for subset, v, _, _ in chosen if v == vidx), None
                    )
                    if assigned_subset is None or not (
                        assigned_subset & required_stops
                    ):
                        return  # skip this complete assignment — it doesn't meet requirement

            if len(chosen) < best["num"] or (
                len(chosen) == best["num"] and time_sum < best["time"]
            ):
                best.update(routes=list(chosen), num=len(chosen), time=time_sum)
            return

        uc = next(c for c in colleges if c not in covered)
        sorted_feasible = sorted(
            feasible,
            key=lambda f: (
                0
                if driver_preferences
                and f[1] in driver_preferences
                and f[0] & driver_preferences[f[1]]
                else 1,
                f[2],  # secondary: prefer lower travel time
            ),
        )

        for subset, vidx, t, order in sorted_feasible:
            if subset.isdisjoint(covered) and vidx not in used_vids:
                # Option 1: Assign whole group normally
                chosen.append((subset, vidx, t, order))
                used_vids.add(vidx)

                # If over time limit and we have spare vehicles, try splitting
                if t > TIME_THRESH and len(used_vids) < len(capacities):
                    # Try breaking this subset into 2 disjoint feasible subgroups
                    for r in range(1, len(subset)):
                        for part1 in combinations(subset, r):
                            part1 = set(part1)
                            part2 = subset - part1
                            if not part1 or not part2:
                                continue
                            for v1 in set(range(len(capacities))) - used_vids:
                                for v2 in (
                                    set(range(len(capacities))) - used_vids - {v1}
                                ):
                                    opt1 = [
                                        f
                                        for f in feasible
                                        if f[0] == part1 and f[1] == v1
                                    ]
                                    opt2 = [
                                        f
                                        for f in feasible
                                        if f[0] == part2 and f[1] == v2
                                    ]
                                    if opt1 and opt2:
                                        f1 = opt1[0]
                                        f2 = opt2[0]
                                        if (
                                            f1[2] + f2[2] < t
                                        ):  # Only split if combined cost is better
                                            chosen[-1] = f1
                                            chosen.append(f2)
                                            used_vids.add(v1)
                                            used_vids.add(v2)
                                            backtrack(
                                                covered | subset,
                                                used_vids,
                                                chosen,
                                                time_sum - t + f1[2] + f2[2],
                                            )
                                            used_vids.remove(v1)
                                            used_vids.remove(v2)
                                            chosen.pop()
                                            chosen[-1] = (
                                                subset,
                                                vidx,
                                                t,
                                                order,
                                            )  # restore original

                else:
                    backtrack(covered | subset, used_vids, chosen, time_sum + t)

                used_vids.remove(vidx)
                chosen.pop()

    backtrack(set(), set(), [], 0)

    if best["routes"] is None:
        # ret = rebalance_groups_export(assign_groups(capacities, graph, college_demands))
        # print(ret)
        # return ret
        raise ValueError("No feasible assignment found")

    result: Dict[int, List[str]] = {}
    for subset, vidx, _, order in best["routes"]:  # pylint: disable=not-an-iterable
        result[vidx] = order

    return result


def maybe_reverse_route(route: List[str], preference_order: List[str]) -> List[str]:
    if len(route) <= 1:
        return route
    preference_map = {name: idx for idx, name in enumerate(preference_order)}
    start_rank = preference_map.get(route[0], float("inf"))
    end_rank = preference_map.get(route[-1], float("inf"))
    return list(reversed(route)) if start_rank < end_rank else route
    # return route


def compute_pickup_times(
    route: List[str], edge_weights: Dict[Tuple[str, str], int], latest_arrival: datetime
) -> List[Tuple[str, str]]:
    OVERHEAD_MINUTES = 1
    times = [(route[-1], latest_arrival.strftime("%I:%M %p"))]
    curr_time = latest_arrival

    for i in range(len(route) - 2, -1, -1):
        u, v = route[i], route[i + 1]
        travel = edge_weights.get((u, v)) or edge_weights.get((v, u))
        if travel is None:
            raise ValueError(f"No travel time between {u} and {v}")
        curr_time -= timedelta(minutes=(travel + OVERHEAD_MINUTES))
        times.append((u, curr_time.strftime("%I:%M %p")))

    return list(reversed(times))


# --- Example test harness ---
if __name__ == "__main__":
    pickup_location = {
        Housing.MUIR: "Scholars ln",
        Housing.SIXTH: "Sixth loop",
        Housing.ERC: "Pangea",
        Housing.SEVENTH: "Seventh",
        Housing.WARREN: "Equality",
        Housing.RITA: "Rita",
        Housing.MARSHALL: "Pangea",
        Housing.PCYN_E: "Innovation ln",
    }

    graph = {
        Housing.MUIR: [(Housing.SIXTH, 2)],
        Housing.SIXTH: [(Housing.MUIR, 2), (Housing.ERC, 2)],
        Housing.ERC: [(Housing.SIXTH, 2)],
        Housing.SEVENTH: [(Housing.ERC, 2), (Housing.WARREN, 15), (Housing.PCYN_E, 16)],
        Housing.WARREN: [
            (Housing.SEVENTH, 15),
            (Housing.RITA, 110),
            (Housing.PCYN_E, 3),
        ],
        Housing.RITA: [(Housing.WARREN, 110), (Housing.PCYN_E, 110)],
        Housing.PCYN_E: [
            (Housing.WARREN, 3),
            (Housing.RITA, 110),
            (Housing.SEVENTH, 16),
        ],
    }

    actual_time = {
        Housing.MUIR: [(Housing.SIXTH, 1)],
        Housing.SIXTH: [(Housing.MUIR, 1), (Housing.ERC, 2)],
        Housing.ERC: [(Housing.SIXTH, 2), (Housing.SEVENTH, 1)],
        Housing.SEVENTH: [(Housing.ERC, 1), (Housing.WARREN, 5), (Housing.PCYN_E, 5)],
        Housing.WARREN: [(Housing.SEVENTH, 5), (Housing.RITA, 9), (Housing.PCYN_E, 2)],
        Housing.RITA: [(Housing.WARREN, 9), (Housing.PCYN_E, 7)],
        Housing.PCYN_E: [(Housing.WARREN, 2), (Housing.RITA, 7), (Housing.SEVENTH, 5)],
    }

    edge_weights = compute_all_pairwise_shortest_paths(graph)
    time_to_travel = compute_all_pairwise_shortest_paths(actual_time)

    test_cases = [
        ([4, 2, 4], {"Muir": 1, "Sixth": 1, "ERC": 1}, None),
        ([4, 2, 4], {"Muir": 3, "Sixth": 2, "ERC": 4}, None),
        ([4, 4, 4], {"Muir": 1, "ERC": 1, "Seventh": 1, "Warren": 1}, None),
        ([4, 4, 4], {"Muir": 4, "Sixth": 4, "ERC": 2}, None),
        ([4, 4, 4], {"Seventh": 3, "Muir": 1, "Warren": 3}, None),
        ([4, 4], {"Seventh": 3, "Muir": 2, "Warren": 3}, None),
        (
            [4, 4],
            {"Warren": 1, Housing.PCYN_E.value: 1, "Rita": 1, "Muir": 2, "Seventh": 2},
            None,
        ),
        (
            [4, 4],
            {"Muir": 2, "Seventh": 2, "Rita": 1, Housing.PCYN_E.value: 1, "Warren": 1},
            None,
        ),
        # ([4, 4, 4, 4], {"Muir": 1, "Sixth": 2, "Rita": 2, Housing.PCYN_E: 1, "Seventh": 1, "ERC": 2, "Warren": 4},None),
        # ([3, 4], {Housing.PCYN_E: 1, "Rita": 2, "Warren": 2, "Seventh": 1, "Muir": 1}, {
        #     0: {"Warren", Housing.PCYN_E}
        # }),
        # ([4, 4, 4, 3, 3], {"ERC": 3, "Muir": 3, "Sixth": 2, Housing.PCYN_E: 1, "Warren": 3, "Seventh": 3, "Rita": 1}, {3: {"Seventh"}, 4: {"Warren", Housing.PCYN_E}}),
        # ([4, 3, 4, 3], {"Muir": 4, Housing.PCYN_E: 1, "Warren": 1, "Rita": 1, "ERC": 2, "Sixth": 2, "Seventh": 1}, {1: {Housing.PCYN_E}, 3: {"Seventh"}}),
        ([4, 4], {"Peppercanyon East": 1, "Seventh": 1, "ERC": 1, "Muir": 1}, {}),
        ([4, 4, 4], {"Seventh": 1, "Muir": 1, "Rita": 2, "Warren": 3}, None),
    ]

    for idx, (capacities, demands, pref) in enumerate(test_cases, 1):
        print(f"\n--- Test Case {idx} ---")
        try:
            routes = create_driver_routes(
                capacities, demands, edge_weights, graph, pref
            )
            # print(routes)
            for vid in sorted(routes):
                route = maybe_reverse_route(routes[vid], PREFERENCE_ORDER)
                load = sum(demands[c] for c in route)
                drive = (
                    0
                    if len(route) == 1
                    else sum(
                        time_to_travel.get((route[i], route[i + 1]))
                        or time_to_travel.get((route[i + 1], route[i]))
                        for i in range(len(route) - 1)
                    )
                )
                print(
                    f" Driver {vid}: capacity={capacities[vid]}, load={load}, drive_time={drive} → {route}"
                )

                pickup_times = compute_pickup_times(
                    route, time_to_travel, LATEST_ARRIVAL
                )
                for loc, time_str in pickup_times:
                    print(f"  - Pickup {loc} at {time_str}")
        except ValueError as e:
            ret = rebalance_groups_export(assign_groups(capacities, graph, demands))
            # print(ret)
            counter = 0
            for car in ret.values():
                num = 0
                route = []

                for colleges, num_ppl in car.items():
                    num += num_ppl
                    route.append(colleges)

                travel_time = 0
                for i in range(len(route) - 1):
                    travel_time += time_to_travel[(route[i], route[i + 1])]
                route = maybe_reverse_route(route, PREFERENCE_ORDER)
                print(
                    f"Driver {counter}: capacity={capacities[i]}, load={num}, drive_time={travel_time} → {route}"
                )
                pickup_times = compute_pickup_times(
                    route, time_to_travel, LATEST_ARRIVAL
                )
                for loc, time_str in pickup_times:
                    print(f"  - Pickup {loc} at {time_str}")
                counter += 1
            # print(f" No feasible assignment: {e}")
