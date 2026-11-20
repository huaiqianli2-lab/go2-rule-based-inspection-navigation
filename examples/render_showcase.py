"""Render synchronized route and 3D views from the archived SLAM-map runs."""

import argparse
import json
import subprocess
from pathlib import Path
import mujoco as mj
import numpy as np
from PIL import Image, ImageDraw
from .render_slam import BG, WHITE, MINT, AMBER, font
from tools.point_cloud import HEIGHT_COLORS, map_view, read_xyz
from .slam_patrol import SCENES, build_model, ground, input_file, load_inputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--scene", choices=SCENES, required=True)
    p.add_argument("--robot-xml", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--ffmpeg", type=Path, required=True)
    p.add_argument("--preview", action="store_true")
    args = p.parse_args()
    task, terrain, _ = load_inputs(args.inputs, args.scene)
    summary = json.loads((args.run / "mission.json").read_text())
    states = np.load(args.run / "states.npz")
    times = states["times"]
    # These contiguous walking spans were chosen from the archived runs.
    start = {"indoor": 2.0, "outdoor": 110.0}[args.scene]
    spans = [(start, start + 11.0)]
    keep = np.flatnonzero((times >= spans[0][0]) & (times <= spans[0][1]))
    if args.preview:
        keep = keep[np.linspace(0, len(keep) - 1, min(6, len(keep))).astype(int)]
    model = build_model(args.inputs, args.scene, args.robot_xml)
    # MuJoCo expresses the near plane as a fraction of the scene extent.
    # The large outdoor map otherwise clips a close camera through the terrain.
    model.vis.map.znear = 0.04 / model.stat.extent
    data = mj.MjData(model)
    renderer = mj.Renderer(model, 584, 870, max_geom=100000)
    options = mj.MjvOption()
    options.geomgroup[3] = False
    options.sitegroup[:] = False
    # Use a semitransparent display for the measured voxel surface. Collisions
    # retain the original geometry and parameters in the separate simulation.
    for g in range(model.ngeom):
        if model.geom(g).name.startswith("obstacle_"):
            model.geom_rgba[g, 3] = 0.42
    cloud = read_xyz(input_file(args.inputs, SCENES[args.scene][-1]))
    # Freeze the map viewport for the whole clip. The position marker moves
    # across measured returns and the real goal remains on screen.
    qpos = states["qpos"]
    stop_counts = states["completed"]
    selected_stops = np.unique(stop_counts[keep])
    goals = np.array(
        [[task["stops"][j]["observe"][axis] for axis in "xy"] for j in selected_stops]
    )
    segment = np.vstack([qpos[keep, :2], goals])
    bounds = (segment.min(axis=0) - 3.5, segment.max(axis=0) + 3.5)
    limits = np.percentile(cloud[:, 2], [8, 94])
    rgb, project, scale = map_view(cloud, bounds, (620, 584), limits, point_radius=1)
    map_base = Image.fromarray(rgb)
    path = np.array(task["planned_path"])
    camera = mj.MjvCamera()
    camera.type = mj.mjtCamera.mjCAMERA_FREE
    # Drape the recorded base XY trace onto the simulated terrain.
    surface = {key: terrain[key] for key in ("origin", "resolution", "ground")}
    trace_start = max(0, keep[0] - 175)
    trace_xy = qpos[trace_start : keep[-1] + 1, :2]
    trace_xyz = np.column_stack(
        [trace_xy, [ground(surface, xy) + 0.045 for xy in trace_xy]]
    )
    mint = np.array([0.24, 0.96, 0.77, 1.0], dtype=np.float32)
    identity = np.eye(3).ravel()
    output = args.run / f"slam-{args.scene}-route.mp4"
    temporary = args.run / f"slam-{args.scene}.route.partial.mp4"
    command = [
        str(args.ffmpeg.resolve()),
        "-v",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        "1600x900",
        "-framerate",
        "25",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "3",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    proc = None if args.preview else subprocess.Popen(command, stdin=subprocess.PIPE)
    poster = keep[len(keep) // 2]
    for number, i in enumerate(keep):
        t = float(times[i])
        xy = qpos[i, :2]
        data.qpos[:] = qpos[i]
        mj.mj_forward(model, data)
        # Keep a fixed azimuth through turns. The low oblique camera shows
        # nearby obstacle heights and the robot's displacement across the terrain.
        camera.lookat[:] = data.qpos[:3] + [0.3, -0.15, 0.24]
        camera.distance = 4.0
        camera.azimuth = 215 if args.scene == "outdoor" else 210
        camera.elevation = -37
        renderer.update_scene(data, camera=camera, scene_option=options)
        scene = renderer.scene
        recent = list(range(max(0, i - 175), i, 5)) + [i]
        for previous, current in zip(recent, recent[1:]):
            start_xyz, end_xyz = trace_xyz[np.array([previous, current]) - trace_start]
            if np.linalg.norm(end_xyz - start_xyz) < 0.015:
                continue
            geom = scene.geoms[scene.ngeom]
            mj.mjv_initGeom(geom, mj.mjtGeom.mjGEOM_CAPSULE, np.zeros(3), np.zeros(3), identity, mint)
            mj.mjv_connector(geom, mj.mjtGeom.mjGEOM_CAPSULE, 0.025, start_xyz, end_xyz)
            scene.ngeom += 1
        # Place a locator above the simulated base so the robot remains easy
        # to spot when the camera looks across an obstacle.
        locator = data.qpos[:3] + [0, 0, 0.49]
        mj.mjv_initGeom(
            scene.geoms[scene.ngeom], mj.mjtGeom.mjGEOM_SPHERE,
            np.full(3, 0.055), locator, identity, mint,
        )
        scene.ngeom += 1
        image = Image.new("RGB", (1600, 900), BG)
        draw = ImageDraw.Draw(image)

        def text(x, y, s, n, color=WHITE, bold=False):
            draw.text((x, y), s, font=font(n, bold), fill=color)

        text(36, 30, f"{args.scene.capitalize()} inspection route", 46, WHITE, True)
        text(1240, 42, f"{t:.1f} s · MuJoCo", 31, WHITE, True)
        text(36, 104, "2D  /  Route and heading", 27, WHITE, True)
        text(694, 104, "3D  /  Go2 on LiDAR-derived terrain", 27, WHITE, True)
        completed = int(stop_counts[i])
        stop = task["stops"][min(completed, len(task["stops"]) - 1)]
        goal = np.array([stop["observe"][axis] for axis in "xy"])
        panel = map_base.copy()
        map_draw = ImageDraw.Draw(panel)
        map_draw.line([tuple(v) for v in project(path[:, :2])], fill="#667384", width=3)
        leg = np.array([[w[axis] for axis in "xy"] for w in stop["waypoints"]])
        map_draw.line(
            [tuple(v) for v in project(np.vstack([leg, goal]))], fill=AMBER, width=6
        )
        trace = project(qpos[: i + 1, :2])
        if len(trace) > 1:
            map_draw.line([tuple(v) for v in trace], fill=MINT, width=5)
        gx, gy = project(goal)
        map_draw.ellipse(
            (gx - 12, gy - 12, gx + 12, gy + 12), fill=AMBER, outline=BG, width=3
        )
        map_draw.text(
            (min(gx + 18, 440), max(18, gy - 38)),
            "NEXT STOP",
            font=font(24, True),
            fill=AMBER,
            stroke_width=3,
            stroke_fill=BG,
        )
        x, y = project(xy)
        heading = data.xmat[model.cam_bodyid[model.camera("inspection").id]].reshape(
            3, 3
        )[:2, 0]
        theta = np.arctan2(-heading[1], heading[0])
        angles = theta + np.array([0.0, 2.45, -2.45])
        arrow = np.column_stack((np.cos(angles), np.sin(angles))) * np.array(
            [[22], [14], [14]]
        )
        map_draw.polygon(
            [tuple(v) for v in arrow + [x, y]], fill=WHITE, outline=BG, width=3
        )
        map_draw.text(
            (x - 22, y + 22),
            "Go2",
            font=font(23, True),
            fill=WHITE,
            stroke_width=3,
            stroke_fill=BG,
        )
        metre = 2 * scale
        map_draw.line((28, 537, 28 + metre, 537), fill=WHITE, width=4)
        map_draw.text((28, 544), "2 m", font=font(20), fill=WHITE)
        image.paste(panel, (36, 147))
        image.paste(Image.fromarray(renderer.render()), (694, 147))
        text(36, 752, "Go2 heading", 23, WHITE, True)
        text(211, 752, "Driven", 23, MINT, True)
        text(320, 752, "Active plan", 23, AMBER, True)
        text(482, 752, "LiDAR height", 20)
        for index, color in enumerate(HEIGHT_COLORS):
            x0 = 484 + 25 * index
            draw.rectangle((x0, 783, x0 + 24, 790), fill=tuple(color))
        text(694, 752, "Mint marker · Go2 position   /   Mint trail · recent path", 23, MINT, True)
        draw.line((36, 809, 1564, 809), fill="#405065", width=2)
        text(36, 833, f"Next stop · {stop['id']}  /  {np.linalg.norm(goal - xy):.1f} m", 26, AMBER, True)
        returned = summary["return_completed"]
        reached = summary["completed_inspection_targets"]
        total = summary["required_inspection_targets"]
        outcome = "returned to start" if returned else "contact-triggered safety stop"
        text(694, 833, f"Full mission · {reached}/{total} stops · {outcome}", 26,
             MINT if returned else AMBER, True)
        if i == poster:
            image.save(args.run / f"slam-{args.scene}.jpg", quality=93)
        if args.preview:
            image.save(args.run / f"preview-{number}.jpg", quality=90)
        else:
            proc.stdin.write(image.tobytes())
        if number % 250 == 0:
            print(args.scene, "render", number, len(keep), flush=True)
    renderer.close()
    if proc is not None:
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError("Video encoding failed")
        temporary.replace(output)
    (
        args.run
        / ("preview-selection.json" if args.preview else "render-selection.json")
    ).write_text(
        json.dumps(
            dict(spans=spans, frames=len(keep), mode="excerpts", playback_speed=1),
            indent=2,
        )
    )
    print(output, flush=True)


if __name__ == "__main__":
    main()
