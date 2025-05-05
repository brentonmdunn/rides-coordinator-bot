from typing import List, Dict, Tuple
from itertools import combinations, permutations
import heapq

from form_groups3_copy import (
    assign_groups_export,
    rebalance_groups_export,
    assign_groups,
)


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
    travel_times: Dict[Tuple[str, str], int],
    graph,
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
                                    travel_times[(perm[i], perm[i + 1])]
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
            if len(chosen) < best["num"] or (
                len(chosen) == best["num"] and time_sum < best["time"]
            ):
                best.update(routes=list(chosen), num=len(chosen), time=time_sum)
            return

        uc = next(c for c in colleges if c not in covered)
        for subset, vidx, t, order in feasible:
            if uc in subset and subset.isdisjoint(covered) and vidx not in used_vids:
                chosen.append((subset, vidx, t, order))
                used_vids.add(vidx)
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
    for subset, vidx, _, order in best["routes"]:
        result[vidx] = order

    return result


# --- Example test harness ---
if __name__ == "__main__":
    graph = {
        "Muir": [("Sixth", 2)],
        "Sixth": [("Muir", 2), ("ERC", 3)],
        "ERC": [("Sixth", 3)],
        "Seventh": [("ERC", 2), ("Warren", 5), ("Innovation", 5)],
        "Warren": [("Seventh", 5), ("Rita", 110), ("Innovation", 1)],
        "Rita": [("Warren", 110), ("Innovation", 110)],
        "Innovation": [("Warren", 1), ("Rita", 110), ("Seventh", 5)],
    }

    travel_times = compute_all_pairwise_shortest_paths(graph)

    test_cases = [
        # ([4, 2, 4], {"Muir": 1, "Sixth": 1, "ERC": 1}),
        # ([4, 2, 4], {"Muir": 3, "Sixth": 2, "ERC": 4}),
        # ([4, 4, 4], {"Muir": 1, "ERC": 1, "Seventh": 1, "Warren": 1}),
        # ([4, 4, 4], {"Muir": 4, "Sixth": 4, "ERC": 2}),
        ([4, 4, 4], {"Seventh": 1, "Muir": 1, "Rita": 2, "Warren": 3}),
        # ([4, 4, 4], {"Seventh": 3, "Muir": 1, "Warren": 3}),
        # ([4, 4], {"Seventh": 3, "Muir": 2, "Warren": 3}),
        # ([4, 4], {"Warren": 1, "Innovation": 1, "Rita": 1, "Muir": 2, "Seventh": 2}),
    ]

    for idx, (capacities, demands) in enumerate(test_cases, 1):
        print(f"\n--- Test Case {idx} ---")
        try:
            routes = create_driver_routes(capacities, demands, travel_times, graph)
            print(routes)
            for vid in sorted(routes):
                route = routes[vid]
                load = sum(demands[c] for c in route)
                drive = (
                    0
                    if len(route) == 1
                    else sum(
                        travel_times[(route[i], route[i + 1])]
                        for i in range(len(route) - 1)
                    )
                )
                print(
                    f" Driver {vid}: cap={capacities[vid]}, load={load}, "
                    f"drive_time={drive} → {route}"
                )
        except ValueError as e:
            ret = rebalance_groups_export(assign_groups(capacities, graph, demands))
            print(ret)
            counter = 0
            for car in ret.values():
                num = 0
                route = []

                for colleges, num_ppl in car.items():
                    num += num_ppl
                    route.append(colleges)

                travel_time = 0
                for i in range(len(route) - 1):
                    travel_time += travel_times[(route[i], route[i + 1])]
                print(
                    f"Driver {counter}: cap={capacities[i]}, load={num}, drive_time={travel_time} → {route}"
                )
                counter += 1
            # print(f" No feasible assignment: {e}")
