#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2", "yt-dlp>=2026.8.19", "imageio-ffmpeg>=0.6.0"]
# ///
"""Scene-change frames of a YouTube video, for Claude to look at (D74).

  frames.py URL [--max 24] [--threshold 0.2] [--max-minutes 180]

Downloads the video stream (<= 720p) into <vault>/.git/synapsidian/frames/<video id>/, takes one
frame per scene change plus evenly spaced frames where scenes are sparse (ffmpeg from the
imageio-ffmpeg wheel, nothing installed system-wide), samples them down to --max across the
whole video, and deletes the video. Frame folders older than two days are removed on every
run; git never sees them.

Prints {"ok", "video", "duration", "scene_changes", "frames": [{"path", "at"}], "dir"}.
Exit 2 = not a YouTube link, 4 = download or extraction failed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from synapsidianlib import config, sources

KEEP_SECONDS = 2 * 24 * 3600
PTS = re.compile(r"pts_time:\s*([0-9.]+)")


def fail(code: int, message: str) -> None:
    print(json.dumps({"ok": False, "error": message}))
    sys.exit(code)


def prune(root: Path) -> None:
    cutoff = time.time() - KEEP_SECONDS
    for folder in root.iterdir() if root.is_dir() else ():
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)


def download(video: str, workdir: Path, max_minutes: int) -> tuple[Path, float]:
    import yt_dlp

    options: dict[str, Any] = {
        # Video only: no audio means no merge step, so no system ffmpeg is needed. H.264 first:
        # its decoder honours `-skip_frame nokey`, AV1 and VP9 decode every frame (3x slower).
        "format": "bv*[height<=720][vcodec^=avc1]/bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]/w",
        "outtmpl": str(workdir / "video.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {max_minutes * 60}"),
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video}", download=True)
    except yt_dlp.utils.DownloadError as exc:
        fail(4, f"download failed: {exc}")
    files = [p for p in workdir.glob("video.*") if p.suffix not in (".part", ".ytdl")]
    if not files:
        fail(4, f"nothing downloaded (longer than {max_minutes} minutes, or unavailable)")
    return files[0], float((info or {}).get("duration") or 0)


def run_ffmpeg(args: list[str]) -> str:
    import imageio_ffmpeg

    proc = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(4, f"ffmpeg failed: {proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else proc.returncode}")
    return proc.stderr


def scene_frames(video_file: Path, workdir: Path, threshold: float) -> list[tuple[Path, float]]:
    """One frame per scene change (plus the first), decoding keyframes only for speed."""
    log = run_ffmpeg(
        [
            "-skip_frame", "nokey", "-i", str(video_file),
            "-vf", f"select='eq(n\\,0)+gt(scene\\,{threshold})',scale='min(1280,iw)':-2,showinfo",
            "-fps_mode", "vfr", "-q:v", "3", str(workdir / "scene_%04d.jpg"),
        ]
    )  # fmt: skip
    times = [float(t) for t in PTS.findall(log)]
    return list(zip(sorted(workdir.glob("scene_*.jpg")), times, strict=False))


def interval_frames(video_file: Path, workdir: Path, duration: float, count: int) -> list[tuple[Path, float]]:
    """`count` evenly spaced frames, each grabbed by seeking (no full decode of the video)."""
    frames: list[tuple[Path, float]] = []
    for index in range(count):
        at = duration * (index + 0.5) / count
        target = workdir / f"even_{index + 1:04d}.jpg"
        run_ffmpeg(
            ["-ss", f"{at:.2f}", "-i", str(video_file), "-frames:v", "1",
             "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(target)]
        )  # fmt: skip
        if target.exists():
            frames.append((target, at))
    return frames


def sample(frames: list[tuple[Path, float]], limit: int) -> list[tuple[Path, float]]:
    """`limit` frames spread evenly over *time* (first and last kept); the rest deleted.

    Picking by index would follow the scene changes, which cluster in busy stretches and
    leave minutes of a slower part unseen; each slot takes the unused frame nearest its time."""
    if len(frames) <= limit:
        return frames
    frames = sorted(frames, key=lambda frame: frame[1])
    first, last = frames[0][1], frames[-1][1]
    targets = [first + (last - first) * i / (limit - 1) for i in range(limit)] if limit > 1 else [first]
    keep: set[int] = set()
    for target in targets:
        free = [i for i in range(len(frames)) if i not in keep]
        keep.add(min(free, key=lambda i: abs(frames[i][1] - target)))
    for index, (path, _) in enumerate(frames):
        if index not in keep:
            path.unlink(missing_ok=True)
    return [frame for index, frame in enumerate(frames) if index in keep]


def clock(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    parser.add_argument("url")
    parser.add_argument("--max", type=int, default=24, help="frames to keep (default 24)")
    parser.add_argument("--threshold", type=float, default=0.2, help="scene-change sensitivity, 0..1")
    parser.add_argument("--max-minutes", type=int, default=180)
    args = parser.parse_args()

    video = sources.youtube_id(args.url)
    if video is None:
        fail(2, f"{args.url!r} is not a YouTube link")
    vault_root = config.vault_path(args.vault)
    base = config.state_dir(vault_root) if vault_root and vault_root.is_dir() else config.data_dir()
    root = base / "frames"  # prune() empties this folder only, never the state dir around it
    root.mkdir(parents=True, exist_ok=True)
    prune(root)
    workdir = root / video
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)

    video_file, duration = download(video, workdir, args.max_minutes)
    try:
        scenes = scene_frames(video_file, workdir, args.threshold)
        even = interval_frames(video_file, workdir, duration, args.max) if duration > 0 else []
    finally:
        video_file.unlink(missing_ok=True)
    frames = sample(merge(scenes, even, duration / max(args.max, 1) / 2), args.max)
    print(
        json.dumps(
            {
                "ok": True,
                "video": video,
                "duration": clock(duration),
                "scene_changes": len(scenes),
                "dir": str(workdir),
                "frames": [{"path": str(path), "at": clock(at)} for path, at in frames],
            }
        )
    )


def merge(scenes: list[tuple[Path, float]], even: list[tuple[Path, float]], gap: float) -> list[tuple[Path, float]]:
    """Scene-change frames, plus evenly spaced ones where no scene frame is within `gap` seconds
    (slow animations and talking heads change little between keyframes). Sorted by time."""
    kept = list(scenes)
    for path, at in even:
        if any(abs(at - s) < gap for _, s in scenes):
            path.unlink(missing_ok=True)
        else:
            kept.append((path, at))
    return sorted(kept, key=lambda frame: frame[1])


if __name__ == "__main__":
    main()
