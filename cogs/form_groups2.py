def make_groups(group_sizes, graph, population):
    pass


group_sizes = [2, 4, 4]
graph = {
    "Muir": [("Sixth", 2)],
    "Sixth": [("Muir", 2), ("ERC", 3)],
    "ERC": [("Sixth", 3)],
}
population = {"Muir": 4, "Sixth": 2, "ERC": 3}

print(make_groups(group_sizes, graph, population))
