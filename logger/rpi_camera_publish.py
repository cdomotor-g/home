#!/usr/bin/env python3
"""
LPU: Raspberry Pi + camera module -> timestamped stills -> GitHub -> dashboard.

Captures a still at each run, drops it into a git repo alongside a
manifest.json, prunes old frames, commits and pushes. The dashboard reads the
manifest (raw.githubusercontent.com and GitHub Pages both send CORS headers)
and shows the latest image plus recent history on the collection's card.

Manifest format (what the dashboard expects — `file` is resolved relative to
the manifest URL, so plain filenames in the same folder Just Work):
  { "images": [ { "file": "2026-07-06T08-00-00.jpg",
                  "t": "2026-07-06T08:00:00+10:00" }, … ] }

Recommended layout — a separate small public repo so this one stays light:
  home-images/
    backyard/manifest.json + stills     <- one folder per camera
Dashboard manifest URL:
  https://raw.githubusercontent.com/YOURUSER/home-images/main/backyard/manifest.json

Setup on the Pi:
  sudo apt install git python3          # rpicam-still ships with Raspberry Pi OS
  git clone git@github.com:YOURUSER/home-images.git /home/pi/home-images
  # edit the settings below, test once:  python3 rpi_camera_publish.py
Schedule with cron (every 30 min, daylight only):
  */30 6-18 * * *  /usr/bin/python3 /home/pi/home/logger/rpi_camera_publish.py
"""

import datetime
import json
import pathlib
import shutil
import subprocess
import sys

# ----------------------------------------------------------------- settings
REPO_DIR = pathlib.Path("/home/pi/home-images")  # git clone with push access
CAMERA_DIR = "backyard"                          # folder per camera/collection
KEEP_FRAMES = 48                                 # frames kept in repo + manifest
WIDTH, HEIGHT, QUALITY = 1280, 720, 85           # keep the repo small

CAPTURE_CMDS = (  # first binary that exists wins (OS-version differences)
    ["rpicam-still", "--nopreview", "--width", str(WIDTH), "--height", str(HEIGHT),
     "--quality", str(QUALITY), "-o"],
    ["libcamera-still", "--nopreview", "--width", str(WIDTH), "--height", str(HEIGHT),
     "--quality", str(QUALITY), "-o"],
)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def capture(dest):
    for cmd in CAPTURE_CMDS:
        if shutil.which(cmd[0]):
            run(cmd + [str(dest)])
            return
    sys.exit("no camera tool found (rpicam-still / libcamera-still)")


def main():
    cam_dir = REPO_DIR / CAMERA_DIR
    cam_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cam_dir / "manifest.json"

    now = datetime.datetime.now().astimezone()
    name = now.strftime("%Y-%m-%dT%H-%M-%S") + ".jpg"
    capture(cam_dir / name)

    try:
        images = json.loads(manifest_path.read_text())["images"]
    except (OSError, ValueError, KeyError):
        images = []
    images.append({"file": name, "t": now.isoformat(timespec="seconds")})

    # prune: manifest keeps the newest KEEP_FRAMES; their files stay, the rest go
    images = images[-KEEP_FRAMES:]
    keep = {e["file"] for e in images} | {"manifest.json"}
    for f in cam_dir.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
    manifest_path.write_text(json.dumps({"images": images}, indent=1) + "\n")

    run(["git", "-C", str(REPO_DIR), "add", "-A", CAMERA_DIR])
    run(["git", "-C", str(REPO_DIR), "commit", "-m", f"{CAMERA_DIR}: {name}", "--quiet"])
    run(["git", "-C", str(REPO_DIR), "push", "--quiet"])
    print(f"published {CAMERA_DIR}/{name} ({len(images)} frames in manifest)")


if __name__ == "__main__":
    main()
