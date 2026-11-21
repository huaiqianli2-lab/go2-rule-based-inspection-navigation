# XT16 mapping adaptation and planning layers

The field system uses the ROS 2 Humble port of [LIO-SAM](https://github.com/TixiaoShan/LIO-SAM). The project's XT16 configuration adapts the sensor-to-body transform and roll/pitch fusion to the mounted Go2 system.

## Matched indoor mapping comparison

Both runs processed the first 1,040 s of the same indoor LiDAR and IMU recording, using the same executable. The input rotation and the IMU roll/pitch fusion weight changed together. The white line in the figure is the archived SLAM trajectory projected along the same horizontal axis in both panels. Surface returns are colored by map Z using one palette and the same limits. The plot exaggerates the vertical axis by 4×.

| Configuration | IMU vector rotation | Roll/pitch weight | Keyframes | Estimated trajectory Z span |
| --- | --- | ---: | ---: | ---: |
| Baseline | Identity | 0.01 | 1,162 | 5.966 m |
| Calibrated | −90° about Z | 0.15 | 1,145 | 0.891 m |

The Z span is the difference between the maximum and minimum estimated trajectory elevations. It summarizes this paired run. Absolute height error would require an independent reference. The two changed settings were not separately ablated. [Measured values and source digests](data/mapping-calibration-ab.json)

## Planner implementation

The delivered indoor and outdoor `inspection_planner.py` compute a local ground surface on a 0.15 m XY grid. For a populated cell within 3.0 m of the nearest mapping pose, the algorithm subtracts the 0.485 m LiDAR mount height from that pose and allows elevation change up to a 25° slope plus 0.16 m step and 0.05 m noise margins. It then takes the 15th percentile of returns below that ceiling. Cells with no surviving returns use the trajectory ground estimate within the supported radius. Cells beyond the radius use the uncapped percentile, and empty cells are unknown at the estimator stage.

The navigation mask counts returns within (0.16, 0.6296) m above the estimated ground. The upper limit is the sum of the 0.485 m mount height, 0.0296 m offset to the LiDAR cap, and 0.115 m clearance margin. The visibility mask counts returns within (0.90, 2.20) m. Each raw mask activates at two returns. The navigation layer can be inflated for footprint clearance; the view layer supports ray sampling from an observation pose towards a target and stops short of the target itself. These are planning rules for the project's geometry model.

## Observation-pose selection

The 3D [principle diagram](../assets/navigation-sight-layers-f929e23d0b15.png) separates two operations: classifying a grid cell by height-band return counts, and screening possible observation positions around an annotated target. Its A/B/C positions and obstacle geometry are illustrative, not measurements or an exhaustive planner trace.

The checked original `observation_point` implementation prefers positions from the recorded mapping trajectory. It screens target distance, the XY line-of-sight mask and camera elevation, scoring accepted positions by their distance from the desired observation range. Three stages widen the search: the preferred distance band with the standard sight test; a wider distance band with a shorter target exclusion margin; then a stage that can omit the sight test. A trajectory position is not rechecked with `is_free` in this branch.

If no trajectory candidate is accepted, grid-ring and spiral fallbacks check the inflated navigation obstacle mask with `is_free`, the visibility mask along the XY ray, and camera elevation against half the vertical field of view. The sight sampler excludes the final segment next to the target (normally 0.5 m, or 0.35 m in the relevant fallback). This is a height-band occupancy heuristic, not a 3D optical ray tracer. If all searches fail, the planner returns an invalid fallback pose for review.

Thus the navigation layer influences grid-based stance clearance and the visibility layer influences target-facing sight checks, alongside distance, local ground height, camera limits and candidate source. Passing a count test alone does not prove physical reachability or image visibility. The diagram places Go2 meshes on the ground at candidate base poses, with ground arrows for yaw and upward camera-to-target lines for elevation. Front-camera anchors are illustrative, not calibrated; the 3D lines explain orientation while the implemented sight check remains a height-band XY-mask test. The diagram's accepted C represents a successful illustrative case; it does not imply that every recorded pose passed both masks without relaxation.

The route uses Dijkstra graph distances for waypoint legs and applies visit-order and observation checks separately. [System workflow](system.md)
