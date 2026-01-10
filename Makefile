# ClaimVoice developer tasks. Everything runs offline: no Docker, no accounts, no keys.
# Ports: web 3040 · API 8040 (the voice runtime runs inside the API process; 8041-8044 reserved).
# On small machines run heavy targets (setup, test, train, eval, web) one at a time.
PY      := backend/.venv/bin/python
BPY     := .venv/bin/python
NPM     := npm --prefix frontend
LINT    := backend scripts eval
export MLFLOW_DISABLE_AGENT_HINT := 1

.PHONY: help setup setup-backend setup-ai setup-frontend lock data api web web-dev dev migrate seed reset \
        test test-backend test-frontend lint format typecheck eval train train-nlu smoke stop clean

help:            ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: setup-backend setup-frontend  ## Install API + web app, create .env, migrate and seed
	@test -f .env || cp .env.example .env
	$(MAKE) migrate seed

setup-backend:   ## Python 3.13 venv with the pinned lock (+ the package, editable)
	@if [ "$$(uname -s)" = "Darwin" ] && [ ! -f /opt/homebrew/opt/libomp/lib/libomp.dylib ] && [ ! -f /usr/local/opt/libomp/lib/libomp.dylib ]; then \
	  echo "XGBoost needs libomp on macOS: run 'brew install libomp' and re-run make setup."; exit 1; fi
	test -d backend/.venv || python3.13 -m venv backend/.venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r backend/requirements.lock
	$(PY) -m pip install -q --no-deps -e "backend[dev]"

setup-ai:        ## Optional: LiteLLM for cloud language understanding (LLM_FAKE=false + a free-tier key)
	$(PY) -m pip install -q "litellm==1.109.1"

setup-frontend:  ## Install the web app (exact versions from package-lock.json)
	$(NPM) ci --no-audit --no-fund

lock:            ## Re-freeze backend/requirements.lock from the current venv (after changing pyproject pins)
	@{ echo "# Frozen from a clean Python 3.13 install of pyproject.toml core + dev dependencies."; \
	   echo "# Regenerate with: make lock"; \
	   $(PY) -m pip freeze --exclude-editable | grep -v '^claimvoice'; } > backend/requirements.lock

data:            ## Download freMTPL2 from OpenML into data/fremtpl2 (~8 MB, checksum-pinned)
	$(PY) scripts/fetch_data.py

api:             ## API + voice runtime on :8040
	cd backend && $(BPY) -m uvicorn claimvoice.api.app:app --host 127.0.0.1 --port 8040 --no-access-log

web-dev:         ## Nuxt dev server on :3040 (proxies /api to :8040)
	$(NPM) run dev

web:             ## Production build of the web app, served on :3040
	$(NPM) run build && $(NPM) run preview

dev:             ## API + web dev server (Ctrl-C stops both)
	@$(MAKE) -j2 api web-dev

migrate:         ## Apply database migrations
	cd backend && $(BPY) -m claimvoice.cli migrate

seed:            ## Seed Larkspur Mutual (idempotent; dated by CLAIMVOICE_DEMO_TODAY)
	cd backend && $(BPY) -m claimvoice.cli seed

reset:           ## Delete the local database, then migrate and seed
	cd backend && $(BPY) -m claimvoice.cli reset --yes

test: test-backend test-frontend  ## All tests

test-backend:    ## API, platform, dialogue, voice, ML and QA tests (no servers needed)
	cd backend && $(BPY) -m pytest

test-frontend:   ## Web app lint, type check, unit tests and production build
	$(NPM) run lint && $(NPM) run typecheck && $(NPM) test && $(NPM) run build

lint:            ## Lint and format checks (ruff)
	$(PY) -m ruff check $(LINT)
	$(PY) -m ruff format --check $(LINT)

format:          ## Apply ruff formatting and safe fixes
	$(PY) -m ruff format $(LINT)
	$(PY) -m ruff check --fix $(LINT)

typecheck:       ## mypy (backend) + nuxt typecheck (web)
	cd backend && $(BPY) -m mypy claimvoice
	$(NPM) run typecheck

eval:            ## Evaluation gates -> eval/RESULTS.md (dialogue, latency, models, call quality)
	cd backend && $(BPY) ../eval/run.py

train:           ## Train the routing checks (tracked in mlruns/) and the loss-type reader (CPU, seeded)
	cd backend && $(BPY) -m claimvoice.ml.train all
	$(MAKE) train-nlu

train-nlu:       ## Train only the loss-type classifier of the offline reader (seconds; nlu/artifacts/)
	cd backend && $(BPY) -m claimvoice.nlu.train

smoke:           ## Re-verify the toolchain: Pipecat SmallWebRTC + Silero VAD, and the ML stack on freMTPL2
	$(PY) scripts/smoke/voice_smoke.py
	@test -f data/fremtpl2/freMTPL2freq.parquet || $(MAKE) data
	$(PY) scripts/smoke/ml_smoke.py

stop:            ## Stop every ClaimVoice process started from this repo
	-pkill -f 'uvicorn claimvoice.api.app' ; pkill -f 'nuxt dev --port 3040' ; pkill -f 'frontend/.output/server/index.mjs' ; true
	@for p in 3040 8040 8041 8042 8043 8044; do lsof -ti :$$p >/dev/null 2>&1 && echo "port $$p still in use" || true; done

clean:           ## Remove caches and build output (keeps data/ and the venv)
	find $(LINT) -path '*/.venv' -prune -o -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -r {} + 2>/dev/null || true
	rm -rf .ruff_cache .mypy_cache .pytest_cache frontend/.nuxt frontend/.output eval/out
