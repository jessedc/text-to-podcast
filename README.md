# Text to Podcast Agent Skill

An agent skill and workflow that generates high quality, mastered `.m4a` podcast episodes with embeded date, title, artist and description meta data from URLs, PDFs or plain text files. 

## Installing

You can install this skill into Claude Code, Gemini, Cursor, and other agents that support the [Agent Skills](https://agentskills.io/home) format:

```bash
npx skills add https://github.com/jessedc/text-to-podcast --skill text-to-podcast
```

Alternatively, you can clone this repository or download a release and install it however you like.

### Prerequisites

```bash
brew install uv ffmpeg espeak-ng
```

`docker` is required for the URL → PDF step. If you start from a PDF or plain text, you can skip it.

Kokoro-82M voice weights (~315 MB) are downloaded to `~/.cache/huggingface` on the first TTS run.

## Using this skill

The skill is called Text to Podcast, and can be triggered in Claude Code:

> /text-to-podcast

The skill walks the agent through a six-step pipeline:

1. **URL → PDF** — Renders the page with a throwaway Gotenberg container
2. **PDF → raw text** — Extracts text from the PDF
3. **LLM reformat** — Strips page chrome and rejoins column-wrap line breaks while preserving body prose verbatim
4. **Text → WAV** — Synthesises speech with Kokoro-82M (multiple voices available)
5. **LLM metadata extraction** — Pulls a `{title, artist, description, date}` JSON object from the cleaned text
6. **WAV → M4A** — Packages the audio with metadata for podcast players

If you already have a PDF, start at step 2. If you already have plain text, start at step 3.

You can also trigger the skill using natural language:

> Use the Text to Podcast skill to turn this article into a podcast episode.

## How It Works

Four Python scripts (run with `uv`, dependencies declared inline via PEP 723):

- **`scripts/web2pdf.py`** — Renders a URL to PDF using a throwaway [Gotenberg](https://gotenberg.dev/) docker container. Supports a `WAIT_DELAY` env var for slow / JS-heavy pages.
- **`scripts/pdf2txt.py`** — Extracts plain text from a PDF.
- **`scripts/tts.py`** — Synthesises speech with the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) TTS model. Splits on blank lines to stream long inputs paragraph by paragraph.
- **`scripts/wav2m4a.py`** — Encodes WAV to M4A with `ffmpeg` and embeds title, artist, album, date, description, and genre metadata.

The two LLM-driven steps (reformat and metadata extraction) are handled by the agent itself, using the prompts in `assets/`:

- **`assets/reformat-prompt.md`** — Rules for removing page chrome and rejoining PDF column-wrap line breaks without paraphrasing or reordering body content.
- **`assets/metadata-prompt.md`** — Rules for extracting `title`, `artist`, `description`, and `date` as a single JSON object.

## Example prompts

> Turn this Simon Willison post into an M4A I can listen to in my podcast app: https://simonwillison.net/2026/feb/14/the-mythical-agent-month/

> I have a PDF of a long research paper, can you produce a podcast version with proper metadata?

> Convert the cleaned-up article in `article.clean.txt` to speech using the male voice.

> Generate the cover-text metadata for this article and package the WAV I already have into an M4A.

## Troubleshooting

- **`espeak-ng` not found** — Kokoro needs it for phonemization. `brew install espeak-ng`.
- **`docker` not found** — only needed for step 1. If you already have a PDF or text, skip `web2pdf.py` entirely.
- **`ffmpeg` not found** — `brew install ffmpeg`.
- **Page loaded blank in step 1** — bump `WAIT_DELAY` (e.g. `WAIT_DELAY=15s uv run --script scripts/web2pdf.py …`).
- **Robotic prosody** — try `--voice male` or nudge `--speed` down to `0.95`.
- **Out of memory on long inputs** — the TTS script splits on blank lines; if a single paragraph is still too big, break it up in the cleaned text file.

## Acknowledgements

- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad — the TTS model that does the heavy lifting in `scripts/tts.py`.
- [Gotenberg](https://gotenberg.dev/) — the headless Chromium / LibreOffice service that `scripts/web2pdf.py` drives for URL → PDF rendering.

## License

[MIT](LICENSE)
