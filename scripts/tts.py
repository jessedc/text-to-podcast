#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "kokoro>=0.9.4",
#   "soundfile>=0.12",
#   "numpy>=1.26",
# ]
# ///
"""
Kokoro-82B text-to-speech.

Usage:
    uv run --script tts.py input.txt out.wav [--voice af_heart] [--speed 1.0]

Voice name prefix encodes language + gender: a=American, b=British, j=Japanese,
z=Mandarin, e=Spanish, f=French, h=Hindi, i=Italian, p=Brazilian Portuguese;
f=female, m=male.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline


SAMPLE_RATE = 24_000

VOICES = [
    # American English — female
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    # American English — male
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
    # British English — female
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    # British English — male
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    # Japanese
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    # Mandarin Chinese
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
    "zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang",
    # Spanish
    "ef_dora", "em_alex", "em_santa",
    # French
    "ff_siwis",
    # Hindi
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    # Italian
    "if_sara", "im_nicola",
    # Brazilian Portuguese
    "pf_dora", "pm_alex", "pm_santa",
]
DEFAULT_VOICE = "af_heart"


def _fade_edges(audio: np.ndarray, fade_ms: float = 15.0) -> np.ndarray:
    # Ramp the first/last few ms to zero so the segment starts and ends on a
    # zero-crossing. Kokoro's chunk boundaries land at arbitrary amplitudes;
    # butting them straight against silence (or each other) steps the waveform
    # and produces an audible click. A short linear fade removes that step.
    n = int(SAMPLE_RATE * fade_ms / 1000.0)
    if n == 0 or audio.size < 2 * n:
        return audio
    out = audio.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out


def synth(text: str, voice: str, speed: float) -> np.ndarray:
    pipeline = KPipeline(lang_code=voice[0])  # 'a' = American English, 'b' = British, etc.
    segments: list[np.ndarray] = []
    # Split on blank lines so very long inputs don't blow up in one go.
    # Within a paragraph, collapse single newlines to spaces — PDF extraction
    # hard-wraps mid-sentence and Kokoro otherwise reads those as pauses.
    paragraphs = [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]
    silence = np.zeros(int(SAMPLE_RATE * 0.4), dtype=np.float32)

    for i, para in enumerate(paragraphs, 1):
        print(f"[{i}/{len(paragraphs)}] {para[:60]}{'…' if len(para) > 60 else ''}", file=sys.stderr)
        # Concatenate this paragraph's chunks into one continuous span, then fade
        # only its outer edges. The intra-paragraph chunks are meant to be
        # seamless speech, so we don't fade between them — only at the paragraph
        # boundary, where the 0.4 s pause would otherwise create a click.
        para_chunks = [
            audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
            for _, _, audio in pipeline(para, voice=voice, speed=speed)
        ]
        if not para_chunks:
            continue
        para_audio = _fade_edges(np.concatenate(para_chunks))
        segments.append(para_audio)
        segments.append(silence)

    return np.concatenate(segments) if segments else np.zeros(0, dtype=np.float32)


def main() -> int:
    ap = argparse.ArgumentParser(description="Kokoro TTS: text file → wav")
    ap.add_argument("input", type=Path, help="Input text file (UTF-8)")
    ap.add_argument("output", type=Path, help="Output .wav path")
    ap.add_argument("--voice", choices=VOICES, default=DEFAULT_VOICE, metavar="VOICE")
    ap.add_argument("--speed", type=float, default=1.0)
    args = ap.parse_args()

    text = args.input.read_text(encoding="utf-8")
    audio = synth(text, args.voice, args.speed)
    sf.write(args.output, audio, SAMPLE_RATE)
    print(f"Wrote {args.output} ({len(audio) / SAMPLE_RATE:.1f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
