from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from backend.conversion.models import ChunkWorkItem


def build_conversion_prompt(
  direction: str,
  chunk: ChunkWorkItem,
  dependency_map: Dict[str, str],
  api_map: Dict[str, str],
  context_summaries: Iterable[str],
  learning_hints: Optional[List[str]],
  previous_summary: Optional[str]
) -> str:
  source_language = chunk.language or 'source'
  target_language = infer_target_language(direction, source_language)
  context_section = '\n'.join(f'- {summary}' for summary in context_summaries if summary)
  if not context_section:
    context_section = '- (no additional context)'
  mapping_section = '\n'.join(f'- {src} → {dst}' for src, dst in dependency_map.items()) or '(no dependency remapping hints)'
  api_section = '\n'.join(f'- {src} → {dst}' for src, dst in api_map.items()) or '(no API mapping hints)'
  learning_section = ''
  if learning_hints:
    learning_section = '\n'.join(f'- {hint}' for hint in learning_hints[:5])
  previous_summary = previous_summary or '(none)'

  guidelines = _directional_guidelines(direction, target_language)

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

DEPENDENCY MAPPINGS
{mapping_section}

API MAPPINGS
{api_section}

PRIOR LEARNING / CORRECTIONS
{learning_section or '(none)'}

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
- Replace Storyboard/XIB references with XAML NavigationView/Page structures where relevant."""
  else:
    return f"""- Target modern {target_language} (Swift 5+/SwiftUI where practical).
- Convert ViewModels to ObservableObject with @Published properties.
- Replace HttpClient with URLSession (async/await).
- Convert dependency injection patterns to Swift protocols/structs.
- Translate WPF/WinUI bindings into SwiftUI state/binding patterns.
- Map Dispatcher/Task scheduling to DispatchQueue or Task.detached as appropriate."""
