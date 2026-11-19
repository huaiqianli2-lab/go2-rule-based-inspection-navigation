"""Plan and verify a synthetic, offline indoor or outdoor inspection route."""
import argparse
from heapq import heappop, heappush
import json


SCENES = {
    "indoor": {
        "size": (28, 16), "start": (2, 13),
        "obstacles": ((7, 2, 8, 11), (13, 4, 21, 5), (16, 9, 18, 13), (23, 8, 25, 10)),
        "stops": ((4, 2), (12, 3), (24, 4), (25, 13), (12, 12)),
    },
    "outdoor": {
        "size": (28, 16), "start": (2, 13),
        "obstacles": ((6, 3, 11, 8), (16, 2, 21, 6), (20, 10, 24, 13), (9, 10, 12, 12)),
        "stops": ((4, 2), (13, 6), (24, 2), (26, 12), (16, 13)),
    },
}


def blocked_cells(rectangles):
    return {
        (x, y)
        for x0, y0, x1, y1 in rectangles
        for x in range(x0, x1 + 1)
        for y in range(y0, y1 + 1)
    }


def shortest_leg(start, goal, size, blocked):
    """Find a shortest four-connected path with a Manhattan heuristic."""
    width, height = size

    def heuristic(cell):
        return abs(goal[0] - cell[0]) + abs(goal[1] - cell[1])

    if any(not (0 <= x < width and 0 <= y < height) or (x, y) in blocked
           for x, y in (start, goal)):
        raise ValueError("Start or goal is blocked or outside the grid")

    queue = [(heuristic(start), 0, start)]
    parent = {start: None}
    best = {start: 0}
    while queue:
        _, distance, cell = heappop(queue)
        if distance != best[cell]:
            continue
        if cell == goal:
            path = []
            while cell is not None:
                path.append(cell)
                cell = parent[cell]
            return path[::-1]

        x, y = cell
        for neighbor in ((x + 1, y), (x, y - 1), (x - 1, y), (x, y + 1)):
            nx, ny = neighbor
            if not (0 <= nx < width and 0 <= ny < height) or neighbor in blocked:
                continue
            next_distance = distance + 1
            if next_distance < best.get(neighbor, float("inf")):
                best[neighbor] = next_distance
                parent[neighbor] = cell
                heappush(queue, (next_distance + heuristic(neighbor), next_distance, neighbor))

    raise ValueError(f"No collision-free path from {start} to {goal}")


def plan_scene(scene):
    settings = SCENES[scene]
    start, stops, size = (settings[k] for k in ("start", "stops", "size"))
    blocked = blocked_cells(settings["obstacles"])
    route = [start]
    arrivals = []
    for destination in (*stops, start):
        route.extend(shortest_leg(route[-1], destination, size, blocked)[1:])
        arrivals.append(len(route) - 1)
    if (route[0] != route[-1] or any(c in blocked for c in route)
            or [route[i] for i in arrivals[:-1]] != list(stops)
            or any(abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1 for a, b in zip(route, route[1:]))):
        raise RuntimeError("Route failed the inspection checks")
    return {
        "scene": scene,
        "grid_size": size,
        "start": start,
        "obstacle_rectangles": settings["obstacles"],
        "inspection_stops": stops,
        "arrival_indices": arrivals[:-1],
        "route": route,
        "grid_steps": len(route) - 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", choices=SCENES)
    args = parser.parse_args()
    print(json.dumps(plan_scene(args.scene), indent=2))


if __name__ == "__main__":
    main()
