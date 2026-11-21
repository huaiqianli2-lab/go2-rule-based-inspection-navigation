"""Lay out timestamp-matched onboard stills and field controller events."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render(record, frames, output):
    def font(size, bold=False):
        face = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(face, size)

    image = Image.new("RGB", (1800, 980), "#0b1721")
    draw = ImageDraw.Draw(image)
    draw.text((30, 20), "Indoor field runs · two obstacle responses", font=font(43, True), fill="#eaf1f4")
    draw.text(
        (30, 80), "Onboard stills matched to controller timestamps · each row starts at its own near-stop event",
        font=font(26), fill="#afc3ce",
    )
    for row, episode in enumerate(record["episodes"]):
        top = 142 + 404 * row
        color = "#55e3c4" if episode["name"] == "dynamic" else "#ffbd6d"
        draw.text((30, top), episode["title"], font=font(34, True), fill=color)
        for column, frame in enumerate(episode["frames"]):
            x = 30 + 440 * column
            with Image.open(frames / frame["file"]) as source:
                still = source.convert("RGB")
            still.thumbnail((420, 245), Image.Resampling.LANCZOS)
            image.paste(still, (x + (420 - still.width) // 2, top + 57 + (245 - still.height) // 2))
            draw.text(
                (x, top + 309), f"{frame['label']} · {frame['t_s']:+.2f} s",
                font=font(25, True), fill="#eaf1f4",
            )
        draw.text((30, top + 350), episode["outcome"], font=font(26), fill="#afc3ce")
    draw.text(
        (30, 940), "Branch decisions come from controller logs. The onboard camera does not cover every obstacle.",
        font=font(23), fill="#afc3ce",
    )
    image.save(output, quality=91, optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("record", "frames", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    render(json.loads(args.record.read_text()), args.frames, args.output)
