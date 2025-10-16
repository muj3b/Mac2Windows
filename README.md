# Mac ↔ Windows Universal Code Converter

End-to-end automation for translating macOS apps to Windows (and the reverse) with zero-touch AI orchestration, quality assurance, reporting, and collaboration features.

## Project Layout

- `electron/` – Electron shell with UI, IPC bridge, and process management.
  - `main.js` launches the renderer and supervises the Python backend.
  - `preload.js` exposes a safe bridge API to the renderer.
  - `src/renderer/` holds the HTML/CSS/JS for the main dashboard.
- `backend/` – FastAPI service orchestrating detection, AI routing, conversion pipeline, QA, reporting, logging, and persistence.
  - `detection/scanner.py` – language/framework/dependency discovery and analysis heuristics.
  - `ai/` – provider registry, model router, and orchestrator enforcing anti-phase prompts.
  - `conversion/` – chunk planner, progress tracker, session manager, and state store integrations.
  - `quality/engine.py` – syntax/dependency/API/security checks plus AI self-review.
  - `reports/` & `storage/` – HTML report generation, backups, embeddings, and session persistence.
  - `learning/memory.py` – captures user corrections for future conversions.
  - `logging/event_logger.py` – structured event log for debugging and audits.
- `data/` – Created on first run to persist SQLite state and ChromaDB collections.

## Getting Started

1. **Install backend dependencies**
   ```bash
   cd /Users/mujeb/mac\ to\ windows
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

2. **Install Electron dependencies**
   ```bash
   cd electron
   npm install
   ```

3. **Run the application**
   ```bash
   # from the project root (ensure the virtualenv is active)
   npm --prefix electron start
   ```
   The Electron process will launch the FastAPI backend automatically (bound to `127.0.0.1:6110`).

### Configure AI providers

Set the relevant environment variables before starting the app:

- `ANTHROPIC_API_KEY` *(optional)* – enables Claude Sonnet/Opus endpoints.
- `ANTHROPIC_API_URL` *(optional)* – override for private Claude gateways.
- `OPENAI_API_KEY` *(optional)* – enables GPT‑5, GPT‑5 mini, GPT‑5 nano.
- `OPENAI_BASE_URL` *(optional)* – override for Azure/OpenAI-compatible endpoints.
- `OPENAI_ORG_ID` *(optional)* – organisation header for OpenAI.
- `OLLAMA_BASE_URL` *(default `http://127.0.0.1:11434`)* – local Ollama instance.

The backend automatically detects configured providers and routes calls to Claude, OpenAI, or Ollama with streaming responses, retries, token accounting, and cost tracking.

### Resource & project conversion stack

- Additional Python dependency: Pillow (for image rescaling) is installed via `backend/requirements.txt`.
- Resource stage now converts Storyboard/XIB ⇄ XAML, `.strings` ⇄ `.resx`, and Info.plist ⇄ app.manifest.
- Project stage generates `.sln/.csproj` for Windows targets and `.xcodeproj` skeletons for macOS.
- Dependency stage maps CocoaPods/SwiftPM ↔ NuGet, emitting `packages.config` or `Package.swift` as appropriate.
- Validation stage runs `dotnet build` or `swiftc -typecheck` when toolchains are available; issues surface in the progress log and summary notes.
- Advanced tooling (Phase 3): git pre/post snapshots, incremental conversion, diff viewer exports, AI self-review, vulnerability/license checks, cloud backups, benchmark summaries, webhook notifications, and manual fallback queues.

## Current Capabilities

- **Smart orchestration** – direction-aware UI with drag‑and‑drop intake, health monitors, webhook hooks, and debug instrumentation.
- **Deep project intelligence** – language/framework/dependency discovery, risk analysis, target suggestions, and automatic dependency graph ordering.
- **Adaptive AI pipeline**
  - Model router balances cost/speed/quality with strategy cues.
  - Anti-phase prompts force complete outputs; retries auto-resume where models stop.
  - RAG context (ChromaDB or in-memory) injects similar patterns, references, and prior decisions.
  - Learning memory applies user corrections to future conversions.
- **Conversion engine** – resources, dependencies, setup, code, tests, and quality stages with pause/resume, auto-save, and batch scheduling.
- **Quality assurance & reporting** – syntax + build heuristics, dependency/API/resource/security checks, AI self-review, vulnerability/license alerts, performance benchmarks, backup/rollback, and searchable HTML reports with per-file diffs.
- **Collaboration tooling** – shared templates, detailed logs, debug prompt capture, webhook notifications, and conversion memory for organization-wide reuse.

To confirm AI connectivity, start the app with valid API keys and use the UI's model selector to run a quick request (e.g. prompt “Convert this Swift code to C#: `let x = 5`”). Streaming responses, token/cost tracking, and error handling are visible in the progress panel and logs.

## Using the Conversion Engine

1. Drag a project onto the app and run auto-detection.
2. Configure conversion/performance/AI settings (or load a saved template), choose your model/provider, and optionally set webhooks.
3. Hit **Start Conversion**. Progress updates show per-stage completion, current file, ETA, token usage, and cost. Pause/resume anytime.
4. Review the generated assets: converted project under `<ProjectName>.<direction>.converted`, HTML report + diffs in `/reports`, backups in `/backups`, and logs via the UI.
5. Trigger rollbacks, share templates, or schedule batch conversions as needed.

## Key APIs & Integrations

- `POST /conversion/start|pause|resume|status/{id}` – session lifecycle.
- `POST /conversion/batch` – queue multiple projects with shared settings.
- `POST /conversion/rollback` – unpack the latest (or chosen) backup for comparison.
- `GET|POST /settings/templates` – manage team presets.
- `POST /settings/debug`, `GET /logs/recent` – enable verbose tracing and retrieve prompt/context logs.

## Roadmap Ideas

- Deeper static analysis and actual toolchain builds when SDKs are available.
- Integrated diff viewer and rollback selector inside the UI.
- Extended vulnerability feeds and license compatibility policies.
