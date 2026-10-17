---
name: sparkrun-index-table-row-edit
description: "Edit or insert a row in the root README.md's hand-aligned index tables (sparkrun-recipe-registry) without breaking the file's one-width-per-column convention, and verify it row-level."
---

# Editing a row in the sparkrun registry index

The root `README.md`'s lane tables are hand-aligned: each column has ONE character width
across header, separator and every data row, and the last column absorbs the difference so
all rows of a table have equal total length. Ragged rows get noticed.

## Procedure

1. **Locate the table by its section heading**, never by its header pattern: several tables
   share the identical `| Recipe | Flags | C1 t/s | …` header line. Take the `## Qwen 4x`-style
   heading, then the first following line that starts with `| Recipe`.
2. Take the table's range as **every consecutive line starting with `|`** from that header
   (the first non-pipe line is the footnote block).
3. Measure widths from the raw split. `line.split("|")` has a leading empty element, so a
   cell's index is +1 versus `line.split("|")[1:-1]` — off-by-one here silently targets the
   flags cell instead of C1.
4. The new width for a column is `max(existing widths, new cell) + 2` (one space each side of
   the cell). **Widening means repadding that column in the header, the separator AND every
   data row** — never just the new row.
5. Keep every other cell byte-identical: copy the `—` cell, the flags/emoji cell, and the text
   cells verbatim from a sibling row of the *same* table. **Never copy a sibling's numeric
   cell into an unmeasured arm's row** — an unmeasured C1 is `—`, and a copied `40.3` is a
   fabricated measurement.
6. Style: numbers right-aligned inside their cell (`|   40.3 |`), flags and text left-aligned,
   and the separator keeps the alignment markers the existing row uses (`:------` / `-------:`).
7. Prefer minimal edits (only the changed columns) over rebuilding the table — a rebuild
   silently loses the alignment style of every cell it rewrites.

## Verification (this is the step that catches mistakes)

Re-read the file from disk, slice **every line from the header to the first non-pipe line,
including the row just added**, and assert:

- each column index has exactly one distinct cell length (skip the flags column only if that
  table already varies there),
- `len({len(line) for line in table}) == 1`,
- then print the table back and look at it.

A check that samples a fixed range (e.g. `sep+2..sep+5`) or that ran before the write passes
while the file is broken. Also re-verify numbers *per arm*: a row that reads plausibly is the
failure mode.

## Traps hit for real (2026-10-15)

- Header search matched the Qwen **3x** table first; the row landed in the wrong section and
  broke its width (277 chars vs 276, unpadded 49-char name).
- A `cell(text, w)` helper that falls back to `" " + text` when the text exceeds the column
  left the column ragged instead of widening it.
- Copying a sibling row's cells wholesale put the base arm's C1 (`40.3`) into an unmeasured
  arm's row; nothing in the arithmetic looked wrong.
- A full table rebuild produced consistent widths but flattened right-aligned numerics and
  rewrote separator markers — visible in `git diff`, invisible to a width check.
