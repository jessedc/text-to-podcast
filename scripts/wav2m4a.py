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
        [--cover IMG] [--bitrate 128k] [--no-master] [--target-lufs -16]

Mastering
=========
Kokoro emits clean but unmastered 24 kHz mono speech: quiet, with a drifting
perceived level and no tonal shaping. Before encoding we run a voice mastering
chain so the result sits at the podcast loudness standard and sounds produced
rather than raw. The chain (applied in this order — order matters) is:

  1. highpass f=70        Remove sub-bass / DC offset. Nothing useful lives
                          below ~70 Hz in speech; it only eats headroom.
  2. equalizer -2 dB @250 Cut the "boxy"/muddy low-mids.
  3. equalizer +2 dB @4k  Lift presence for intelligibility (consonants).
  4. acompressor          Gentle 3:1 to even out level so it's consistent on
                          earbuds / in a car.
  5. loudnorm             Normalize to the EBU R128 / Apple Podcasts target of
                          -16 LUFS integrated, -1.5 dBTP. Run two-pass: a
                          measurement pass collects the true input loudness,
                          then the encode pass feeds those measurements back in
                          for an accurate, linear normalization. Falls back to
                          single-pass if measurement can't be parsed.
  6. alimiter -1 dB       True-peak safety catch on any overshoot.
  7. aresample 48000      48 kHz gives the AAC encoder better-behaved input and
                          maximum player compatibility. (Does not add fidelity
                          that isn't in the 24 kHz source — it's about the
                          encoder/playback path, not resolution.)

Steps a human-voice chain would also include (noise gate, de-breath, heavy
de-essing) are skipped: synthetic speech has no noise floor or breaths, and
af_heart isn't notably sibilant. Pass --no-master to encode the WAV untouched.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# Tonal + dynamics processing applied before loudness normalization. Kept
# identical across the measurement and encode passes so the measured loudness
# reflects the signal that actually gets normalized.
PRE_FILTERS = (
    "highpass=f=70,"
    "equalizer=f=250:t=q:w=1.0:g=-2,"
    "equalizer=f=4000:t=q:w=1.5:g=2,"
    "acompressor=threshold=-18dB:ratio=3:attack=10:release=120:makeup=2"
)
LUFS_TP = -1.5   # true-peak ceiling (dBTP)
LUFS_LRA = 11.0  # target loudness range


def measure_loudness(ffmpeg: str, input_wav: Path, target_lufs: float) -> dict | None:
    """First loudnorm pass: measure the (pre-processed) input. Returns the
    parsed JSON stats, or None if measurement fails (caller falls back to
    single-pass)."""
    af = (
        f"{PRE_FILTERS},"
        f"loudnorm=I={target_lufs}:TP={LUFS_TP}:LRA={LUFS_LRA}:print_format=json"
    )
    argv = [ffmpeg, "-i", str(input_wav), "-af", af, "-f", "null", "-"]
    print("Measuring loudness (pass 1/2)…", file=sys.stderr)
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    # loudnorm prints a flat JSON object last in stderr.
    stderr = result.stderr
    start, end = stderr.rfind("{"), stderr.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(stderr[start : end + 1])
    except json.JSONDecodeError:
        return None


def build_master_af(target_lufs: float, measured: dict | None) -> str:
    """Full mastering filter chain for the encode pass."""
    if measured:
        loudnorm = (
            f"loudnorm=I={target_lufs}:TP={LUFS_TP}:LRA={LUFS_LRA}"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            ":linear=true:print_format=summary"
        )
    else:
        # Single-pass fallback — less precise but still normalizes.
        loudnorm = f"loudnorm=I={target_lufs}:TP={LUFS_TP}:LRA={LUFS_LRA}"
    return f"{PRE_FILTERS},{loudnorm},alimiter=limit=-1dB,aresample=48000"


def build_ffmpeg_argv(
    *,
    ffmpeg: str,
    input_wav: Path,
    output_m4a: Path,
    cover: Path | None,
    bitrate: str,
    metadata: dict[str, str],
    audio_filter: str | None,
) -> list[str]:
    argv = [ffmpeg, "-y", "-i", str(input_wav)]
    if cover is not None:
        argv += ["-i", str(cover), "-map", "0:a", "-map", "1:v"]
        argv += ["-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
    if audio_filter:
        argv += ["-af", audio_filter]
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
    ap.add_argument("--bitrate", default="128k", help="AAC bitrate (default: 128k)")
    ap.add_argument("--cover", type=Path, help="Optional cover image (jpg/png)")
    ap.add_argument("--no-master", dest="master", action="store_false",
                    help="Encode the WAV untouched, skipping the mastering chain")
    ap.add_argument("--target-lufs", type=float, default=-16.0,
                    help="Integrated loudness target in LUFS (default: -16, Apple Podcasts)")

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

    audio_filter = None
    if args.master:
        measured = measure_loudness(ffmpeg, args.input, args.target_lufs)
        if measured is None:
            print("warning: loudness measurement failed, using single-pass loudnorm",
                  file=sys.stderr)
        audio_filter = build_master_af(args.target_lufs, measured)

    argv = build_ffmpeg_argv(
        ffmpeg=ffmpeg,
        input_wav=args.input,
        output_m4a=args.output,
        cover=args.cover,
        bitrate=args.bitrate,
        metadata=metadata,
        audio_filter=audio_filter,
    )

    if args.master:
        print("Mastering + encoding (pass 2/2)…", file=sys.stderr)
    print(f"Running: {' '.join(argv)}", file=sys.stderr)
    result = subprocess.run(argv)
    if result.returncode != 0:
        return result.returncode

    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
