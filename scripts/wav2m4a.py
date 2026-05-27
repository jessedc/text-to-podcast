#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Package a WAV as an M4A podcast file with metadata via ffmpeg.

Usage:
    uv run --script wav2m4a.py in.wav out.m4a [--title …] [--artist …]
        [--album …] [--date YYYY-MM-DD] [--genre …]
        [--description TEXT | --description-file PATH]
        [--cover IMG] [--bitrate 64k]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path


def build_ffmpeg_argv(
    *,
    ffmpeg: str,
    input_wav: Path,
    output_m4a: Path,
    cover: Path | None,
    bitrate: str,
    metadata: dict[str, str],
) -> list[str]:
    argv = [ffmpeg, "-y", "-i", str(input_wav)]
    if cover is not None:
        argv += ["-i", str(cover), "-map", "0:a", "-map", "1:v"]
        argv += ["-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
    argv += ["-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart"]
    for key, value in metadata.items():
        if value:
            argv += ["-metadata", f"{key}={value}"]
    argv += [str(output_m4a)]
    return argv


def main() -> int:
    ap = argparse.ArgumentParser(description="WAV → M4A podcast with metadata")
    ap.add_argument("input", type=Path, help="Input .wav path")
    ap.add_argument("output", type=Path, help="Output .m4a path")
    ap.add_argument("--title", help="Episode title (default: output filename stem)")
    ap.add_argument("--artist", default="Kokoro TTS", help="Default: 'Kokoro TTS'")
    ap.add_argument("--album", help="Show name (default: same as --title)")
    ap.add_argument("--date", default=date.today().isoformat(), help="ISO date (default: today)")
    ap.add_argument("--genre", default="Podcast")
    ap.add_argument("--bitrate", default="64k", help="AAC bitrate (default: 64k)")
    ap.add_argument("--cover", type=Path, help="Optional cover image (jpg/png)")

    desc = ap.add_mutually_exclusive_group()
    desc.add_argument("--description", help="Inline description text")
    desc.add_argument("--description-file", type=Path, help="Read description from a file")

    args = ap.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("error: ffmpeg not found on PATH (try `brew install ffmpeg`)", file=sys.stderr)
        return 1

    if not args.input.is_file():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 1

    if args.cover is not None and not args.cover.is_file():
        print(f"error: cover not found: {args.cover}", file=sys.stderr)
        return 1

    title = args.title or args.output.stem
    album = args.album or title

    description = args.description
    if args.description_file is not None:
        description = args.description_file.read_text(encoding="utf-8").strip()

    metadata = {
        "title": title,
        "artist": args.artist,
        "album": album,
        "album_artist": args.artist,
        "date": args.date,
        "genre": args.genre,
        "comment": description or "",
        "description": description or "",
    }

    argv = build_ffmpeg_argv(
        ffmpeg=ffmpeg,
        input_wav=args.input,
        output_m4a=args.output,
        cover=args.cover,
        bitrate=args.bitrate,
        metadata=metadata,
    )

    print(f"Running: {' '.join(argv)}", file=sys.stderr)
    result = subprocess.run(argv)
    if result.returncode != 0:
        return result.returncode

    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
