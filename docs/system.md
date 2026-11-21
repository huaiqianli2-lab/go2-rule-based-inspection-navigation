# System notes

Go2 Patrol organizes the field inspection workflow around a source map and its mission. LiDAR and IMU recordings feed the 3D mapping pipeline. Operators annotate targets on the resulting point cloud. The desktop software generates observation poses, visit order, waypoints, and matching navigation layers. The robot checks the bundle before a supervised run, then returns trajectories, target images, and event logs. The original planning code uses Dijkstra for graph distances and path reconstruction. Observation pose checks, visit ordering and onboard execution are separate parts of the workflow.

| Layer | Components | Responsibility |
| --- | --- | --- |
| Sensing | Hesai XT16, IMU, Go2 front camera | Geometry, inertial data, and inspection imagery |
| Desktop orchestration | Python GUI and command dispatcher | Acquisition, mapping, annotation, planning, sync, review |
| Mapping | ROS 2, Hesai driver, LIO-SAM | LiDAR and inertial recordings to point-cloud maps |
| Planning | Separate indoor/outdoor entry points | Reachability, geometry, elevation, camera visibility, and mission consistency |
| Robot execution | Go2 EDU, onboard compute, platform motion interface | Preflight, localization, navigation, capture, and operator takeover |
| Reporting | Map, path, photos, logs | Traceable inspection evidence |

## Implementation map

These names describe the original field system. This repository publishes the two offline audit tools and standalone examples.

| Module | Role |
| --- | --- |
| `app/` | Desktop interface and orchestration |
| `semantic_annotator.py` | Target annotation |
| `planning_dispatch.py` | Indoor/outdoor planner selection |
| `planning_indoor/`, `planning_outdoor/` | Scenario-specific planning and checks |
| `map_navigation.py`, `inspection_planner.py` | Point-cloud geometry, observation poses, and route generation |
| `navigation_checks.py`, `height_checks.py` | Footprint, route, elevation, and turning checks |
| [`route_intersections.py`](../tools/route_intersections.py) | True XY crossings, including crossings split at vertices, and collinear retracing |
| [`visit_order_metrics.py`](../tools/visit_order_metrics.py) | Exhaustive audit for 1–8 fixed stops with directed leg costs |
| `inspection_bundle.py`, `acceptance_preflight.py` | Bundle consistency and preflight checks |
| `exp4_inspect.cpp` | Field navigation and image capture |

## Interpreting the examples

The [maps](gallery.md) visualize the stored route and target poses for two historical scenes. The field clips show separate inspection excerpts. Evaluating measured performance requires the original logs, software version, and evaluation conditions for the corresponding run. The [grid simulation](simulation.md) verifies synthetic routes against its own grid model.

The [SVG overview](../assets/architecture.svg) and [editable draw.io source](architecture.drawio) show the roles of the desktop and robot hardware. Solid edges show the mission flow. Dashed edges show onboard hardware services.

The [integrated overview](../assets/system-overview-451e88bbdc40.png) combines a dominant measured outdoor map with the planned route and observation stops, paired exterior and onboard field views, a compact [native draw.io workflow](inspection-workflow.drawio) and paired indoor/outdoor evidence panels. Field clips, scan maps and plans are separate evidence views; the composition does not assert synchronization. The [composition master](system-overview.drawio) embeds image panels and retains editable headings and figure labels. The native workflow master retains editable nodes and connected edges. The navigation mask feeds Dijkstra leg paths and, through a dashed edge, grid fallback candidate checks. Line of sight (LOS), range and camera elevation inform observation-pose selection. Visit ordering and return planning precede supervised navigation and target-image capture. The separate [planning-layer master](navigation-sight-principle.drawio) illustrates independent per-cell height bands and grounded candidate poses. [Selection details](mapping.md#observation-pose-selection) describe the checks and relaxed fallback stages.

[Back to the README](../README.md)
