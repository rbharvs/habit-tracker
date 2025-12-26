.PHONY: help fix format lint typecheck test dev browser clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

fix: format lint typecheck  ## Run all fixes (format + lint + typecheck)

format:  ## Format code with ruff
	uv run ruff format src/ tests/

lint:  ## Lint and auto-fix with ruff
	uv run ruff check --fix src/ tests/

typecheck:  ## Type-check with ty
	uv run ty check src/

test:  ## Run tests with pytest
	uv run pytest tests/ -v

dev:  ## Run development server with auto-reload
	uv run uvicorn habit_tracker.main:app --reload

browser:  ## Open the app in the default browser
	open http://localhost:8000 || xdg-open http://localhost:8000 2>/dev/null

clean:  ## Remove generated files
	rm -rf .pytest_cache .ruff_cache __pycache__ src/**/__pycache__
