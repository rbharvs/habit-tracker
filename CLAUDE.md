# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commit Messages

- Imperative mood, ~50 char title (e.g., "Add habit storage layer")
- Succinct body with details if needed
- Don't reference plan phases in commits

## Commands

```bash
make fix        # Format + lint + typecheck (run before committing)
make test       # Run all tests
make dev        # Start dev server at localhost:8000
make help       # Show all available commands
```

Run a single test:
```bash
uv run pytest tests/test_models.py::test_binary_habit_creation -v
```

## Dependencies

Use `uv add` and `uv remove` to manage dependencies - never edit pyproject.toml directly when adding/removing dependencies:

```bash
uv add requests              # Add a runtime dependency
uv add --dev pytest-cov      # Add a dev dependency
uv remove requests           # Remove a runtime dependency
uv remove --dev pytest-cov   # Remove a dev dependency
```

## Architecture

Personal habit tracker with FastAPI backend, HTMX frontend, JSON file storage.

### Data Model

Uses Pydantic discriminated unions for type-safe polymorphism:

- **Habits** (`Habit` type): `BinaryHabit`, `SingleSelectHabit`, `JournalHabit` - distinguished by `type` field
- **Entries** (`HabitEntry` type): `BinaryEntry`, `SingleSelectEntry`, `JournalEntry` - parallel structure

When handling habits/entries, use exhaustive `match`/`case` with `assert_never` for the default case.

### Storage

- `data/config.json` - habit definitions
- `data/entries/YYYY-MM-DD.json` - daily entries

The `data/` directory is gitignored (user data).

### Key Files

- `src/habit_tracker/models.py` - Pydantic models with discriminated unions
- `src/habit_tracker/storage.py` - JSON file operations
- `src/habit_tracker/main.py` - FastAPI routes (Phase 2)
