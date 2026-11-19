"""Summarize historical pose traces without sharing site geometry."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont


COLORS = {"current":"#64e5c5", "astar":"#f9b66e", "dijkstra":"#86acff"}
NAMES = {"current":"Project stack", "astar":"NavFn A*", "dijkstra":"NavFn Dijkstra"}
W, H, FPS = 1440, 810, 24


def font(size, bold=False):
    return ImageFont.truetype(f"DejaVuSans{'-Bold' if bold else ''}.ttf", size)


def frame(traces, t):
    im = Image.new("RGB", (W,H), "#0b1822")
    d = ImageDraw.Draw(im)

    def label(pos, text, size, color="#eff6f7", bold=False):
        d.text(pos,text,fill=color,font=font(size,bold))

    label((52,30),"GO2 PATROL   /   MUJOCO R2 ARCHIVE",21,COLORS["current"],True)
    label((50,66),"Distance from each run’s first pose",42,bold=True)
    label((52,126),"Six saved simulation traces   ·   Common elapsed-time axis",24,"#acc5d3")
    label((1190,62),f"{t/60:05.1f} min",29,bold=True)
    for j,(scene,title) in enumerate((("indoor_large","Indoor"),("outdoor_small","Outdoor"))):
        x0 = 53+676*j
        x1 = x0+654
        d.rounded_rectangle((x0,198,x1,679),17,fill="#142b37")
        label((x0+24,213),title,29,bold=True)
        left, top, right, bottom = x0+69, 281, x1-31, 605
        def xy(tv,value):
            return left+(right-left)*tv/2400, bottom-(bottom-top)*value/80
        for val in (0,20,40,60,80):
            _, y = xy(0,val)
            d.line((left,y,right,y),fill="#345361",width=1)
            label((left-42,y-12),f"{val}",15,"#abc3cd")
        for minute in (0,10,20,30,40):
            x, _ = xy(minute*60,0)
            d.line((x,top,x,bottom),fill="#345361",width=1)
            label((x-13,bottom+9),str(minute),16,"#abc3cd")
        label((x0+22,259),"m",15,"#abc3cd")
        label((right-49,bottom+32),"minutes",15,"#abc3cd")
        for method,color in COLORS.items():
            samples = traces[scene][method]
            points = [xy(time,value) for time,value in samples if time <= t]
            if len(points) > 1:
                d.line(points,fill=color,width=4)
            if points:
                x,y=points[-1]
                d.ellipse((x-5,y-5,x+5,y+5),fill=color)
    for i,(method,color) in enumerate(COLORS.items()):
        x=53+315*i
        d.rounded_rectangle((x,716,x+29,722),3,fill=color)
        label((x+41,705),NAMES[method],21,color,True)
    label((52,757),"A dot marks the latest available sample. Traces end when their recordings end.",21,"#acc5d3")
    return im


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("data",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--ffmpeg",default="ffmpeg")
    args=p.parse_args()
    traces=json.loads(args.data.read_text())["traces"]
    args.output.mkdir(parents=True,exist_ok=True)
    frame(traces,2400).save(args.output/"archived-distance.png",optimize=True)
    command=[args.ffmpeg,"-y","-v","error","-f","rawvideo","-pixel_format","rgb24","-video_size",f"{W}x{H}",
             "-framerate",str(FPS),"-i","-","-c:v","libx264","-threads","2","-crf","20","-pix_fmt","yuv420p",
             "-movflags","+faststart",str(args.output/"archived-distance.mp4")]
    with subprocess.Popen(command,stdin=subprocess.PIPE) as ffmpeg:
        for n in range(14*FPS):
            ffmpeg.stdin.write(frame(traces,min(2400,n*2400/(12*FPS))).tobytes())
        ffmpeg.stdin.close()
        if ffmpeg.wait():
            raise RuntimeError("FFmpeg failed")


if __name__=="__main__":
    main()
