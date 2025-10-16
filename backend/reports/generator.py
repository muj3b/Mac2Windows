from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from backend.config import settings
from backend.conversion.diff import generate_diff_entry
from backend.conversion.models import ConversionReport

if TYPE_CHECKING:
  from backend.conversion.manager import ConversionSession


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Conversion Report</title>
    <style>
      :root {
        color-scheme: light dark;
        --bg: #f8fafc;
        --panel: #ffffff;
        --border: #cbd5f5;
        --text: #0f172a;
        --muted: #64748b;
        --accent: #2563eb;
        --accent-muted: #dbeafe;
        --success: #16a34a;
        --warning: #f97316;
        --error: #dc2626;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: 'Segoe UI', Roboto, sans-serif;
        background: var(--bg);
        color: var(--text);
      }
      header.app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 18px 32px;
        background: var(--panel);
        border-bottom: 1px solid var(--border);
        position: sticky;
        top: 0;
        z-index: 10;
      }
      header h1 {
        margin: 0;
        font-size: 24px;
      }
      header .muted { color: var(--muted); margin: 4px 0 0; }
      .header-actions button {
        padding: 8px 16px;
        border-radius: 8px;
        border: 1px solid var(--accent);
        background: var(--accent);
        color: #fff;
        cursor: pointer;
      }
      .tab-nav {
        display: flex;
        gap: 8px;
        padding: 12px 32px;
        background: transparent;
      }
      .tab-button {
        border: 1px solid var(--border);
        background: var(--panel);
        color: var(--text);
        padding: 8px 18px;
        border-radius: 8px;
        cursor: pointer;
      }
      .tab-button.active {
        border-color: var(--accent);
        color: var(--accent);
        background: var(--accent-muted);
      }
      main { padding: 0 32px 48px; }
      .tab { display: none; }
      .tab.active { display: block; }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-top: 16px;
      }
      .metric-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.05);
      }
      .metric-card .label { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; }
      .metric-card .value { font-size: 24px; margin-top: 8px; font-weight: 600; }
      .notes-card {
        margin-top: 24px;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
      }
      .notes-card ul { margin: 12px 0 0; padding-left: 20px; }
      .benchmark-table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
      .benchmark-table th, .benchmark-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); text-align: left; }
      .benchmark-table tr.regression td { color: var(--warning); font-weight: 600; }
      .diff-layout {
        display: grid;
        grid-template-columns: 280px 1fr;
        gap: 16px;
        height: calc(100vh - 220px);
      }
      .diff-sidebar {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      #diff-search {
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid var(--border);
        font-size: 14px;
      }
      .severity-filters {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .severity-filters button {
        border: 1px solid var(--border);
        background: transparent;
        padding: 6px 10px;
        border-radius: 999px;
        cursor: pointer;
        font-size: 12px;
      }
      .severity-filters button.active {
        border-color: var(--accent);
        background: var(--accent);
        color: #fff;
      }
      #diff-file-list {
        list-style: none;
        margin: 0;
        padding: 0;
        overflow-y: auto;
        flex: 1;
      }
      #diff-file-list li {
        padding: 10px;
        border-radius: 8px;
        cursor: pointer;
        border: 1px solid transparent;
        margin-bottom: 6px;
      }
      #diff-file-list li.active {
        border-color: var(--accent);
        background: var(--accent-muted);
      }
      #diff-file-list li .name { display: block; font-weight: 600; }
      #diff-file-list li .meta { color: var(--muted); font-size: 12px; }
      .severity-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11px;
        margin-left: 8px;
      }
      .severity-high { background: rgba(220, 38, 38, 0.15); color: var(--error); }
      .severity-medium { background: rgba(249, 115, 22, 0.18); color: var(--warning); }
      .severity-low { background: rgba(34, 197, 94, 0.15); color: var(--success); }
      .diff-view {
        display: flex;
        flex-direction: column;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
      }
      #diff-header {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      #diff-table-container {
        overflow: auto;
        flex: 1;
      }
      .diff-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      .diff-table td {
        border-bottom: 1px solid var(--border);
        padding: 0;
      }
      .diff-code {
        display: flex;
        gap: 12px;
        padding: 4px 12px;
        cursor: pointer;
      }
      .diff-code.selected { outline: 2px solid var(--accent); background: var(--accent-muted); }
      .line-number {
        width: 48px;
        color: var(--muted);
        text-align: right;
        font-family: 'Fira Code', 'SFMono-Regular', monospace;
      }
      .line-text {
        flex: 1;
        white-space: pre;
        font-family: 'Fira Code', 'SFMono-Regular', monospace;
      }
      .type-insert .line-text.right { background: rgba(34, 197, 94, 0.16); }
      .type-delete .line-text.left { background: rgba(220, 38, 38, 0.15); }
      .type-replace .line-text.right { background: rgba(37, 99, 235, 0.14); }
      .type-replace .line-text.left { background: rgba(244, 114, 182, 0.14); }
      .explanation-panel {
        border-top: 1px solid var(--border);
        padding: 12px 16px 18px;
      }
      .explanation-panel h3 { margin: 0 0 8px; }
      .muted { color: var(--muted); }
      .quality-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 16px;
        margin-top: 20px;
      }
      .quality-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
      }
      .quality-card h3 { margin-top: 0; }
      .quality-issue {
        border-top: 1px solid var(--border);
        padding: 12px 0;
      }
      .quality-issue:first-of-type { border-top: none; }
      .quality-issue .severity {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--muted);
      }
      @media (max-width: 960px) {
        .diff-layout {
          grid-template-columns: 1fr;
          height: auto;
        }
        .diff-view { min-height: 420px; }
      }
    </style>
  </head>
  <body>
    <header class=\"app-header\">
      <div>
        <h1>Conversion Report</h1>
        <p class=\"muted\" id=\"report-subtitle\"></p>
      </div>
      <div class=\"header-actions\">
        <button id=\"btn-print\">Export PDF</button>
      </div>
    </header>
    <nav class=\"tab-nav\">
      <button class=\"tab-button active\" data-tab=\"summary\">Summary</button>
      <button class=\"tab-button\" data-tab=\"diff\">Diff Viewer</button>
      <button class=\"tab-button\" data-tab=\"quality\">Quality</button>
    </nav>
    <main>
      <section id=\"tab-summary\" class=\"tab active\">
        <div class=\"metric-grid\" id=\"summary-metrics\"></div>
        <div class=\"notes-card\" id=\"tests-card\" style=\"display:none;\"></div>
        <div class=\"notes-card\" id=\"benchmark-card\" style=\"display:none;\"></div>
        <div class=\"notes-card\">
          <h2>Notes</h2>
          <ul id=\"summary-notes\"></ul>
        </div>
      </section>
      <section id=\"tab-diff\" class=\"tab\">
        <div class=\"diff-layout\">
          <aside class=\"diff-sidebar\">
            <input type=\"search\" id=\"diff-search\" placeholder=\"Search files...\" />
            <div class=\"severity-filters\">
              <button class=\"active\" data-severity=\"all\">All</button>
              <button data-severity=\"high\">High</button>
              <button data-severity=\"medium\">Medium</button>
              <button data-severity=\"low\">Low</button>
            </div>
            <ul id=\"diff-file-list\"></ul>
          </aside>
          <section class=\"diff-view\">
            <div id=\"diff-header\"></div>
            <div id=\"diff-table-container\">
              <table class=\"diff-table\"><tbody id=\"diff-table-body\"></tbody></table>
            </div>
            <div class=\"explanation-panel\" id=\"explanation-panel\">
              <h3>AI Explanation</h3>
              <div id=\"explanation-content\" class=\"muted\">Select a changed line to request an explanation.</div>
            </div>
          </section>
        </div>
      </section>
      <section id=\"tab-quality\" class=\"tab\">
        <div id=\"quality-summary\"></div>
        <div class=\"quality-grid\" id=\"quality-issues\"></div>
      </section>
    </main>
    <script>
      window.__REPORT_DATA__ = __REPORT_CONTEXT__;
      (function() {
        const DATA = window.__REPORT_DATA__;
        const state = {
          severity: 'all',
          search: '',
          activeFileId: null,
          activeRow: null,
          loading: false
        };
        const severityOrder = { high: 3, medium: 2, low: 1 };
        const severityLabels = { high: 'High', medium: 'Medium', low: 'Low' };

        document.getElementById('btn-print').addEventListener('click', () => window.print());
        document.querySelectorAll('.tab-button').forEach((button) => {
          button.addEventListener('click', () => {
            document.querySelectorAll('.tab-button').forEach((btn) => btn.classList.remove('active'));
            document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(`tab-${button.dataset.tab}`).classList.add('active');
          });
        });

        const subtitle = document.getElementById('report-subtitle');
        subtitle.textContent = `${DATA.project_name} • ${DATA.direction.toUpperCase()} • ${new Date(DATA.generated_at * 1000).toLocaleString()}`;

        const metricsEl = document.getElementById('summary-metrics');
        const notesEl = document.getElementById('summary-notes');
        const testsCard = document.getElementById('tests-card');
        const benchmarkCard = document.getElementById('benchmark-card');
        const diffListEl = document.getElementById('diff-file-list');
        const diffSearch = document.getElementById('diff-search');
        const diffTableBody = document.getElementById('diff-table-body');
        const diffHeader = document.getElementById('diff-header');
        const explanationContent = document.getElementById('explanation-content');
        const qualitySummary = document.getElementById('quality-summary');
        const qualityIssues = document.getElementById('quality-issues');

        const formatDuration = (seconds) => {
          if (!seconds || seconds < 1) return 'Under 1s';
          const mins = Math.floor(seconds / 60);
          const secs = Math.floor(seconds % 60);
          const hours = Math.floor(mins / 60);
          if (hours) return `${hours}h ${mins % 60}m`;
          if (mins) return `${mins}m ${secs}s`;
          return `${secs}s`;
        };

        const renderSummary = () => {
          const metrics = [
            { label: 'Converted Files', value: `${DATA.summary.converted_files} / ${DATA.summary.total_files}` },
            { label: 'Tokens Used', value: DATA.summary.tokens_used.toLocaleString() },
            { label: 'Estimated Cost', value: `$${DATA.summary.cost_usd.toFixed(4)}` },
            { label: 'Elapsed Time', value: formatDuration(DATA.summary.elapsed_seconds) },
            { label: 'Direction', value: DATA.direction.toUpperCase() },
            { label: 'Model', value: `${DATA.model.provider} • ${DATA.model.identifier}` }
          ];
          metricsEl.innerHTML = '';
          metrics.forEach((metric) => {
            const card = document.createElement('div');
            card.className = 'metric-card';
            const label = document.createElement('div');
            label.className = 'label';
            label.textContent = metric.label;
            const value = document.createElement('div');
            value.className = 'value';
            value.textContent = metric.value;
            card.appendChild(label);
            card.appendChild(value);
            metricsEl.appendChild(card);
          });

          notesEl.innerHTML = '';
          if (!DATA.notes.length) {
            const empty = document.createElement('li');
            empty.textContent = 'No additional notes recorded.';
            empty.className = 'muted';
            notesEl.appendChild(empty);
          } else {
            DATA.notes.forEach((note) => {
              const item = document.createElement('li');
              item.textContent = note;
              notesEl.appendChild(item);
            });
          }

          if (testsCard) {
            const tests = DATA.tests || {};
            if (tests.status) {
              testsCard.style.display = 'block';
              const failures = tests.failures ? tests.failures.length : 0;
              const header = `<h2>Automated Tests</h2>`;
              const summary = `<p>Status: <strong>${tests.status.toUpperCase()}</strong> • Failures: ${failures}</p>`;
              const failureList = failures
                ? `<ul>${tests.failures.map((entry) => `<li>${entry}</li>`).join('')}</ul>`
                : '<div class="muted">No failing tests</div>';
              const todoList = tests.todo && tests.todo.length
                ? `<div class="muted">TODO:<ul>${tests.todo.map((entry) => `<li>${entry}</li>`).join('')}</ul></div>`
                : '';
              testsCard.innerHTML = `${header}${summary}${failureList}${todoList}`;
            } else {
              testsCard.style.display = 'none';
              testsCard.innerHTML = '';
            }
          }

          if (benchmarkCard) {
            const benchmarkData = DATA.benchmarks || {};
            const comparisons = benchmarkData.comparisons || [];
            if (comparisons.length) {
              benchmarkCard.style.display = 'block';
              const rows = comparisons.map((item) => {
                const regressionClass = item.regression ? 'regression' : '';
                const delta = (item.delta_pct * 100).toFixed(1);
                return `<tr class="${regressionClass}"><td>${item.metric.toUpperCase()}</td><td>${item.original_duration.toFixed(3)}s</td><td>${item.converted_duration.toFixed(3)}s</td><td>${delta}%</td></tr>`;
              }).join('');
              benchmarkCard.innerHTML = `
                <h2>Performance Benchmarks</h2>
                <table class="benchmark-table">
                  <thead><tr><th>Metric</th><th>Original</th><th>Converted</th><th>Δ %</th></tr></thead>
                  <tbody>${rows}</tbody>
                </table>
              `;
            } else {
              benchmarkCard.style.display = 'none';
              benchmarkCard.innerHTML = '';
            }
          }
        };

        const renderQuality = () => {
          const summaryItems = [
            { label: 'Syntax', value: DATA.quality.syntax_passed ? 'Passed' : 'Failed', cls: DATA.quality.syntax_passed ? 'severity-low' : 'severity-high' },
            { label: 'Build', value: DATA.quality.build_passed ? 'Passed' : 'Failed', cls: DATA.quality.build_passed ? 'severity-low' : 'severity-high' },
            { label: 'Dependencies', value: DATA.quality.dependency_ok ? 'Healthy' : 'Issues', cls: DATA.quality.dependency_ok ? 'severity-low' : 'severity-medium' },
            { label: 'Resources', value: DATA.quality.resources_ok ? 'Healthy' : 'Issues', cls: DATA.quality.resources_ok ? 'severity-low' : 'severity-medium' },
            { label: 'API Usage', value: DATA.quality.api_ok ? 'Healthy' : 'Issues', cls: DATA.quality.api_ok ? 'severity-low' : 'severity-medium' },
            { label: 'Security', value: DATA.quality.security_ok ? 'Healthy' : 'Issues', cls: DATA.quality.security_ok ? 'severity-low' : 'severity-high' }
          ];
          qualitySummary.innerHTML = '';
          const summaryContainer = document.createElement('div');
          summaryContainer.className = 'metric-grid';
          summaryItems.forEach((item) => {
            const card = document.createElement('div');
            card.className = `metric-card ${item.cls}`;
            const label = document.createElement('div');
            label.className = 'label';
            label.textContent = item.label;
            const value = document.createElement('div');
            value.className = 'value';
            value.textContent = item.value;
            card.appendChild(label);
            card.appendChild(value);
            summaryContainer.appendChild(card);
          });
          qualitySummary.appendChild(summaryContainer);

          qualityIssues.innerHTML = '';
          if (!DATA.issues.length) {
            const card = document.createElement('div');
            card.className = 'quality-card';
            card.textContent = 'No issues reported.';
            qualityIssues.appendChild(card);
            return;
          }
          DATA.issues.forEach((issue) => {
            const card = document.createElement('div');
            card.className = 'quality-card';
            const title = document.createElement('h3');
            title.textContent = issue.category || 'Issue';
            const severity = document.createElement('div');
            severity.className = 'severity';
            severity.textContent = `${issue.severity.toUpperCase()} • ${issue.file_path || 'file unknown'}`;
            const message = document.createElement('p');
            message.textContent = issue.message;
            card.appendChild(title);
            card.appendChild(severity);
            card.appendChild(message);
            if (issue.manual_note) {
              const note = document.createElement('p');
              note.className = 'muted';
              note.textContent = issue.manual_note;
              card.appendChild(note);
            }
            qualityIssues.appendChild(card);
          });
        };

        const applyFilters = () => {
          const term = state.search.toLowerCase();
          return DATA.diffs.filter((file) => {
            const severityMatch = state.severity === 'all' || file.severity === state.severity;
            const termMatch = !term || file.display_name.toLowerCase().includes(term);
            return severityMatch && termMatch;
          });
        };

        const renderFileList = () => {
          const files = applyFilters().sort((a, b) => {
            const severityDelta = (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0);
            if (severityDelta) return severityDelta;
            return a.display_name.localeCompare(b.display_name);
          });
          diffListEl.innerHTML = '';
          if (!files.length) {
            const empty = document.createElement('li');
            empty.className = 'muted';
            empty.textContent = 'No files match current filters.';
            diffListEl.appendChild(empty);
            return;
          }
          files.forEach((file) => {
            const item = document.createElement('li');
            item.dataset.fileId = file.id;
            if (state.activeFileId === file.id) {
              item.classList.add('active');
            }
            const title = document.createElement('span');
            title.className = 'name';
            title.textContent = file.display_name;
            const severity = document.createElement('span');
            severity.className = `severity-pill severity-${file.severity}`;
            severity.textContent = severityLabels[file.severity] || 'Low';
            title.appendChild(severity);
            const meta = document.createElement('span');
            meta.className = 'meta';
            meta.textContent = `+${file.added}  −${file.removed}`;
            item.appendChild(title);
            item.appendChild(meta);
            item.addEventListener('click', () => {
              state.activeFileId = file.id;
              renderFileList();
              renderDiff(file);
            });
            diffListEl.appendChild(item);
          });
        };

        const gatherSnippet = (rows, index, side) => {
          const lines = [];
          const start = Math.max(0, index - 3);
          const end = Math.min(rows.length - 1, index + 3);
          for (let i = start; i <= end; i += 1) {
            const row = rows[i];
            const text = side === 'left' ? row.left_text : row.right_text;
            if (text) {
              lines.push(text);
            }
          }
          return lines.join('\n');
        };

        const clearExplanation = () => {
          state.activeRow = null;
          explanationContent.classList.add('muted');
          explanationContent.textContent = 'Select a changed line to request an explanation.';
        };

        const requestExplanation = async (file, row, index, element) => {
          if (state.loading) return;
          const before = gatherSnippet(file.rows, index, 'left');
          const after = gatherSnippet(file.rows, index, 'right');
          if (!before && !after) {
            explanationContent.classList.add('muted');
            explanationContent.textContent = 'No diff context available for this line.';
            return;
          }
          state.loading = true;
          explanationContent.classList.remove('muted');
          explanationContent.textContent = 'Requesting explanation…';
          try {
            const response = await fetch(`${DATA.backend_url}/diff/explain`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                session_id: DATA.session_id,
                file_path: file.file_path,
                line_number: row.right_number || row.left_number || 0,
                before_snippet: before,
                after_snippet: after
              })
            });
            if (!response.ok) {
              const error = await response.json().catch(() => ({ detail: 'Unable to fetch explanation.' }));
              throw new Error(error.detail || 'Unable to fetch explanation.');
            }
            const result = await response.json();
            explanationContent.classList.remove('muted');
            explanationContent.textContent = result.explanation || 'No explanation returned.';
          } catch (err) {
            explanationContent.classList.add('muted');
            explanationContent.textContent = err.message || 'Explanation request failed.';
          } finally {
            state.loading = false;
          }
        };

        const renderDiff = (file) => {
          diffHeader.innerHTML = '';
          const heading = document.createElement('div');
          heading.innerHTML = `<strong>${file.display_name}</strong><br/><span class="muted">${file.file_path}</span>`;
          diffHeader.appendChild(heading);
          diffTableBody.innerHTML = '';
          const rows = file.rows;
          rows.forEach((row, index) => {
            const tr = document.createElement('tr');
            tr.className = `diff-row type-${row.type}`;
            const td = document.createElement('td');
            const wrapper = document.createElement('div');
            wrapper.className = 'diff-code';
            const leftNumber = document.createElement('div');
            leftNumber.className = 'line-number';
            leftNumber.textContent = row.left_number ?? '';
            const leftText = document.createElement('div');
            leftText.className = 'line-text left';
            leftText.textContent = row.left_text || '';
            const rightNumber = document.createElement('div');
            rightNumber.className = 'line-number';
            rightNumber.textContent = row.right_number ?? '';
            const rightText = document.createElement('div');
            rightText.className = 'line-text right';
            rightText.textContent = row.right_text || '';
            wrapper.appendChild(leftNumber);
            wrapper.appendChild(leftText);
            wrapper.appendChild(rightNumber);
            wrapper.appendChild(rightText);
            wrapper.addEventListener('click', () => {
              document.querySelectorAll('.diff-code').forEach((el) => el.classList.remove('selected'));
              wrapper.classList.add('selected');
              requestExplanation(file, row, index, wrapper);
            });
            td.appendChild(wrapper);
            tr.appendChild(td);
            diffTableBody.appendChild(tr);
          });
          clearExplanation();
        };

        diffSearch.addEventListener('input', (event) => {
          state.search = event.target.value;
          renderFileList();
        });

        document.querySelectorAll('.severity-filters button').forEach((button) => {
          button.addEventListener('click', () => {
            document.querySelectorAll('.severity-filters button').forEach((btn) => btn.classList.remove('active'));
            button.classList.add('active');
            state.severity = button.dataset.severity;
            renderFileList();
          });
        });

        renderSummary();
        renderQuality();
        renderFileList();
        const firstFile = applyFilters()[0];
        if (firstFile) {
          state.activeFileId = firstFile.id;
          renderFileList();
          renderDiff(firstFile);
        } else {
          diffHeader.textContent = 'No diffs captured.';
        }
      }());
    </script>
  </body>
</html>
"""


def _normalize_issue_path(path_str: str, session: 'ConversionSession') -> str:
  path = Path(path_str)
  if path.is_absolute():
    for root in (session.target_path, session.project_path):
      try:
        return str(path.relative_to(root))
      except ValueError:
        continue
    return path.name
  return path_str


def generate_conversion_report(session: 'ConversionSession') -> ConversionReport:
  reports_dir = session.target_path / 'reports'
  reports_dir.mkdir(parents=True, exist_ok=True)

  summary = session.progress.summary()
  quality_report = session.quality_report.summary() if session.quality_report else {
    'syntax_passed': True,
    'build_passed': True,
    'dependency_ok': True,
    'resources_ok': True,
    'api_ok': True,
    'security_ok': True,
    'issues': []
  }

  issue_map: Dict[str, List[Dict[str, object]]] = {}
  if session.quality_report:
    for issue in session.quality_report.issues:
      key = _normalize_issue_path(issue.file_path, session) if issue.file_path else '__general__'
      issue_map.setdefault(key, []).append({
        'category': issue.category,
        'message': issue.message,
        'severity': issue.severity,
        'file_path': issue.file_path,
        'manual_note': None
      })

  severity_order = {'error': 'high', 'warning': 'medium', 'info': 'low'}

  diff_entries = []
  for idx, record in enumerate(session.chunks.values()):
    if not record.output_path or not record.chunk.file_path.exists() or not record.output_path.exists():
      continue
    if record.chunk.file_path.is_dir() or record.output_path.is_dir():
      continue
    relative_name = record.chunk.file_path.relative_to(session.project_path)
    file_issues = issue_map.get(str(relative_name), [])
    severity = 'low'
    if file_issues:
      if any(item['severity'].lower() == 'error' for item in file_issues):
        severity = 'high'
      elif any(item['severity'].lower() == 'warning' for item in file_issues):
        severity = 'medium'
    diff_entry = generate_diff_entry(
      record.chunk.file_path,
      record.output_path,
      str(relative_name),
      severity,
      file_issues
    )
    diff_entry['id'] = f"diff-{idx}"
    diff_entries.append(diff_entry)

  report_context = {
    'session_id': session.session_id,
    'project_name': session.project_path.name,
    'direction': session.direction,
    'summary': {
      'converted_files': summary.converted_files,
      'total_files': summary.total_files,
      'tokens_used': summary.tokens_used,
      'cost_usd': summary.cost_usd,
      'elapsed_seconds': summary.elapsed_seconds
    },
    'quality': quality_report,
    'issues': quality_report.get('issues', []),
    'notes': session.summary_notes,
    'diffs': diff_entries,
    'generated_at': time.time(),
    'session_created_at': session.created_at,
    'model': {
      'provider': session.orchestrator_config.provider_id,
      'identifier': session.orchestrator_config.model_identifier
    },
    'benchmarks': session.benchmarks or {},
    'tests': session.test_results or {},
    'backend_url': f"http://{settings.backend_host}:{settings.backend_port}",
    'webhooks': session.webhooks
  }

  summary_path = reports_dir / 'conversion_report.html'
  html = HTML_TEMPLATE.replace('__REPORT_CONTEXT__', json.dumps(report_context))
  summary_path.write_text(html, encoding='utf-8')

  return ConversionReport(
    summary_html=summary_path,
    diff_artifacts=[],
    generated_at=time.time(),
    metadata=report_context
  )
