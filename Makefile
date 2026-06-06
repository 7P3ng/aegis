VENV := .venv/bin
.PHONY: install test lint type pytest eval-dry eval-live ui-build clean

install:
	python -m venv .venv && $(VENV)/pip install -e ".[dev]"

lint:
	$(VENV)/ruff check core redteam evals tests

type:
	$(VENV)/mypy core redteam evals

pytest:
	$(VENV)/pytest -q

test: lint type pytest

eval-dry:
	$(VENV)/python -m evals.run_gauntlet --dry-run

eval-live:
	$(VENV)/python -m evals.run_gauntlet --live --target deepseek

ui-build:
	cd ui && npm install && npm run build

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__ *.db
