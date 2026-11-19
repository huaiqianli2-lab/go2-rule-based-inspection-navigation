"""Verify an offline replan after adding an obstacle to a synthetic grid."""
import json

from .grid_simulation import blocked_cells, shortest_leg


SIZE = (32, 20)
START, GOAL = (3, 10), (28, 10)
STATIC = ((8, 2, 11, 6), (7, 15, 10, 18), (21, 4, 24, 7), (21, 14, 24, 17))
OBSTACLE = (13, 9, 15, 11)
CHANGE_INDEX = 6


def clearance_cells(rectangles):
    """Expand each obstacle by one cell in both grid dimensions."""
    return blocked_cells(
        (x0 - 1, y0 - 1, x1 + 1, y1 + 1) for x0, y0, x1, y1 in rectangles
    )


def plan_replan():
    """Return the original plan and the route followed after replanning."""
    initial = shortest_leg(START, GOAL, SIZE, clearance_cells(STATIC))
    blocked = clearance_cells((*STATIC, OBSTACLE))
    replan_cell = initial[CHANGE_INDEX]
    if not blocked.intersection(initial[CHANGE_INDEX + 1:]):
        raise RuntimeError("The inserted obstacle must obstruct the remaining route")

    replacement = shortest_leg(replan_cell, GOAL, SIZE, blocked)
    route = initial[:CHANGE_INDEX] + replacement
    if blocked.intersection(replacement) or route[-1] != GOAL:
        raise RuntimeError("The revised plan failed its clearance or goal check")

    return {
        "initial_route_steps": len(initial) - 1,
        "replanned_mission_steps": len(route) - 1,
        "initial_route": initial,
        "replayed_route": route,
        "obstacle": OBSTACLE,
        "replan_cell": replan_cell,
    }


if __name__ == "__main__":
    print(json.dumps(plan_replan(), indent=2))
