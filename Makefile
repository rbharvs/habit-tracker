.PHONY: help fix check format lint typecheck test dev browser clean build deploy snapshot-update snapshot-check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

fix: format lint typecheck  ## Run all fixes (format + lint + typecheck)

check:  ## Check code (CI mode - no auto-fix)
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run ty check src/

format:  ## Format code with ruff + generate requirements.txt
	uv run ruff format src/ tests/
	@uv export --no-dev --no-hashes --no-emit-project -o src/requirements.txt > /dev/null 2>&1

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

build:  ## Build SAM application (uses container locally, skips on CI/Linux)
	uv run sam build $$([ -z "$$CI" ] && echo "--use-container")

deploy: fix build  ## Deploy to AWS Lambda (requires env vars from .env)
	uv run sam deploy --parameter-overrides "AllowedIPs=$(ALLOWED_IPS)" "DomainName=$(DOMAIN_NAME)" "CertificateArn=$(CERTIFICATE_ARN)"

snapshot-update:  ## Update snapshot files
	uv run pytest tests/test_snapshots.py --snapshot-update

snapshot-check:  ## Check for unused snapshots
	uv run pytest --snapshot-warn-unused
