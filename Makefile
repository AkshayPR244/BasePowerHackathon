SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PY := cd backend && PYTHONPATH=. uv run
FE := cd frontend && pnpm

LANE_A_PATHS := app/data app/valuation app/validate tests/lane_a
LANE_B_PATHS := app/planning app/baselines app/compare app/api tests/lane_b
LANE_R_PATHS := app/recovery app/baselines app/planning tests/lane_r
LANE_H_PATHS := app/api tests/lane_h ../scripts

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: ## Install backend and frontend deps
	cd backend && uv sync
	[ -f frontend/package.json ] && $(FE) install || echo "frontend/package.json missing: lane C creates it"
	[ -f frontend/package.json ] && (cd frontend && pnpm exec playwright install chromium) || true

dev: ## Frontend on :5173 against recorded mocks (no backend needed)
	$(FE) dev

dev-live: ## Backend on :8000 plus frontend proxied to it
	trap 'kill 0' EXIT; \
	(cd backend && uv run uvicorn app.api.main:app --reload --port 8000) & \
	(cd frontend && VITE_API_MODE=live pnpm dev) & \
	wait

api: ## Backend only on :8000
	cd backend && uv run uvicorn app.api.main:app --reload --port 8000

check: check-contracts check-backend check-c ## Everything CI would run

check-contracts: ## Contract round-trips, lane boundaries, and a stale openapi.json
	$(PY) pytest -q tests/contract
	$(PY) python ../scripts/export_openapi.py --check

check-a: ## Lane A: lint + tests
	$(PY) ruff check $(LANE_A_PATHS)
	$(PY) ruff format --check $(LANE_A_PATHS)
	$(PY) pytest -q tests/lane_a tests/contract

check-b: ## Lane B: lint + tests
	$(PY) ruff check $(LANE_B_PATHS)
	$(PY) ruff format --check $(LANE_B_PATHS)
	$(PY) pytest -q tests/lane_b tests/contract

check-r: ## Lane R: lint + tests
	$(PY) ruff check $(LANE_R_PATHS)
	$(PY) ruff format --check $(LANE_R_PATHS)
	$(PY) pytest -q tests/lane_r tests/contract

check-h: ## Lane H: backend lint + tests
	$(PY) ruff check $(LANE_H_PATHS)
	$(PY) ruff format --check $(LANE_H_PATHS)
	$(PY) pytest -q tests/lane_h tests/contract

check-backend: ## Whole backend: ruff on app, tests, and scripts, then every test suite
	$(PY) ruff check . ../scripts
	$(PY) ruff format --check . ../scripts
	$(PY) pytest -q

check-c: ## Lane C: typecheck, unit tests, build
	$(FE) typecheck
	$(FE) test
	$(FE) build

e2e: ## Lane C: Playwright against mocks, saves screenshots
	$(FE) e2e

types: ## Regenerate contracts/openapi.json and frontend/src/api/generated.ts
	$(PY) python ../scripts/export_openapi.py
	./scripts/gen_types.sh

mocks: ## Re-record MSW responses from the in-process API
	$(PY) python ../scripts/record_mocks.py

demo: ## Planned: reset demo data and run the live app
	$(MAKE) mocks
	$(MAKE) dev-live

.PHONY: help setup dev dev-live api check check-contracts check-a check-b check-r check-h check-backend check-c e2e types mocks demo
