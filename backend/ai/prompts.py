from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from backend.conversion.models import ChunkWorkItem


def build_conversion_prompt(
  direction: str,
  chunk: ChunkWorkItem,
  dependency_map: Dict[str, str],
  api_map: Dict[str, str],
  shortcut_map: Dict[str, str],
  menu_role_map: Dict[str, str],
  context_summaries: Iterable[str],
  learning_hints: Optional[List[str]],
  previous_summary: Optional[str],
  thinking_output: Optional[str] = None
) -> str:
  source_language = chunk.language or 'source'
  target_language = infer_target_language(direction, source_language)
  context_section = '\n'.join(f'- {summary}' for summary in context_summaries if summary)
  if not context_section:
    context_section = '- (no additional context)'
  mapping_section = '\n'.join(f'- {src} → {dst}' for src, dst in dependency_map.items()) or '(no dependency remapping hints)'
  api_section = '\n'.join(f'- {src} → {dst}' for src, dst in api_map.items()) or '(no API mapping hints)'
  shortcut_section = '\n'.join(f'- {src} → {dst}' for src, dst in shortcut_map.items()) or '(no shortcut mapping hints)'
  menu_role_section = '\n'.join(f'- {src} → {dst}' for src, dst in menu_role_map.items()) or '(no menu role mapping hints)'
  learning_section = ''
  if learning_hints:
    learning_section = '\n'.join(f'- {hint}' for hint in learning_hints[:5])
  previous_summary = previous_summary or '(none)'
  thinking_section = ''
  if thinking_output:
    thinking_section = f"\nPRE-COMPUTED ANALYSIS (THINKING MODE)\n{thinking_output}\n"

  guidelines = _directional_guidelines(direction, target_language)
  pitfall_examples = _common_pitfall_examples(direction)
  
  platform_specifics = ""
  if direction == 'mac-to-win':
    platform_specifics = """
PLATFORM SPECIFIC MIGRATION (Mac -> Windows):
- **Menu Bar**: Convert macOS Menu Bar items to Windows System Tray (Notification Area) icons or standard window menus (File/Edit/etc).
- **App Lifecycle**: Windows apps often minimize to tray instead of terminating. Handle `WM_CLOSE` vs `WM_QUIT`.
- **File Paths**: Ensure backslashes `\\` are used or use `Path.Combine`. Handle drive letters (C:).
- **Settings**: Migrate `NSUserDefaults` to Windows Registry or `AppData` config files.
- **Installer**: Suggest MSIX or Inno Setup instead of DMG/Pkg.
"""
  elif direction == 'win-to-mac':
    platform_specifics = """
PLATFORM SPECIFIC MIGRATION (Windows -> Mac):
- **System Tray**: Convert Windows System Tray icons to macOS Menu Bar extras (NSStatusItem).
- **Window Management**: Handle macOS window lifecycle (app stays running when last window closes).
- **File Paths**: Use forward slashes `/`. Handle case-sensitive file systems if applicable.
- **Settings**: Migrate Registry keys to `NSUserDefaults` (plist).
- **Sandboxing**: Ensure file access complies with macOS App Sandbox rules.
"""

  return f"""You are an expert software engineer specialising in cross-platform conversions.
Convert the following {source_language} code into **{target_language}** suitable for the target platform.

CRITICAL REQUIREMENTS
- Return the ENTIRE converted file in a single response.
- Do NOT omit using/import statements, class/struct declarations, or helper functions.
- Do NOT explain, comment, or summarise the conversion. Output code only.
- Preserve logical flow, data models, and async/threading behaviour.
- Use platform-idiomatic APIs and patterns described below.
- Apply dependency and API mappings exactly where relevant.
- If information is missing, make the safest reasonable assumption and note it as a TODO comment in the code.

TARGET CONTEXT
- Conversion direction: {direction}
- Source path: {chunk.file_path}
- Prior chunk summary: {previous_summary}
- Language focus: {source_language} → {target_language}

GUIDELINES
{guidelines}

{platform_specifics}

COMMON PITFALL EXAMPLES
{pitfall_examples}

DEPENDENCY MAPPINGS
{mapping_section}

API MAPPINGS
{api_section}

SHORTCUTS
{shortcut_section}

MENU ROLES
{menu_role_section}

PRIOR LEARNING / CORRECTIONS
{learning_section or '(none)'}

{thinking_section}

SUPPORTING CONTEXT
{context_section}

SOURCE CODE
```{source_language.lower()}
{chunk.content}
```

OUTPUT FORMAT
- Return only the complete {target_language} code without explanation.
- Do not wrap the code in markdown fences.
- Ensure indentation and braces are valid for {target_language}.
"""


def infer_target_language(direction: str, source_language: str) -> str:
  normalized = direction.lower()
  if normalized == 'mac-to-win':
    if source_language.lower() in {'c++', 'objective-c++'}:
      return 'C++'
    return 'C#'
  if normalized == 'win-to-mac':
    if source_language.lower() == 'c++':
      return 'C++'
    return 'Swift'
  return 'C#'


def _directional_guidelines(direction: str, target_language: str) -> str:
  if direction == 'mac-to-win':
    return f"""- Use modern {target_language} (.NET 8) patterns (async/await, Task-based async).
- Prefer WinUI 3 controls unless existing UI is best represented in WPF; when uncertain default to WinUI.
- Replace property wrappers or @Published with INotifyPropertyChanged.
- Replace URLSession/NSURLConnection with HttpClient and HttpRequestMessage.
- Persist data via Entity Framework or community equivalents for Core Data.
- Convert dispatch queues to Task.Run or DispatcherQueue depending on UI thread requirements.
- Replace Storyboard/XIB references with XAML NavigationView/Page structures where relevant.
- Map macOS menu bar items to Windows app menus with accelerators; translate Command/Option to Ctrl/Alt.
- Ensure accessibility properties are set (AutomationProperties.Name/HelpText) and keyboard navigation works.
- Adjust for DPI scaling and font metrics; prefer layout containers over absolute positioning."""
  else:
    return f"""- Target modern {target_language} (Swift 5+/SwiftUI where practical).
- Convert ViewModels to ObservableObject with @Published properties.
- Replace HttpClient with URLSession (async/await).
- Convert dependency injection patterns to Swift protocols/structs.
- Translate WPF/WinUI bindings into SwiftUI state/binding patterns.
- Map Dispatcher/Task scheduling to DispatchQueue or Task.detached as appropriate.
- Map Windows app menus and accelerators to macOS menu bar items and Command/Option keys.
- Use accessibility modifiers (accessibilityLabel, accessibilityHint) and ensure keyboard focus behaviour.
- Adjust for Retina scaling and dynamic type; prefer stacks and grids over fixed frames."""


def _common_pitfall_examples(direction: str) -> str:
  if direction == 'mac-to-win':
    return """Example 1 – Layout conversions
Source (Swift)
  view.frame = CGRect(x: 16, y: 20, width: 180, height: 72)
Target (C#/XAML)
  <!-- Avoid setting Width/Height directly; prefer Grid/StackPanel -->
  <Grid Margin="16,20,16,0">
    <Grid.ColumnDefinitions>
      <ColumnDefinition Width="Auto" />
      <ColumnDefinition Width="*" />
    </Grid.ColumnDefinitions>
  </Grid>

Example 2 – Escaping closures
Source (Swift)
  func fetchUser(completion: @escaping (Result<User, Error>) -> Void)
Target (C#)
  public void FetchUser(Action<Result<User, Exception>> completion)

Example 3 – UserDefaults → LocalSettings
Source (Swift)
  let launchCount = UserDefaults.standard.integer(forKey: "launchCount")
Target (C#)
  var values = ApplicationData.Current.LocalSettings.Values;
  var launchCount = values.TryGetValue("launchCount", out object stored) && stored is int count ? count : 0;
"""
  return """Example 1 – Layout conversions
Source (C# / XAML)
  <StackPanel Width="180" Height="72">...</StackPanel>
Target (SwiftUI)
  VStack { ... }
    .frame(maxWidth: .infinity, alignment: .leading)

Example 2 – Delegates → Escaping closures
Source (C#)
  public void Fetch(Action<string> callback)
Target (Swift)
  func fetch(completion: @escaping (String) -> Void)

Example 3 – LocalSettings → UserDefaults
Source (C#)
  var launchCount = (int?)settings.Values["launchCount"] ?? 0;
Target (Swift)
  let launchCount = UserDefaults.standard.integer(forKey: "launchCount")
"""


def build_review_prompt(
  direction: str,
  chunk: ChunkWorkItem,
  converted_code: str,
  summary: str,
  context_summaries: Iterable[str]
) -> str:
  target_language = infer_target_language(direction, chunk.language or '')
  context_section = '\n'.join(f'- {ctx}' for ctx in context_summaries if ctx) or '- (no extra context)'
  return (
    "You are performing a rigorous code review on the converted {lang} file. Analyse the code for correctness, missing namespaces/imports, platform API misuse, async/threading mishandling, or unimplemented sections.\n\n"
    "Return your findings strictly as JSON with this structure:\n"
    "{\n  \"issues\": [\n    {\n      \"message\": \"Concise description\",\n      \"severity\": \"error|warning|info\",\n      \"auto_fix\": { \"full_text\": \"<entire corrected file>\" } | null,\n      \"manual_note\": \"Guidance for manual fix\" | null\n    }\n  ]\n}\n\n"
    "- Use auto_fix.full_text only when you can provide the complete corrected file that compiles.\n"
    "- If no issues are found, respond with {\"issues\": []}.\n\n"
    "Direction: {direction}\n"
    "File: {file}\n"
    "Chunk summary: {summary}\n"
    "Context:\n{context}\n"
    "Converted code:\n```{lang_lower}\n{code}\n```"
  ).format(
    lang=target_language,
    direction=direction,
    file=chunk.file_path,
    summary=summary or '(none)',
    context=context_section,
    code=converted_code,
    lang_lower=target_language.lower()
  )


def build_diff_explanation_prompt(before_snippet: str, after_snippet: str, metadata: Dict[str, object]) -> str:
  file_path = metadata.get('file_path', 'unknown file')
  line_number = metadata.get('line_number')
  direction = metadata.get('direction', 'conversion')
  return (
    "You are reviewing a code diff produced by an automated Mac ↔ Windows conversion pipeline. "
    "Explain why the highlighted change was necessary. Focus on intent, platform-specific adjustments, "
    "and behavioural differences. Keep the response under 6 sentences.\n\n"
    f"Direction: {direction}\n"
    f"File: {file_path}\n"
    f"Line: {line_number}\n\n"
    "Original snippet:\n"
    "```\n"
    f"{before_snippet.strip() or '(none)'}\n"
    "```\n\n"
    "Converted snippet:\n"
    "```\n"
    f"{after_snippet.strip() or '(none)'}\n"
    "```\n\n"
    "Explain the rationale for this change, referencing platform APIs or language semantics when relevant."
  )


def build_test_prompt(
  direction: str,
  chunk: ChunkWorkItem,
  source_language: str,
  target_language: str,
  source_framework: str,
  target_framework: str
) -> str:
  return (
    "You are converting automated tests between platforms for a Mac ↔ Windows migration.\n"
    f"Source framework: {source_framework}\n"
    f"Target framework: {target_framework}\n"
    f"Source language: {source_language}\n"
    f"Target language: {target_language}\n\n"
    "Requirements:\n"
    "- Preserve test intent, assertions, and fixtures.\n"
    "- Map XCTest lifecycle methods (setUp/tearDown) to the target framework equivalents.\n"
    "- Convert assertions (e.g., XCTAssertEqual → Assert.AreEqual, Assert.Equal, XCTAssertTrue → Assert.IsTrue, etc.).\n"
    "- When an assertion has no direct counterpart, use the closest equivalent and add an inline TODO comment.\n"
    "- Maintain descriptive test names (convert to PascalCase for .NET).\n"
    "- Ensure the output compiles in the target framework with necessary imports/usings.\n"
    "- Avoid using placeholder implementations; translate the logic faithfully.\n"
    "- If the original test references unavailable APIs post-conversion, add an explanatory TODO comment while keeping the test runnable.\n\n"
    f"Convert the following {source_framework} test file into {target_framework}:\n"
    "---------------- SOURCE TEST ----------------\n"
    f"{chunk.content}\n"
    "---------------- END SOURCE -----------------\n"
    "Output only the converted test file content."
  )


def infer_test_frameworks(direction: str, source_language: str) -> Tuple[str, str]:
  normalized = direction.lower()
  if normalized == 'mac-to-win':
    return ('XCTest', 'NUnit')
  return ('NUnit', 'XCTest')


def build_thinking_prompt(
  direction: str,
  chunk: ChunkWorkItem,
  context_summaries: Iterable[str]
) -> str:
  source_language = chunk.language or 'source'
  target_language = infer_target_language(direction, source_language)
  context_section = '\n'.join(f'- {summary}' for summary in context_summaries if summary) or '(no additional context)'
  
  return f"""You are an expert software architect. Analyze the following {source_language} code to prepare for a conversion to {target_language}.
  
  GOAL: Provide a detailed technical analysis to guide the conversion process.
  
  CONTEXT:
  - Direction: {direction}
  - File: {chunk.file_path}
  - Additional Context:
  {context_section}
  
  SOURCE CODE:
  ```{source_language.lower()}
  {chunk.content}
  ```
  
  INSTRUCTIONS:
  1. Identify the core responsibilities of this code.
  2. List specific platform-dependent APIs (e.g., UI frameworks, file I/O, threading) that need migration.
  3. Suggest the most appropriate {target_language} equivalents or patterns.
     - **CRITICAL**: If converting Mac Menu Bar, explicitly plan for Windows System Tray or Window Menus.
     - **CRITICAL**: If converting Windows Tray, explicitly plan for Mac Status Bar Items.
  4. Highlight potential pitfalls (e.g., memory management differences, async patterns).
  5. Do NOT generate the converted code yet. Focus on the "HOW" and "WHY".
  
  OUTPUT FORMAT:
  - Concise bullet points.
  - Clear headings for "Responsibilities", "API Migration", "Patterns", and "Risks".
  """
