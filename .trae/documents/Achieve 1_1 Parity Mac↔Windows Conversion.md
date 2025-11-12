## Goal
Deliver a terminal-only, fully finished converter that guarantees practical 1:1 behavior and appearance parity for typical macOS and Windows desktop apps across SwiftUI/AppKit and WinUI/WPF/MAUI, with robust tooling, validation, and tests.

## Parity Scope
- UI components and layout: complete mappings for controls, containers, text, images, lists, navigation, dialogs.
- Menus and shortcuts: mac menu bar ↔ Windows app menu/taskbar integrations; `⌘` ↔ `Ctrl`; accelerators.
- Windowing and lifecycle: app start/quit, window size/state, multiple windows, focus, activation.
- System services: file dialogs, clipboard, notifications, sandbox/permissions, Keychain ↔ Credential Locker.
- Assets and branding: icons (ICNS ↔ ICO), app metadata (Info.plist ↔ app.manifest), resources, localization.
- Accessibility: map semantics and roles, keyboard navigation, labels.
- DPI scaling: retina ↔ Windows DPI; font metrics and spacing adjustments.
- Tests and benchmarks: parity tests, compile/run validation, performance regression detection.

## Technical Implementation
### 1. IR & Parsers
- Build a richer Intermediate Representation (IR) covering:
  - UI tree (views, properties, bindings), layout constraints, events, actions.
  - Menus/shortcuts, resources, app metadata, lifecycle hooks.
- Parsing
  - Swift/SwiftUI/AppKit: use `swift-syntax` or `tree-sitter-swift` for AST; extract symbol tables.
  - .NET/XAML: XML parse for XAML; C# syntax via Roslyn-compatible grammar or direct AST tools.

### 2. Deterministic Mapping Catalogs
- Expand `API_MAP` and `DEPENDENCY_MAP`:
  - SwiftUI: `Text`, `Image`, `Button`, `Toggle`, `Slider`, `Picker`, `List`, `NavigationStack`, `TabView`, `Alert`, `Sheet`, `Menu`, `ContextMenu`, `ProgressView` ↔ WinUI/WPF equivalents.
  - AppKit: `NSView`, `NSWindow`, `NSTextField`, `NSButton`, `NSMenu`, `NSMenuItem`, `NSAlert` ↔ WPF.
  - Gestures/shortcuts: `Command`/`Option`/`Shift` combos ↔ `Ctrl`/`Alt`/`Shift` accelerators.
  - Services: `UserDefaults`, `FileManager`, `NotificationCenter`, `Keychain`, `URLSession` ↔ .NET equivalents.
- Layout translation: VStack/HStack/ZStack ↔ StackPanel/Grid/Canvas; padding/margins; alignment.
- Menu bar and taskbar: construct Windows app menus and taskbar notifications mirroring mac items.

### 3. Translation Pipeline
- Deterministic transforms first; then AI-assisted fills for unmapped patterns.
- Guardrails: framework-specific prompt conditioning; enforce generated file layout and project structure.
- Learning engine: record manual fixes and auto-apply recurring patterns; cost-aware model switching.

### 4. Project Generation & Build Drivers
- Windows: generate a `dotnet` solution with chosen UI framework (WinUI/WPF/MAUI); write XAML + C#; invoke `dotnet restore/build`.
- macOS: generate Swift package or Xcode project (SwiftUI/AppKit); write Swift files; invoke `swift build` or `xcodebuild`.
- Resource conversion: ICNS↔ICO, image sizes/scales, localization catalogs; bundle IDs and versioning.

### 5. Validation, Testing & Reporting
- Validation engine: `dotnet build` and `swiftc -typecheck`; surface issues with fix suggestions.
- Test harness: discover/run platform tests; parse failures into actionable TODO.
- Benchmarks: UI/data parse timing; flag regressions.
- Reports: `conversion_report.json`, `quality_report.json`, optional HTML diff report; cost and token summary.

## Packaging & UX
- Console script `macwin` via `pyproject.toml` entry point.
- Config via env and optional `~/.macwin/config.toml`.
- Progress bar with JSON output; `--verbose` for detailed logs.

## Security & Privacy
- API keys via env; redact logs; offline-first mode.
- Backup/credentials optional; only enabled when dependencies present; never store secrets unencrypted.

## Acceptance Criteria
- 1:1 parity for a representative set of apps:
  - SwiftUI sample app with menus/shortcuts, lists, dialogs, notifications, preferences.
  - AppKit sample with multi-window and menus.
  - WPF/WinUI sample app with equivalent features.
- All samples convert, compile, and run on target OS with matching behavior and visuals (icon, branding, layout, interactions).
- Quality score ≥ 0.95 and zero blocking validation errors.

## Milestones
- M1: IR and parser integration; expanded mapping catalogs; generate stub projects; compile validation.
- M2: Full mapping coverage for common controls and services; menu/shortcut parity; resource conversion.
- M3: Test harness, accessibility mapping, DPI adjustments; HTML diff reports; performance baselines.
- M4: Polish and edge cases (custom controls hooks, advanced animations); finalize documentation and examples.

## Next Steps
- Implement expanded mapping modules and IR types; integrate parsers.
- Wire build drivers and compile paths; add sample apps and parity tests.
- Deliver end-to-end artifacts and reports for both directions on macOS and Windows.