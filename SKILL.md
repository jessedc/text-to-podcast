---
name: text-to-podcast
description: Convert a web article or PDF into an .m4a podcast file with embedded title, artist, description, and date metadata. Use when the user wants to listen to a long article, paper, or document on a podcast player. Pipeline is URL → PDF → text → LLM reformat → speech (WAV) → LLM metadata extraction → M4A.
license: MIT
compatibility: Requires uv, ffmpeg, espeak-ng, and (only for the URL→PDF step) docker. Kokoro-82M weights (~315 MB) download to ~/.cache/huggingface on first tts run.
---

# text-to-podcast

Turn a web article or PDF into a sideloadable `.m4a` podcast episode with proper metadata.

## Pipeline

```
URL ──► scripts/web2pdf.py ──► .pdf
                                 │
                                 ▼
                          scripts/pdf2txt.py ──► raw .txt
                                                   │
                                                   ▼
                         (LLM applies assets/reformat-prompt.md) ──► clean .txt
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          ▼                                                 ▼
                   scripts/tts.py ──► .wav      (LLM applies assets/metadata-prompt.md) ──► JSON
                                                   │                                          │
                                                   └─────────────────►  scripts/wav2m4a.py ──► .m4a
```

If the user already has a PDF, start at step 2. If they already have plain text, start at step 3.

## File Naming Convention

Use a single `<slug>` derived from the source (article title, author, or date) and apply it to all intermediate files. This makes the pipeline traceable and debuggable:

| Stage | File name | Example |
|-------|-----------|--------|
| PDF (step 1) | `<slug>.pdf` | `mythical-agent-month.pdf` |
| Raw text (step 2) | `<slug>.raw.txt` | `mythical-agent-month.raw.txt` |
| Clean text (step 3) | `<slug>.clean.txt` | `mythical-agent-month.clean.txt` |
| WAV (step 4) | `<slug>.wav` | `mythical-agent-month.wav` |
| Final M4A (step 6) | `<slug>.m4a` | `mythical-agent-month.m4a` |

After producing the `.m4a`, delete the intermediate `.pdf`, `.raw.txt`, `.clean.txt`, and `.wav` files unless the user asks to keep them.

## Prerequisites

```sh
brew install uv ffmpeg espeak-ng
# docker only needed for step 1 (URL → PDF)
```

## Steps

### 1. URL → PDF (skip if input is already a PDF or text)

```sh
uv run --script scripts/web2pdf.py <url> [output.pdf]
```

- Output defaults to `YYYY-MM-DD-<url-slug>.pdf` in the current directory.
- Spins up a throwaway Gotenberg docker container; the container is stopped on exit.
- For slow / JS-heavy pages, set `WAIT_DELAY=15s` (default `5s`).

### 2. PDF → raw text

```sh
uv run --script scripts/pdf2txt.py <input.pdf> <output.raw.txt>
```

The PDF extractor emits column-wrap line breaks and may include page chrome (nav menus, ad blocks, tag lists, footers). That is fixed in step 3.

### 3. LLM reformat — clean the text

Read `assets/reformat-prompt.md` and apply it to the raw text produced in step 2. Write the result to a new file, e.g. `<name>.clean.txt`.

The prompt's hard rules:
- Body content must be preserved character-for-character. No paraphrasing, summarizing, or reordering.
- Only inline page chrome (ads, nav, tag lists, copyright footers) may be removed.
- PDF column-wrap line breaks within a paragraph are joined into one line.
- Section headings are placed on their own line with blank lines above and below.

Spot-check that body sentences in the output match the input verbatim.

### 4. Text → WAV (speech synthesis)

```sh
uv run --script scripts/tts.py <clean.txt> <output.wav> [--voice female|male] [--speed 1.0]
```

- `female` → `af_heart` (American female, warm) — default
- `male` → `bm_george` (British male)
- First run downloads the Kokoro-82M weights (~315 MB).
- The script splits on blank lines, so very long inputs stream paragraph by paragraph.

### 5. LLM metadata extraction

Read `assets/metadata-prompt.md` and apply it to the cleaned text from step 3. The model returns a single JSON object:

```json
{"title": "...", "artist": "...", "description": "...", "date": "YYYY-MM-DD"}
```

Parse it. If `date` is the empty string, substitute today's date in `YYYY-MM-DD` form.

### 6. WAV → M4A podcast

```sh
uv run --script scripts/wav2m4a.py <input.wav> <output.m4a> \
  --title "<title>" \
  --artist "<artist>" \
  --date <date> \
  --description "<description>"
```

If the description would exceed **500 characters**, write it to a file (e.g., `<slug>.desc.txt`) and pass `--description-file <path>` instead of `--description`. Short descriptions can be passed inline.

By default this step also **masters** the audio: a voice EQ/compression chain plus two-pass loudness normalization to −16 LUFS (Apple Podcasts / EBU R128) with a −1.5 dBTP true-peak ceiling, then a 48 kHz resample. This is what makes the output sit at podcast loudness and sound produced rather than raw. See the module docstring in `scripts/wav2m4a.py` for the full chain. Pass `--no-master` to encode the WAV untouched.

Other flags (with sensible defaults):

| Flag           | Default                            |
| -------------- | ---------------------------------- |
| `--album`      | same as `--title`                  |
| `--genre`      | `Podcast`                          |
| `--bitrate`    | `128k`                             |
| `--target-lufs`| `-16` (integrated loudness target) |
| `--no-master`  | off (mastering on by default)      |

## Worked example

```sh
URL="https://example.com/posts/the-mythical-agent-month"

uv run --script scripts/web2pdf.py "$URL" article.pdf
uv run --script scripts/pdf2txt.py article.pdf article.raw.txt

# Step 3: agent applies assets/reformat-prompt.md to article.raw.txt
#         and writes article.clean.txt

uv run --script scripts/tts.py article.clean.txt article.wav

# Step 5: agent applies assets/metadata-prompt.md to article.clean.txt
#         and parses the returned JSON

uv run --script scripts/wav2m4a.py article.wav article.m4a \
  --title "The Mythical Agent-Month" \
  --artist "Simon Willison" \
  --date 2026-02-14 \
  --description "Simon Willison argues that adding more AI agents to a stalled project rarely produces linear speedups, because coordination overhead grows faster than throughput."
```

## Troubleshooting

- **`espeak-ng` not found** — Kokoro needs it for phonemization. `brew install espeak-ng`.
- **`docker` not found / refusing to start** — only needed for step 1. If you already have a PDF or text, skip web2pdf entirely.
- **`ffmpeg` not found** — `brew install ffmpeg`.
- **Page loaded blank in step 1** — bump `WAIT_DELAY` (e.g. `WAIT_DELAY=15s uv run --script scripts/web2pdf.py …`).
- **Robotic prosody** — try `--voice male` or nudge `--speed` down to `0.95`.
- **Out of memory on long inputs** — the TTS script splits on blank lines; if a single paragraph is still too big, break it up in the cleaned text file.
- **`title` or `artist` missing from JSON** — re-run step 5 with a longer excerpt that includes the byline and date, or fall back to manual values when invoking `wav2m4a.py`.

## What to Do When Things Break

Use this decision tree to recover from failures without aborting the pipeline:

### Step 1 (URL → PDF)
- **Page loaded blank / timeout** — bump `WAIT_DELAY` to `15s` or `30s`, retry.
- **Port 3000 conflict** — check if something else is bound to that port; the script may need a fix.
- **Paywalled or JS-rendered page** — ask the user for a PDF or plain text instead and skip to step 2 or 3.

### Step 2 (PDF → Text)
- **Corrupt or password-protected PDF** — ask the user to re-export or provide a different file.
- **Empty output** — the PDF may have embedded images only (no selectable text); ask the user for an alternative source.

### Step 3 (LLM Reformat)
- **LLM refuses or hallucinates** — re-run with a smaller excerpt of the raw text first as a test. If the agent still struggles, manually remove obvious chrome and retry.

### Step 4 (Text → WAV)
- **TTS OOM or crash on a paragraph** — split that paragraph in the `.clean.txt` file with a blank line, then retry.
- **Kokoro model download fails** — check internet connectivity; the weights (~315 MB) are cached at `~/.cache/huggingface` so retries pick up where they left off.

### Step 5 (Metadata Extraction)
- **`date` missing or unparseable** — substitute today's date in `YYYY-MM-DD` form.
- **`title` or `artist` missing** — re-run with a longer excerpt that includes the byline, or use manual fallback values in step 6.
- **`description` is too generic** — ask the agent to focus on the article's main thesis or unique angle.

### Step 6 (WAV → M4A)
- **ffmpeg fails** — check disk space, lower `--bitrate` (e.g. `96k`), or try `--no-master` to isolate whether the mastering chain is the cause.
- **Description too long for inline flag** — write it to `<slug>.desc.txt` and use `--description-file` (threshold: 500 characters).

### General
- **Want to inspect intermediate files** — don't delete them after step 6; they're useful for debugging.
- **Want to skip the whole pipeline** — you can start at any step. If the user provides a PDF, begin at step 2. If they provide plain text, begin at step 3.
