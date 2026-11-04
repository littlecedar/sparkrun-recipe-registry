"""Tests for the campaign driver package.

Run from the repository root:

    uv run --project campaign --frozen python -B -m unittest discover -s campaign/tests -t campaign

`-t campaign` is what puts `sparkrun_campaign/` on `sys.path` (the package is not installed; see
`DESIGN.md` §Dependencies). The same command is the CI step in `.github/workflows/gate.yml`.
"""