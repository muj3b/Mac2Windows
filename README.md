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
- Asset optimisation (Phase 3 step 4): PNG/JPEG resources are compressed automatically (configurable quality and megapixel caps via conversion settings). Savings are logged in the session notes and included in reports.
- Vulnerability & license reporting: dependencies are checked against OSV during conversion; SPDX-based license scanning flags high-risk combinations. Issues surface in quality reports and can trigger manual fix workflows.

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
- **Cloud backups & retention** – encrypted credential store with local/GDrive/Dropbox/OneDrive uploads, per-session metadata, and retention limits driven from the UI.
- **Interactive reports** – consolidated HTML report with summary metrics, searchable diff viewer, severity filters, and one-click AI explanations for any changed line.
- **Automated test scaffolding** – XCTest ↔ NUnit conversions with post-conversion execution, failure surfacing, and TODOs for complex cases.
- **Performance benchmarking** – cross-project UI/data parsing benchmarks with regression detection and reporting.
- **Collaboration tooling** – shared templates, detailed logs, debug prompt capture, webhook notifications, and conversion memory for organization-wide reuse.

To confirm AI connectivity, start the app with valid API keys and use the UI's model selector to run a quick request (e.g. prompt “Convert this Swift code to C#: `let x = 5`”). Streaming responses, token/cost tracking, and error handling are visible in the progress panel and logs.

## Using the Conversion Engine

1. Drag a project onto the app and run auto-detection.
2. Configure conversion/performance/AI settings (or load a saved template), choose your model/provider, and optionally set webhooks.
3. Hit **Start Conversion**. Progress updates show per-stage completion, current file, ETA, token usage, and cost. Pause/resume anytime.
4. Review the generated assets: converted project under `<ProjectName>.<direction>.converted`, HTML report + diffs in `/reports`, backups in `/backups`, and logs via the UI.
5. Trigger rollbacks, share templates, or schedule batch conversions as needed.

## Cloud Backups

- Enable the **Cloud Backup** toggle in the settings panel to mirror the converted target after each run.
- Supported providers: local filesystem, Google Drive, Dropbox, and OneDrive. OAuth flows launch in your default browser and tokens are encrypted via `data/credentials.db`.
- Configure retention (number of archives to keep), remote path template (supports `{project}`, `{direction}`, `{session}`, `{timestamp}`), and credential selection directly from the UI. Local backups can target any writable directory.
- Each backup embeds `conversion_metadata.json` (tokens, cost, quality summary, notes) inside the archive. The consolidated HTML report lists recent backups and links to cloud copies when available.
- Rollbacks continue to reference the `backups/` folder under each converted project; cloud copies are treated as off-site mirrors.

## Automated Test Generation

- Test files detected during planning are fed through a specialised prompt to translate XCTest ↔ NUnit (or vice versa) while preserving assertions, fixtures, and naming conventions.
- Converted tests are written directly to the target project tree. Failures or provider issues automatically enqueue manual-fix tasks with contextual notes.
- After conversion the harness executes `dotnet test` or `swift test` (tooling permitting). Results flow into the quality report, progress dashboard, and summary notes.
- Any failing suites generate actionable TODO entries and appear in the HTML report’s summary + quality tabs.

## Performance Benchmarks

- A lightweight benchmark harness parses representative UI and data assets in both the original and converted projects.
- Metrics capture wall-clock duration, CPU time, and memory deltas for operations such as XML layout parsing and resource loading.
- Regression thresholds (20% by default) automatically flag slowdowns in the quality report and conversion summary.
- Benchmark results appear in the interactive report (summary tab) with side-by-side comparisons and regression highlighting.

## Interactive Reports & Diff Viewer

- The **Open Conversion Report** button launches a self-contained HTML dashboard with summary metrics, quality outcomes, and a searchable diff explorer.
- Filter files by severity, search by name, or drill into any change. Selecting a line requests an on-demand explanation from the same model/provider used for the conversion.
- Reports render locally (no network dependency) and can be exported to PDF via the built-in **Export PDF** button or the browser’s print dialogue.
- Quality issues surface in a dedicated tab with categorised severity. AI explanations require the session to remain active so the backend can reuse the cached provider credentials.

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
