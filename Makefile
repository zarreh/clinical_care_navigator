.PHONY: run dev test lint typecheck imports check eval eval-live up down data docs docs-assets docs-screenshots frontend-dev frontend-build frontend-types frontend-e2e

# API on :8000 and frontend on :3000; Ctrl-C stops both.
run:
	@[ -d frontend/node_modules ] || (cd frontend && npm install)
	@trap 'kill 0' INT TERM EXIT; \
	uv run uvicorn navigator.api.main:app --port 8000 --timeout-graceful-shutdown 2 & \
	(cd frontend && npm run dev) & \
	wait

dev:
	uv run uvicorn navigator.api.main:app --reload --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

imports:
	PYTHONPATH=src uv run lint-imports

check: lint typecheck imports test

eval:
	uv run python -m evals.run

# Real model, needs NAVIGATOR_OPENAI_API_KEY and spends tokens; `eval` is the key-free CI gate.
eval-live:
	uv run python -m evals.run_live

up:
	docker compose up --build

down:
	docker compose down

data:
	uv run python -m data.fetch_synthea
	uv run python -m data.build_store
	uv run python -m data.render_notes
	uv run python -m data.fetch_education
	uv run python -m data.generate_policy_rules
	uv run python -m data.scenarios

docs:
	uv run mkdocs serve

docs-assets:
	PYTHONPATH=. uv run python docs/generate_plots.py

docs-screenshots:
	cd frontend && npx playwright test capture-screenshots.spec.ts

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-types:
	PYTHONPATH=src uv run python -c "from navigator.api.main import app; import json; json.dump(app.openapi(), open('frontend/openapi.json', 'w'), indent=2)"
	cd frontend && npm run gen:types

frontend-e2e:
	cd frontend && npx playwright test conversation.spec.ts
