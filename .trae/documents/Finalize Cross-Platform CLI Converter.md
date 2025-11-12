## Objectives
- Deliver a terminal-only, fully working Mac ↔ Windows converter with end-to-end flow: analyze → preview → convert → compile → validate → report.
- Remove desktop app dependency; provide a packaged CLI (`macwin`) installable on macOS and Windows.
- Ensure 1:1 UX parity where feasible: menus/shortcuts, system dialogs, assets, icons, and app metadata.

## Implementation Scope
### CLI & Packaging
1. Package Python CLI with entry point `macwin` (pip/pipx install) and Windows `py -3 -m macwin` compatibility.
2. Subcommands: `analyze`, `preview`, `convert`, `compile`, `report` (already prototyped) wired to backend.
3. Config: support env vars + optional `~/.macwin/config.toml` for providers and defaults.
4. Progress: stable progress bar with JSON output; `--verbose` for deep logs.

### Remove GUI
1. Retire `electron/` and Node dependencies.
2. Update startup scripts: backend FastAPI remains optional; CLI runs standalone.

### Detection & IR
1. Robust detection of project types (`.xcodeproj`, `Package.swift`, `.csproj`, `.sln`) via `ProjectScanner`.
2. Build intermediate representation (IR) for UI, inputs, lifecycle, resources.
3. AST parsing:
   - Swift: `swift-syntax` (preferred) or `tree-sitter-swift` for structure and symbol tables.
   - .NET: parse XAML and C# via XML and Roslyn-compatible parsers or Antlr grammars.

### Deterministic Mappings
1. UI components: SwiftUI/AppKit ↔ WinUI/WPF/MAUI (views, stacks, lists, buttons, text fields, images, menus).
2. Layout constraints: VStack/HStack/ZStack ↔ StackPanel/Grid/Canvas equivalents.
3. Input mappings: `⌘` ↔ `Ctrl`, menu bar ↔ app/taskbar integrations, accelerators.
4. System services: file dialogs, notifications, clipboard, sandbox permissions.
5. Assets & metadata: ICNS ↔ ICO, Info.plist ↔ app.manifest, bundle IDs, app icons, versioning.

### AI-Assisted Translation
1. Provider adapters (local: Ollama/LM Studio; cloud: OpenAI/Anthropic/Azure) with rate limiting and fallback.
2. Prompting with guardrails to emit target framework code; enforce structure and file layout.
3. Auto-learning: record manual fixes and apply recurring patterns; cost-aware switching.

### Project Generation & Build Drivers
1. Windows: generate `dotnet` solution for WinUI/WPF/MAUI; write XAML/C# and project files; run `dotnet restore/build`.
2. macOS: generate Swift package or Xcode project (SwiftUI/AppKit); run `swift build` or `xcodebuild`.
3. Post-processing: resource conversion, localization, accessibility hints.

### Validation & Reporting
1. Validation engine: `dotnet build`/`swiftc -typecheck` and surface issues.
2. Test harness: discover and run tests where present; parse failures into actionable TODO.
3. Benchmarks: basic UI/data parse timing to flag regressions.
4. Reports: JSON summary + optional HTML report artifacts with diffs, issues, costs.

### Security & Privacy
1. Secrets via env vars; redact logs; no persistent sensitive data.
2. Offline-first operations; deterministic-only mode when AI disabled.
3. Optional backups gated behind installed cryptography; disabled by default in CLI.

## Milestones
### Phase 1: Terminal-Only Baseline
- Finalize CLI packaging, retire Electron, ensure `analyze`/`preview`/`convert` run with offline provider.
- Minimal SwiftUI ↔ WinUI/WPF mapping for common controls; path mapping and resource copying.

### Phase 2: Full Conversion Flow
- Expand mappings to AppKit and MAUI; handle menus/shortcuts; dialogs; notifications.
- Generate project scaffolds and compile on target OS; add validation output.

### Phase 3: Quality & Reporting
- Integrate test harness, quality engine, benchmarks; HTML report generation; manual fix workflows.
- Improve cost tracking and model auto-switch under budget.

### Phase 4: Coverage & Polish
- Accessibility, localization, custom controls hooks; granular IR diff preview; docs for installation and examples.

## Deliverables
- Packaged CLI (`macwin`) with installer instructions for macOS and Windows.
- Sample projects demonstrating mac→win and win→mac conversions.
- Reports and artifacts: `conversion_report.json`, `quality_report.json`, project outputs ready to compile/run on target OS.

## Risks & Mitigation
- 1:1 parity for complex custom UI may require manual fixes: surface as actionable TODOs with learning patterns.
- Toolchain prerequisites: detect and guide users to install `dotnet` or Xcode; graceful skipping when missing.
- Cross-compilation limitations: build on target OS or containerized environment.

## Next Steps
- Implement packaging (entry points), retire Electron, and expand mapping tables.
- Wire build drivers and compile/validate commands; add sample projects.
- Run end-to-end tests on macOS and Windows and deliver final artifacts.
