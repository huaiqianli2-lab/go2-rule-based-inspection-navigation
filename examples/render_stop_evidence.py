"""Render the final saved poses and the separately timestamped safety event."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .render_measured_patrol import MeasuredRenderer, mj
from .render_slam import AMBER, BG, MUTED, WHITE, font
from .slam_patrol import SCENES, build_model, ground, input_file, load_inputs
from tools.point_cloud import read_xyz


def render(inputs, robot_xml, run, output, *, sequence=False):
    summary = json.loads((run / "mission.json").read_text())
    (stop,) = (event for event in summary["events"] if event["event"] == "safety_stop")
    with np.load(run / "states.npz") as states:
        times, poses = states["times"], states["qpos"]
    last = np.searchsorted(times, stop["t_s"], side="right") - 1
    approach = np.searchsorted(times, times[last] - (3.5 if sequence else 1.5))
    if not 0 <= approach < last:
        raise ValueError("The archive needs two saved poses before the safety event")

    scene = summary["scene"]
    _, terrain, _ = load_inputs(inputs, scene)
    model = build_model(inputs, scene, robot_xml)
    cloud = read_xyz(input_file(inputs, SCENES[scene][-1]))
    data = mj.MjData(model)
    renderer = MeasuredRenderer(model, cloud, poses[approach:last + 1], scene, size=(960, 480) if sequence else (564, 342))
    renderer.camera_offset *= 0.41
    def render_pose(index):
        data.qpos[:] = poses[index]
        mj.mj_forward(model, data)
        xy = poses[max(0, index - 38):index + 1, :2]
        trace = np.c_[xy, [ground(terrain, p) + 0.055 for p in xy]]
        return Image.fromarray(renderer.render(data, trace))

    if sequence:
        output.mkdir(parents=True, exist_ok=True)
        # Archive cadence is 25 Hz. Keep alternate samples, including the last one.
        indices = range(last - 2 * ((last - approach) // 2), last + 1, 2)
        try:
            for number, index in enumerate(indices):
                render_pose(index).save(output / f"{number:04d}.jpg", quality=94)
        finally:
            renderer.close()
        (output / "times.json").write_text(json.dumps([float(times[i]) for i in indices]))
        return

    image = Image.new("RGB", (1800, 576), BG)
    draw = ImageDraw.Draw(image)
    draw.text((30, 20), "Indoor simulation · the logged safety stop", font=font(43, True), fill=WHITE)
    draw.text((31, 81), "Archived Go2 states in the measured scene", font=font(28), fill=MUTED)
    try:
        for x, index, label in ((30, approach, "Approaching"), (618, last, "Last saved pose")):
            image.paste(render_pose(index), (x, 130))
            draw.text((x, 494), f"{label} · {times[index]:.3f} s", font=font(30, True), fill=WHITE)
    finally:
        renderer.close()

    draw.rounded_rectangle((1206, 130, 1770, 472), 16, fill="#29231e")
    draw.text((1234, 155), "RECORDED EVENT", font=font(27, True), fill=AMBER)
    draw.text((1234, 203), f"{stop['t_s']:.3f} s · Safety stop", font=font(34, True), fill=WHITE)
    for y, line in (
        (267, "Obstacle contact samples: " + str(stop["obstacle_contact_samples"])),
        (310, "Non-foot floor contacts: " + str(stop["non_foot_floor_contact_samples"])),
        (366, f"{summary['completed_inspection_targets']}/{summary['required_inspection_targets']} observations completed"),
        (409, "Simulation ends at the trigger"),
    ):
        draw.text((1234, y), line, font=font(27), fill=WHITE)
    draw.text((1206, 495), "No pose recorded at the contact instant", font=font(25), fill=MUTED)
    image.save(output, quality=92, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("inputs", "robot-xml", "run", "output"):
        parser.add_argument(f"--{argument}", required=True, type=Path)
    parser.add_argument("--sequence", action="store_true", help="Write a 12.5 Hz image sequence to an output directory")
    options = parser.parse_args()
    render(options.inputs, options.robot_xml, options.run, options.output, sequence=options.sequence)
