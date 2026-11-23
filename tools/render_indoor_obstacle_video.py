"""Assemble a single video from the saved simulation and synchronized onboard frames."""

import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

SIZE = (960, 632)
FPS = 12.5
BG = "#0b1721"
WHITE = "#edf5f8"
AMBER = "#ffc57b"
MINT = "#63e4cd"
BLUE = "#8ec9ff"
ACCENTS = (AMBER, MINT, BLUE)


def font(size, bold=False):
    return ImageFont.truetype(f"DejaVuSans{'-Bold' if bold else ''}.ttf", size)


def camera_frame(folder, index):
    with Image.open(folder / f"{index:04d}.jpg") as source:
        return ImageOps.contain(source.convert("RGB"), (960, 480), Image.Resampling.LANCZOS)


def layout(view, tag, title, time, status, detail, chapter, progress, *, slate=None):
    accent = ACCENTS[chapter]
    image = Image.new("RGB", SIZE, BG)
    if slate:
        view = ImageEnhance.Brightness(view).enhance(0.55)
    image.paste(view, ((960 - view.width) // 2, 57 + (480 - view.height) // 2))
    draw = ImageDraw.Draw(image)
    draw.text((22, 15), tag, font=font(23, True), fill=accent)
    draw.text((268, 17), title, font=font(23), fill=WHITE)
    draw.text((938, 18), time, anchor="ra", font=font(22, True), fill=WHITE)
    if slate:
        draw.rounded_rectangle((198, 220, 762, 373), radius=14, fill="#152430", outline=accent, width=2)
        draw.text((480, 243), slate[0], anchor="ma", font=font(39, True), fill=accent)
        draw.text((480, 306), slate[1], anchor="ma", font=font(28, True), fill=WHITE)
    draw.text((22, 546), status, font=font(28, True), fill=accent)
    draw.text((22, 582), detail, font=font(21), fill=WHITE)
    for i, color in enumerate(ACCENTS):
        left = 322 * i
        draw.rectangle((left, 626, left + 315, 631), fill="#314855")
        if i <= chapter:
            fill = 1 if i < chapter else progress
            draw.rectangle((left, 626, left + round(315 * fill), 631), fill=color)
    return image


def field_overlay(episode, time):
    events = {entry["event"]: entry for entry in episode["events"]}
    if time < 0:
        return "APPROACH", "Onboard camera · near-stop clock starts at 0.00 s"
    if time >= events["nav_arrived"]["t_s"]:
        return "WAYPOINT REACHED", "The controller logged arrival at the same waypoint"
    if episode["name"] == "dynamic":
        if time >= events["near_judge_dynamic"]["t_s"]:
            return "CLEARANCE RESTORED · RESUME", "Controller classified transient blockage at +2.44 s"
    elif time >= events["bypass_done"]["t_s"]:
        return "BYPASS COMPLETE · RESUME", "Right bypass completed · 0.81 m logged"
    elif time >= events["bypass_start"]["t_s"]:
        return "BYPASS RIGHT", "Backoff complete · 0.06 m logged"
    elif time >= events["backoff_start"]["t_s"]:
        return "PERSISTENT BLOCKAGE · BACK OFF", "Controller classified static blockage at +3.02 s"
    return "STOPPED · CHECKING CLEARANCE", f"Controller hold · {time:.1f} s elapsed"


def render(root, record, indoor, output, ffmpeg):
    chapters = ["simulation", "dynamic", "static"]
    times = {key: json.loads((root / key / "times.json").read_text()) for key in chapters}
    stop_frames = 35
    title_frames = 12
    (event_record,) = (event for event in indoor["events"] if event["event"] == "safety_stop")
    observations = f"{indoor['completed_inspection_targets']}/{indoor['required_inspection_targets']}"
    with subprocess.Popen(
        [ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", f"{SIZE[0]}x{SIZE[1]}", "-framerate", str(FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-threads", "2", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)],
        stdin=subprocess.PIPE,
    ) as encoder:
        def write(*args, **kwargs):
            encoder.stdin.write(layout(*args, **kwargs).tobytes())

        sim_tag = "01 / SIMULATION"
        sim_title = "Archived Go2 · measured SLAM map"
        for i, time in enumerate(times["simulation"]):
            view = camera_frame(root / "simulation", i)
            write(view, sim_tag, sim_title, f"{time:.1f} s",
                  "APPROACH TO LOGGED STOP", "Saved robot poses · 1×", 0,
                  progress=(i + 1) / (len(times["simulation"]) + stop_frames))
        for i in range(stop_frames):
            write(view, sim_tag, sim_title, f"{event_record['t_s']:.3f} s log",
                  "RUN ENDED AT THE TRIGGER",
                  f"Image held at {times['simulation'][-1]:.3f} s · last saved pose", 0,
                  progress=(len(times["simulation"]) + i + 1) / (len(times["simulation"]) + stop_frames),
                  slate=("SAFETY STOP LOGGED", f"Obstacle contact · {observations} completed"))
        for chapter, episode in enumerate(record["episodes"], 1):
            name = episode["name"]
            title = "Transient blockage" if name == "dynamic" else "Persistent blockage"
            field_run = f"FIELD RUN {'A' if chapter == 1 else 'B'}"
            tag = f"0{chapter + 1} / {field_run}"
            first = camera_frame(root / name, 0)
            for _ in range(title_frames):
                write(first, tag, title, "1× follows", "ONBOARD CAMERA",
                      "Clock resets at this run's near stop", chapter, progress=0,
                      slate=(field_run, "Separate real recording"))
            for j, time in enumerate(times[name]):
                status, detail = field_overlay(episode, time)
                write(camera_frame(root / name, j), tag, title, f"{time:+.2f} s",
                      status, detail, chapter, progress=(j + 1) / len(times[name]))
        encoder.stdin.close()
        if encoder.wait():
            raise RuntimeError("Video encoding failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    data = Path(__file__).resolve().parents[1] / "docs/data"
    record = json.loads((data / "field-obstacle-response.json").read_text())
    (indoor,) = (case for case in json.loads((data / "slam-physics-results.json").read_text())["cases"]
                 if case["scene"] == "indoor")
    render(args.frames, record, indoor, args.output, args.ffmpeg)
