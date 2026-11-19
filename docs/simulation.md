# Archived A* developer examples

These independent fixtures ship with the historical releases. The original inspection system uses Dijkstra for graph search. See the [field system notes](system.md).

## Obstacle replanning in 3D

This synthetic 32 × 20 grid starts with four rectangular obstacles. A four-connected A* search uses a one-cell margin around each obstacle. After the robot reaches cell (9, 10), a scripted event adds an obstacle that overlaps the original path. The planner checks that the replacement avoids the expanded obstacles and reaches the goal.

| Route | Grid steps |
| --- | ---: |
| Initial plan | 25 |
| Executed prefix and replacement together | 31 |

```bash
python3 -m examples.obstacle_replan > replan.json
```

The computation runs offline and emits both paths, the obstacle bounds, and the replanning cell. The video was rendered in MuJoCo 3.10.0 using the [Unitree Go2 model from MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/370c43965323c0944b433b202aac5058b5f907a9/unitree_go2). See the [upstream model license](https://github.com/google-deepmind/mujoco_menagerie/blob/370c43965323c0944b433b202aac5058b5f907a9/unitree_go2/LICENSE). The render sets the model pose along the route at each frame. It has zero physics integration steps and uses a scripted obstacle event in place of sensor detection.

[Full 1600 × 900 MP4](https://github.com/walmfml88886666/go2-rule-based-inspection/releases/download/v0.3.0/obstacle-replan-mujoco.mp4) · [High-resolution still](../assets/obstacle-replan-poster.jpg)

## Round-trip inspections in 2D

The public example isolates one aspect of rule-based inspection: routing between known observation stops while respecting blocked areas. The two synthetic layouts use rectangular obstacles and a 28 × 16 grid. A four-connected A* search with a Manhattan heuristic computes each leg. The stop order is fixed, and the last leg returns to the initial cell. The simulation demonstrates geometry and visit progression; it does not test the field planner or any physical robot.

[![Full-resolution simulation frame](../assets/simulation-poster.png)](../assets/simulation-poster.png)

| Scene | Checkpoints visited | Path length | Final state |
| --- | ---: | ---: | --- |
| Indoor | 5 / 5 | 76 grid steps | Returned to start |
| Outdoor | 5 / 5 | 82 grid steps | Returned to start |

```bash
python3 -m examples.grid_simulation indoor > indoor-route.json
python3 -m examples.grid_simulation outdoor > outdoor-route.json
```

Each JSON result contains the obstacles, ordered stops, arrival indices, and the complete cell-by-cell route. The program checks obstacle clearance, adjacency, stop order, and return to start before returning the result. A grid step is one cell transition, with no physical unit or speed assigned.

[Download the 720p simulation](https://github.com/walmfml88886666/go2-rule-based-inspection/releases/download/v0.2.0/grid-simulation.mp4) · [Back to the README](../README.md)
