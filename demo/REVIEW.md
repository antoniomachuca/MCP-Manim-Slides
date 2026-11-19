# Review: MCP-Manim-Slides demo film (40 s)

## Creative calls
- One storyline, taken from the two reference films the person gave (light question pill, a
  "By hand / With the MCP" toggle, a dark Claude Code session with a result card, a light end card
  with the install command and a Star click). No alternative storylines were built.
- Content chosen to show what the server does that a plain script does not: live render progress
  (`execute_manim_code`), the agent reviewing its own deck (`contact_sheet`), a one-scene fix, and
  per-scene caching (`sync_deck` re-renders only `SquareProof`), then `export_video`.
- Everything in the terminal comes from a real run of the tools (`manim/mcp_results.json`). Display
  edits: paths shown as `/Users/you/decks`, each result trimmed to the keys that matter plus the
  real "+N lines" count, progress messages sampled from the real stream.
- The deck (`manim/pythagoras.py`) was rewritten for the film: unit-cell squares on each side, and
  the 9 + 16 cells fly into the 25-cell square.

## Measured
- `hyperframes check`: no errors.
- Rendered audio: -15.2 LUFS integrated, -2.1 dBTP, no clipping. Measured, not listened to.

## Kept warnings
- `text_below_floor` in `byhand`: the scrolling code and shell are texture; the counter and the
  commands carry the read.
- `line_unread` on the typed prompt: it stays on screen afterwards as the history line.
- `nested_media_start_basis_ambiguous`: `data-start="0.25"` on the deck video is local on purpose.

## Weakest shot
- `byhand`: the two windows sit small in the frame. With more time I'd push in on the shell as the
  commands run.
- No music bed. Sign in (`npx hyperframes auth login`) for the catalog and lay one under it.
