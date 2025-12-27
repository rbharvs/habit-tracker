# Habit Tracker

Personal habit tracker with a FastAPI backend and HTMX frontend.

## Features

- **Binary habits** - Yes/no tracking (e.g., "Did you exercise?")
- **Single-select habits** - Choose from options (e.g., mood: great/good/okay/bad)
- **Journal habits** - Free-form text entries
- Auto-save with HTMX
- Date navigation for past entries
- Keyboard-friendly (tab navigation, Ctrl+Enter to save)
- Mobile-friendly interface

## Quick Start

```bash
make dev      # Start server at localhost:8000
make test     # Run tests
make fix      # Format + lint + typecheck
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
