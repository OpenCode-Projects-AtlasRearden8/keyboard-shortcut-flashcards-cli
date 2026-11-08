# Shortcut Flashcards

Daily keyboard-shortcut memory drills in your terminal — a tiny, offline,
spaced-repetition flashcard trainer from [Asdale Dynamics, LLC](https://dylanasdale.github.io).

Recall the shortcut, reveal the answer, grade yourself honestly, and the
scheduler decides when each card comes back. Two minutes a day is enough.

## Why this exists

- **Windows**, **macOS**, **VS Code**, **Vim**, and **Emacs** decks are built in.
- Load **your own deck** from any CSV file (`shortcut,description` lines).
- **Spaced repetition** (SM-2-style) reminds you of weak cards first.
- The default **two-minute session** fits inside a coffee refill.
- 100% offline, no accounts, no telemetry, one JSON file of progress.

## Install

```sh
pip install .            # from a checkout of this repository
```

Python 3.10+ is required. There are no dependencies.

## Quick start

```sh
shortcut-flashcards decks               # list the builtin decks
shortcut-flashcards run windows         # a 2-minute drill
shortcut-flashcards run vscode
shortcut-flashcards show vim            # study reference list
shortcut-flashcards stats               # progress overview
shortcut-flashcards reset windows       # forget a deck's history
```

Run your own CSV deck:

```sh
shortcut-flashcards run examples/example-deck.csv
```

CSV format (one card per line, `#` comments allowed, UTF-8):

```csv
shortcut,description[,optional note]
Ctrl+D,"Select the word at the cursor"
Win+V,Clipboard history,works after enabling once
```

## How a session works

1. Cards you failed recently come back first, then cards whose due date
   arrived, then a few brand-new cards.
2. You see the description, press Enter to reveal the shortcut, and grade
   yourself: `y` good, `n` again, `e` easy, `q` quit.
3. Wrong answers are re-queued within the session.
4. Progress is saved to `~/.local/share/shortcut-flashcards/state.json`
   (override with `SHORTCUT_FLASHCARDS_HOME`, or the `--home` flag before
   the subcommand).

## Scripting

The CLI is plain and quiet, so it composes well:

```sh
# scheduled daily drill, results captured
shortcut-flashcards run windows --minutes 2 >> drills.log 2>&1

# CI-style sanity check of any CSV deck
shortcut-flashcards show mydeck.csv > /dev/null
```

## Development

```sh
python3 -m pytest           # 89 tests cover the loader, scheduler, store, session, CLI
ruff check .
```

Source layout: `src/shortcut_flashcards/` (`deck.py` loader, `scheduler.py`
SM-2-lite, `store.py` JSON persistence, `session.py` drill runner,
`cli.py` terminal interface).

## Related projects

Distinct from a typing-speed trainer (raw WPM) — this one is about
**remembering**, one card at a time.

Copyright (c) 2026 Asdale Dynamics, LLC. MIT licensed — see `LICENSE`.
