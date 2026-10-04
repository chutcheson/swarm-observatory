#!/usr/bin/env python3
"""Contact sheet of frames from a video: tools/contact.py VIDEO OUT.png [--every S] [--cols N] [--width W]"""
import argparse, subprocess, json, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("out")
ap.add_argument("--every", type=float, default=3.0)
ap.add_argument("--cols", type=int, default=4)
ap.add_argument("--width", type=int, default=480)
ap.add_argument("--times", type=str, default="")
a = ap.parse_args()
dur = float(json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","json",a.video]))["format"]["duration"])
times = [float(x) for x in a.times.split(",")] if a.times else [t*a.every for t in range(int(dur//a.every)+1)]
tiles = []
with tempfile.TemporaryDirectory() as td:
    for i,t in enumerate(times):
        p = Path(td)/f"f{i}.png"
        subprocess.run(["ffmpeg","-v","error","-ss",f"{min(t,dur-0.05):.3f}","-i",a.video,"-frames:v","1","-vf",f"scale={a.width}:-1",str(p),"-y"],check=True)
        im = Image.open(p).convert("RGB"); d = ImageDraw.Draw(im)
        d.rectangle([0,0,70,18], fill=(0,0,0)); d.text((3,3), f"{t:6.1f}s", fill=(255,255,0))
        tiles.append(im)
w,h = tiles[0].size; rows = (len(tiles)+a.cols-1)//a.cols
sheet = Image.new("RGB",(w*a.cols,h*rows),(40,40,40))
for i,im in enumerate(tiles): sheet.paste(im,((i%a.cols)*w,(i//a.cols)*h))
sheet.save(a.out); print(a.out, len(tiles), "frames, video", round(dur,2), "s")
