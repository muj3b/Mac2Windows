## Goals
- Replace the current Electron desktop app with a terminal-first CLI that works on macOS and Windows.
- Accept a source app/project (mac→win or win→mac), analyze dependencies, translate APIs/UI, and compile a runnable target binary.
- Allow AI providers: local (e.g., Ollama/LM Studio) or cloud (OpenAI, Anthropic, Azure, etc.).
- Provide clear progress reporting (spinner/progress bar), logs, and a final conversion report.

## Current State (from repo survey)
- Backend: Python FastAPI service with conversion logic under `backend/` (entrypoint `backend/main.py`, requirements in `backend/requirements.txt`).
- GUI: Electron app under `electron/` that spawns the backend and renders conversion UI.
- Data: `data/` for state and learning memory.
- No Swift/C# source for the tool itself; Swift/Windows frameworks are conversion targets only.

## High-Level Approach
1. Preserve and extend Python backend as the core engine (conversion, dependency resolution, AI integration, reporting).
2. Add a robust CLI layer around the backend with subcommands (`convert`, `analyze`, `compile`, `preview`, `report`).
3. Remove Electron runtime dependency and optionally keep FastAPI as an internal service for CLI features that benefit from HTTP orchestration.
4. Implement a translation pipeline that combines deterministic mappings + AST transforms + AI-assisted gaps.
5. Generate a buildable target project (Windows or macOS) and invoke the platform toolchain to compile.

## CLI Design
- Command: `macwin` (installable via `pipx`/`pip`).
- Subcommands:
  - `convert`: `macwin convert --direction mac-to-win --src <path> --out <dir> --framework winui|wpf|maui|swiftui|appkit --model local|cloud --provider <name> --dry-run`
  - `analyze`: static inventory of APIs, assets, build settings, and risk report.
  - `compile`: build the generated target project using `dotnet` (Windows) or `swift build` (mac).
  - `preview`: run a lightweight simulation using the IR with a simple renderer.
  - `report`: show conversion summary, manual fix suggestions, diffs, and costs.
- Output: human-readable logs + `--json` machine output; progress bar for long phases.

## Conversion Pipeline
- Detect project type: SwiftUI/AppKit/Xcode vs WPF/WinUI/.NET; read manifests (`.xcodeproj`, `Package.swift`, `.csproj`, `.sln`).
- Parse source:
  - Swift: use `tree-sitter-swift` or `swift-syntax` to build AST; extract types, UI hierarchy, actions.
  - .NET: read XAML/C# with Roslyn-like AST (via `antlr4` grammars or external tools) when converting win→mac.
- Build an intermediate representation (IR): components, layouts, commands, resources, input gestures, lifecycle hooks.
- Deterministic mapping tables:
  - UI: SwiftUI/AppKit ↔ WinUI/WPF/MAUI (views, layout stacks, controls, bindings).
  - Input: `⌘` → `Ctrl`, menu bar ↔ app menu/taskbar integrations, shortcuts.
  - System services: file dialogs, notifications, clipboard, sandbox permissions.
  - Assets: icons, images, fonts; app metadata.
- AI-assisted translation:
  - Fill gaps where deterministic mappings are insufficient; generate idiomatic target code and comments for manual follow-up when necessary.
  - Guardrails: constrain output to chosen framework; enforce project structure.
- Project generation:
  - Windows: create `dotnet` solution with chosen UI framework, inject translated XAML/C# or WinUI components.
  - macOS: create `swift` package/Xcode project with SwiftUI/AppKit.
- Post-processing:
  - Resource conversion (ICNS/ICO), localization files, bundle identifiers, signing placeholders.
  - Create `manual_fixes.md` with items needing human confirmation.

## Compilation & Toolchains
- Windows build: require `dotnet SDK` (WinUI/WPF/MAUI). Command: `dotnet restore && dotnet build -c Release`.
- macOS build: require Xcode/Swift toolchain. Command: `swift build -c release` or `xcodebuild` when needed.
- Cross-compilation is out-of-scope for step 1; build must occur on the target OS or in a container/VM with the toolchain.

## AI Provider Integration
- Local: detect and connect to `ollama`, `LM Studio`, or local server URL. Config via `~/.macwin/config.toml` or env.
- Cloud: pluggable providers with API keys in env vars. Rate-limit, token-cost tracking, and offline fallback to deterministic-only.
- Routing: choose model by task (code explanation vs UI mapping vs resource renaming) with temperature and context limits.

## Progress & UX
- TUI/CLI progress: phases (analyze → map → generate → compile → validate). Spinner/progress bar with ETA and phase summaries.
- Logs: structured logs to file; concise console output; `--verbose` for deep traces.
- Reports: save `conversion_report.json` and `quality_report.json`; optional HTML report.

## Validation & Parity
- Snapshot testing against IR to ensure component parity where possible.
- Smoke-run on target binary: launch, open main windows, verify menus/shortcuts mapping.
- Diff view (`preview` subcommand) to compare source UI vs generated UI.

## Security & Privacy
- Never store secrets; read API keys from env; redact logs.
- Offline-first; cache only non-sensitive artifacts.
- Allow opt-in telemetry for conversion metrics; disabled by default.

## Incremental Delivery
- Phase 1: CLI skeleton + `analyze` + deterministic mappings for common SwiftUI ↔ WinUI/WPF components; generate stub project.
- Phase 2: AI-assisted translation and richer mapping tables; `compile` wiring.
- Phase 3: Preview renderer, reports, and manual fixes guidance.
- Phase 4: Expand coverage (AppKit, MAUI, complex gestures, accessibility).

## Repo Changes (planned)
- Remove/retire `electron/` and associated scripts; keep FastAPI as optional internal service.
- Add Python CLI module (e.g., `backend/cli/__main__.py`) with `entry_points` for `macwin`.
- Introduce mapping modules under `backend/conversion/mappings/` and IR types under `backend/conversion/ir/`.
- Add provider adapters under `backend/ai/providers/` with local & cloud options.
- Add build drivers under `backend/build/` for `dotnet` and `swift`.

## Risks & Constraints
- Perfect 1:1 parity is non-trivial; some platform-specific behaviors require human review.
- Toolchains must be present on the machine; cross-compiling is limited.
- Complex, custom controls may need manual porting.

## Next Steps
- Implement CLI entrypoints and wire them to existing backend routines.
- Add minimal SwiftUI ↔ WinUI/WPF mapping and project generation for a basic app.
- Provide initial `convert` flow and a sample project to validate end-to-end on both OSes.
