.PHONY: install test lint typecheck check demo site examples

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

check: lint typecheck test

demo:
	uv run shule-timetable demo --school secondary --out out/secondary

# Rebuild the committed sample inputs from the deterministic generator.
examples:
	uv run python -m shule_timetable.demo --write-examples examples

# Render the static sample site from the committed solutions (what GitHub Pages publishes).
site:
	uv run shule-timetable report examples/secondary --solution examples/secondary/solution.json --out site/secondary
	uv run shule-timetable report examples/primary --solution examples/primary/solution.json --out site/primary
