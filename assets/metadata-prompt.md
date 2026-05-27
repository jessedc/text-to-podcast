You receive cleaned article or document text. Extract podcast metadata from it.

Output ONLY a single JSON object with exactly these four fields:

- `title` — the article or document title, taken verbatim from the text (usually the first heading or an explicit title line). Required.
- `artist` — the primary author byline if present (e.g. "by Jane Doe"); if multiple authors, join them with `, ` in a single string; if no author is discoverable, use `"Unknown"`.
- `description` — a neutral 1–2 sentence summary of the piece, written in the third person, at most 280 characters. No marketing tone, no first-person, no rhetorical questions.
- `date` — publication date as `YYYY-MM-DD` if discoverable in the text; otherwise the empty string `""` (the caller will substitute today's date).

Rules:
- Emit ONLY the JSON object. No preamble, no trailing commentary, no code fences, no markdown.
- Use straight ASCII double quotes (`"`). Escape any internal double quotes with `\"`.
- No trailing comma after the last field.
- Order fields as listed above.

Example input (excerpt):

```
The Mythical Agent-Month

by Simon Willison · 2026-02-14

When teams add more AI agents to a stalled project, they often expect linear
speedups. In practice, coordination overhead grows faster than throughput…
```

Expected output:

```
{"title": "The Mythical Agent-Month", "artist": "Simon Willison", "description": "Simon Willison argues that adding more AI agents to a stalled project rarely produces linear speedups, because coordination overhead grows faster than throughput.", "date": "2026-02-14"}
```
