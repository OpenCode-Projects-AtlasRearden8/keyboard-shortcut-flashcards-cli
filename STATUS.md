# STATUS

**Project:** Shortcut Flashcards CLI
**Version:** 0.1.0
**Date:** 2026-11-08
**Built by:** Asdale Dynamics, LLC (for Dylan Asdale's beginner-friendly, local-first tool collection)

## What was built

A terminal app for daily keyboard-shortcut memory drills — the "recall, reveal,
grade" card model with spaced repetition, wrapped in a standard pip-installable
Python package (`shortcut_flashcards`, MIT licensed, stdlib only, zero runtime
dependencies, fully offline).

Components (`src/shortcut_flashcards/`):

- **`deck.py`** — CSV deck loader and parser: builtin decks packaged as CSV
  resources (`builtin_decks/*.csv`), plus any user CSV file. Validates rows,
  tolerates comments/blank lines/headers/BOM/quoted commas, and raises precise
  line-numbered errors. This is the most-strictly-tested module (per project
  brief: fully tested deck loader).
- **`scheduler.py`** — SM-2-lite spaced repetition: ease factor (1.3–2.8),
  intervals 1 → 6 → interval×ease days, `again` resets learning and resurfaces
  the card inside the current session, day-precision due dates.
- **`store.py`** — local JSON persistence (`state.json`), atomic saves via
  temp file + rename, per-deck reset, corrupt-file recovery (starts fresh),
  `SHORTCUT_FLASHCARDS_HOME` env override.
- **`session.py`** — the two-minute drill runner: due-first queue capped at 10
  new cards, injectable clock/input/output for testing, in-session requeue of
  missed cards, streak/accuracy summary.
- **`cli.py`** — argparse front end with `decks`, `show`, `run`, `stats`,
  `reset` subcommands, `--home`, `--minutes`, `--shuffle`, `--version`.

Built-in decks (all validated): Windows (37 cards), macOS (30), VS Code (30),
Vim (36), Emacs (28). An `examples/example-deck.csv` (Final Fantasy XIV chat
commands) demonstrates loading custom CSV decks.

## How to run

```sh
pip install .                            # Python 3.10+, no dependencies
shortcut-flashcards decks                # list builtin decks
shortcut-flashcards run windows          # default 2-minute drill
shortcut-flashcards run examples/example-deck.csv   # your own CSV deck
shortcut-flashcards show vim             # print reference list
shortcut-flashcards stats                # progress summary
shortcut-flashcards reset windows        # clear a deck's schedule
```

State file: `~/.local/share/shortcut-flashcards/state.json`
(override: `SHORTCUT_FLASHCARDS_HOME=...` or `--home DIR` before the subcommand).
No secrets, no network calls, no telemetry.

## Verification results

- `python3 -m pytest` — **89 tests, all passing** covering the deck loader
  (malformed rows, quoting, BOM, duplicates, header/comment handling, builtin
  integrity), scheduler (interval math, ease clamps, lapse handling, due
  ordering), store (roundtrip, case-insensitive deck keys, reset, corrupt
  file recovery, env override), session runner (grade flows, requeue on
  failure, time-budget termination, EOF/quit paths, new-card cap, queue
  ordering, shuffle), and CLI (exit codes, clean error messages, state
  creation, reset/stats flows).
- `ruff check .` — clean (0 findings).
- Installed editable (`pip install -e .`) and smoke-tested the real console
  script: `--version`, `decks`, `show windows`, and a scripted interactive
  `run vscode` session (reveal → grade → quit) followed by `stats`, showing
  counts updated correctly ("due now: 28 | scheduled (not due): 2").
- Package data (builtin CSVs) confirmed importable via `importlib.resources`.

## Known gaps

- Self-grading only: the session does not verify that you typed/pressed the
  actual shortcut (matching typed shortcuts across OS keyboard layouts is
  brittle; a typed-answer mode could be a future `--type` option).
- Deck editing is out of scope — edit CSVs in any editor; no in-app add card.
- No import from other SRS apps (e.g. Anki export); JSON state is internal.
- macOS deck entries are US-keyboard-centric; non-QWERTY layouts may differ.
- No pip dependency resolution issues currently (stdlib only), but no CI
  pipeline exists yet in this repository.
- Unicode card content is fine, but `show` output columns assume monospace.
