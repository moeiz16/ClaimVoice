# ADR 0001: Toolchain, verified on the target machine

**Status:** accepted

## Context
ClaimVoice must run on a laptop with 8 GB of RAM and limited disk, on Python 3.13 and Node 21.7, with no Docker, no
paid services and no local language or speech models. Before fixing the contract we checked every load-bearing
dependency by installing it and running it, not by reading release notes.

## What we checked and found

| Question | Result | Evidence |
|---|---|---|
| Does `pipecat-ai` with the SmallWebRTC transport install on Python 3.13 / macOS arm64 without heavy dependencies? | **Yes.** `pipecat-ai==1.16.0` + `aiortc==1.16.0`. No PyTorch: torch is only pulled by the `local-smart-turn` extra, which we do not use | `scripts/smoke/voice_smoke.py`: WebRTC offer/answer with a plain aiortc peer, data channel opens in ~0.1 s, JSON round trip < 1 ms, 40 audio frames received in 1 s; peak memory ~150 MB |
| Which extras? | We install `aiortc` directly instead of `pipecat-ai[webrtc]`. The extra also pulls `opencv-python-headless` (~120 MB) for video, which the transport only imports lazily for video tracks | same smoke run, with OpenCV uninstalled |
| Silero VAD? | **Fine.** Pipecat ships the Silero ONNX model (2.3 MB) and depends on `onnxruntime` (~85 MB installed); about 0.1 ms of CPU per 32 ms chunk | same smoke run |
| Pipecat API shape | 1.x renamed `PipelineTask`/`PipelineRunner` to `PipelineWorker`/`WorkerRunner` (old names deprecated). The browser must send `ping-…` text on the data channel about once a second once it starts, or the server treats the caller as gone after 3 s | smoke code; `pipecat/transports/smallwebrtc/connection.py` |
| Pipecat's request handler | `SmallWebRTCRequestHandler` imports FastAPI. We call `SmallWebRTCConnection` directly from Litestar instead (offer → `initialize` → `get_answer`; ICE via `add_ice_candidate`) | smoke code |
| Litestar 2.x + SQLAlchemy 2 + Alembic on 3.13? | **Yes.** `litestar==2.25.0`, `SQLAlchemy==2.1.8` (async, aiosqlite), `alembic==1.20.1`; initial migration applies and `alembic check` reports no drift | `backend/tests`, CI |
| Litestar middleware and 404s | Route middleware does not wrap unmatched routes, so a 404 would miss `X-ClaimVoice-Now`. We add response headers in an app-level `before_send` hook instead | `api/middleware.py`, `tests/test_api.py` |
| Is freMTPL2 reachable, and under what licence? | **Yes.** OpenML 41214 (`freMTPL2freq`) and 41215 (`freMTPL2sev`) download as Parquet (7.5 MB + 0.3 MB); OpenML lists CC0, the original CASdatasets package is GPL-2+. We download at setup and never redistribute | `scripts/fetch_data.py`, checksums in `scripts/data_pins.json` |
| Reading Parquet without PyArrow | `fastparquet` (+ cramjam, ~6 MB) instead of `pyarrow` (~100 MB+) | `scripts/smoke/ml_smoke.py` |
| XGBoost, Optuna, SHAP, MLflow on 3.13 arm64? | **Yes.** `xgboost==3.4.1` (needs Homebrew `libomp`), `optuna==5.0.0`, `shap==0.54.1`, `mlflow-skinny==3.18.0` with a SQLite tracking store, `scikit-learn==1.9.1`. Smoke on freMTPL2 claims: 8 s, peak ~360 MB | `scripts/smoke/ml_smoke.py` |
| Does Nuxt 3 build on Node 21.7? | **Yes, with the right minor.** Nuxt 3.18 and later need Node ^20.19 or ≥ 22.12 (Vite 7 uses `require(esm)`). **Nuxt 3.17.7 on Vite 6.4** installs and builds on Node 21.7.1; npm prints engine warnings for a few transitive packages (Nitro 2.13, unplugin 3) that run fine. Lint, `nuxt typecheck`, Vitest and the production build all pass | `frontend/`, `make test-frontend` |
| Nitro proxy route rules | `routeRules: { proxy }` does not type-check with this Nuxt/Nitro pair; a typed server route (`server/routes/api/[...].ts` with `proxyRequest`) forwards `/api/**` instead and streams SSE | `frontend/server/routes/api/[...].ts` |
| Browser speech in Chrome on macOS | `SpeechRecognition` is available unprefixed; `SpeechRecognition.available({ langs: ["en-CA"|"fr-CA"], processLocally: true })` returns `downloadable` (an on-device pack can be installed) and the cloud path returns `available`. `speechSynthesis` lists ~180 local voices including several fr-CA voices. So the offline demo can speak locally, and recognition is on-device once the language pack is installed, otherwise it uses the browser's own service (no key, no account) | headless Chrome probe with playwright-core |

## Decision
Pin these versions (`backend/pyproject.toml`, frozen in `backend/requirements.lock`; `frontend/package.json` exact
pins with `package-lock.json`):

- Python: `pipecat-ai==1.16.0`, `aiortc==1.16.0`, `litestar==2.25.0`, `uvicorn[standard]==0.54.0`, `msgspec==0.22.0`,
  `SQLAlchemy[asyncio]==2.1.8`, `aiosqlite==0.22.1`, `alembic==1.20.1`, `argon2-cffi==25.1.0`, `structlog==26.1.0`,
  `xgboost==3.4.1`, `optuna==5.0.0`, `shap==0.54.1`, `mlflow-skinny==3.18.0`, `scikit-learn==1.9.1`, `pandas==3.1.1`,
  `fastparquet==2026.9.0`; dev `pytest==9.2.0`, `ruff==0.17.5`, `mypy==2.4.1`. Optional extras: `ai` (LiteLLM),
  `voice-cloud` (Pipecat's Groq, Deepgram and Cartesia services), `postgres`.
- Web: `nuxt@3.17.7` (Vite 6.4), `vue@3.5.45`, `vue-router@4.6.5`, `tailwindcss@4.1.18` + `@tailwindcss/vite@4.1.18`,
  `@vueuse/core@13.9.0` + `@vueuse/nuxt@13.9.0` (14+ needs Node 22), `motion-v@1.10.3`, `wavesurfer.js@7.12.12`,
  `typescript@5.9.3`, `vue-tsc@2.2.12`, `vitest@3.2.7` (4+ needs Node 22), `happy-dom@20.14.6`, `eslint@9.39.5` with
  `typescript-eslint@8.72.2` and `eslint-plugin-vue@10.12.1`.

## Consequences
- The backend venv is ~820 MB (onnxruntime, scipy, pandas, scikit-learn, av and aiortc are the large parts);
  `node_modules` is ~320 MB. Both are git-ignored.
- Upgrading Nuxt past 3.17 or VueUse past 13 requires Node 22; the CI uses `.nvmrc` (21.7.1) so a bad upgrade fails
  in CI first.
- `make smoke` re-runs both smoke scripts; CI runs the voice smoke on every push.
