
You receive raw text extracted from a PDF by pypdf, destined for a text-to-speech engine. Your job is to fix whitespace AND strip inline page chrome.

You MUST preserve every word, punctuation mark, and character of BODY content verbatim — no rewriting, no summarizing, no paraphrasing, no reordering of body text. The ONLY content you may delete is inline page chrome as defined in rule 5.

Defects you must handle:
- Most newlines are PDF column-wrap breaks at ~60–80 chars (mid-sentence).
- Blank lines may be real paragraph breaks, PDF page boundaries, or both.
- Section headings may be split across two source lines, sometimes mid-word at a hyphen (e.g. `The Mythical Agent-\nMonth` → `The Mythical Agent-Month`).
- Inline page chrome appears mid-flow: ad blocks, site navigation, tag/category lists, copyright footers.
- A sentence may be physically interrupted by chrome (e.g. `…pejorative "prompt / [nav block + ad] / and chill"…`). After removing the chrome, rejoin the two halves into one continuous sentence.

Rules:
1. Join PDF-wrap line breaks within a paragraph. Each paragraph becomes one continuous line.
2. A blank line in the input usually marks a paragraph boundary; output exactly ONE blank line between paragraphs.
3. EXCEPTION to rule 2: if the line before a blank ends without sentence-final punctuation (no `.`, `?`, `!`, `:`, `"`, `)`) and the line after the blank clearly continues the same clause, treat the blank as a stray PDF page boundary and JOIN — do not paragraph-break.
4. Headings are short lines (1–10 words, title case or capitalized, not ending in `.`, `?`, or `!`) that introduce a new section. Put each heading on its own line with one blank line above AND one blank line below. If a heading is split across two source lines — including mid-word at a hyphen — rejoin them onto one line before isolating.
5. STRIP inline page chrome from the output. REMOVE (do not include in output):
   - Advertisement blocks (e.g. `Union.ai: ... www.union.ai`, `Ads by EthicalAds`, sponsor sidebars).
   - Site navigation menus (e.g. `Home About Posts`, run-together nav strings like `Wes McKin…HomeSoftwareBookSpicy Takes BlogTalks & Media`).
   - Tag / category lists (e.g. `Career   Open leadership   Culture`, `AI AGENTS THOUGHTS` — short capitalized terms separated by spaces or wide gaps that don't form a sentence).
   - Copyright / legal footers (`© 2026 …`, "All rights reserved", reproduction notices).
   When chrome interrupts a sentence, remove the chrome and join the two halves of the sentence into one continuous paragraph.
   KEEP (these are content, each on its own paragraph): titles, author bylines, dates, `tl;dr:` lines, image captions, block quotes, `Sidenote:` insets.
6. Block quotes and `Sidenote:` insets become their own paragraphs separated by single blank lines.
7. For all non-chrome content, preserve every word and character of the input verbatim.

Output ONLY the reformatted text. No preamble, no explanation, no code fences, no markdown.
