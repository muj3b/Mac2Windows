# Mac ↔ Windows Universal Code Converter

End-to-end automation for translating macOS apps to Windows (and the reverse) with AI orchestration, quality gates, cost controls, and collaboration tooling.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Getting Started](#getting-started)
3. [AI Provider Setup](#ai-provider-setup)
4. [Cloud Backup OAuth](#cloud-backup-oauth)
5. [Using the Dashboard](#using-the-dashboard)
6. [Webhooks & CI/CD](#webhooks--cicd)
7. [Cost Controls & Preview Mode](#cost-controls--preview-mode)
8. [Manual Fix & Error Recovery](#manual-fix--error-recovery)
9. [Batch Conversion & Templates](#batch-conversion--templates)
10. [Community & Sharing](#community--sharing)
11. [Troubleshooting](#troubleshooting)
12. [FAQ](#faq)

## Architecture Overview

```
monorepo
├── electron/           # Electron shell + renderer UI
│   ├── main.js         # Launches renderer + supervises Python backend
│   ├── preload.js      # Sandboxed bridge API exposed to the renderer
│   └── src/renderer/   # HTML/CSS/JS for the dashboard
└── backend/            # FastAPI orchestration service
    ├── conversion/     # Session manager, work planner, cleanup, cost control
    ├── ai/             # Provider registry, model router, orchestrator
    ├── detection/      # Language/framework/dependency discovery
    ├── quality/        # Syntax/build/QA + AI self-review
    ├── reports/        # Conversion report + diff generator
    ├── storage/        # SQLite/ChromaDB persistence, template repo
    └── security/       # License + vulnerability scanners
```

Key backend services expose REST APIs for conversion management, template storage, webhook dispatch, community metrics, and reporting. The renderer communicates exclusively through the preload bridge to maintain sandboxed isolation.

## Getting Started

1. **Install backend dependencies**
   ```bash
   cd /Users/mujeb/mac\ to\ windows
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

2. **Install renderer dependencies**
   ```bash
   cd electron
   npm install
   ```

3. **Run the application**
   ```bash
   # from the project root with the virtualenv activated
   npm --prefix electron start
   ```
   The Electron process spawns the FastAPI backend automatically (default `127.0.0.1:6110`).

## AI Provider Setup

The converter auto-detects configured providers and displays every model exposed by the backend registry. Set the relevant environment variables before launching:

| Provider          | Environment variables                                                                                                      | Notes |
|-------------------|-----------------------------------------------------------------------------------------------------------------------------|-------|
| OpenAI / Azure    | `OPENAI_API_KEY`, `OPENAI_BASE_URL` (Azure), `OPENAI_ORG_ID`                                                                | GPT‑5, GPT‑5 mini, GPT‑5 nano |
| Anthropic         | `ANTHROPIC_API_KEY`, `ANTHROPIC_API_URL`                                                                                    | Claude Sonnet / Opus |
| Google           | `GOOGLE_VERTEX_URL`, `GOOGLE_VERTEX_TOKEN` *(if using Vertex or Gemini-compatible gateway)*                                | Gemini 1.5/Flash |
| Ollama (local)    | `OLLAMA_BASE_URL` *(default `http://127.0.0.1:11434`)*                                                                      | Llama3, CodeLlama, custom ggml |

Additional notes:
- Tokens, cost, and provider metadata flow into the session summary and webhook payloads.
- Model fallbacks are configured in the **Settings → Performance & AI Strategy** panel.
- Offline-only mode forces Ollama/local providers (indicated in the status pill).

## Cloud Backup OAuth

Enable cloud mirroring in **Settings → Backup & Recovery**. Credentials are encrypted via `data/credentials.db` and managed through the UI.

### Google Drive (OAuth)
1. Create a Google Cloud project and OAuth consent screen (external).
2. Create OAuth client credentials (Desktop).
3. In the UI, enter *Client ID*, *Client Secret*, optional *Scopes* (default `https://www.googleapis.com/auth/drive.file`).
4. Click **Connect**; a browser window opens. Approve access and return—credentials appear in the drop-down.

### Dropbox
1. Create a Dropbox app (Scoped access → App folder or Full Dropbox).
2. Generate an app key/secret.
3. Provide the key/secret in the UI, leave scopes empty (Dropbox scopes are implied).
4. Complete the OAuth flow and select the stored credential.

### OneDrive / Microsoft 365
1. Register an Azure AD application (public client, device flow).
2. Supply *Client ID*, optional *Tenant* (default `common`), add scopes like `Files.ReadWrite.All offline_access`.
3. Complete the OAuth dance; new credentials appear in the selector.

Local backups can be targeted to any writable directory (e.g. external drive) via the **Save Path** button. Retention limits are enforced per session.

## Using the Dashboard

The UI is organised into four tabs:

1. **Dashboard** – project intake, health monitors, preview summary, progress timeline, manual fix queue, vulnerability dashboard, cost tracker, and build console.
2. **Settings** – conversion preferences, performance/AI tuning, cost guardrails, webhook editor, template manager, and backup configuration.
3. **Batch** – enqueue multiple projects (direction + paths) and run them sequentially with shared settings.
4. **Community** – anonymised success metrics, leaderboard, and one-click issue reports.

### Manual Fix Queue
- Pending fixes appear in the left column; selecting one pre-fills the notes area.
- Paste or type the corrected code and hit **Apply Manual Fix** to override the generated output.
- Applied fixes update the progress tracker and feed the learning memory for subsequent conversions.

### Vulnerability Alerts
- Security and license issues flagged during dependency conversion surface here.
- Severity is mirrored in the quality report and webhook payloads.
- Critical issues automatically enqueue manual fixes.

### Build Console
- Streams backend logs (fetch via **Refresh**) including build/test output, AI retry messages, and warnings.
- Enable debug mode to capture prompt metadata for triage.

## Webhooks & CI/CD

### Event Types
| Event | Description |
|-------|-------------|
| `conversion.started`   | Fired as soon as a session begins (includes preview estimate, applied settings, project type).
| `conversion.quality_ready` | Emitted after the quality stage completes (includes quality score, issues, benchmarks, cleanup results).
| `conversion.paused`    | Fired when a session pauses (manual, cost budget, or error).
| `conversion.completed` | Fired when all stages finish successfully (full summary, diff artifacts, backup links).
| `conversion.failed`    | Fired if an unrecoverable error occurs (error note, manual fix counts, latest stage).

### Payload Structure (excerpt)
```json
{
  "session_id": "abcd1234",
  "status": "completed",
  "direction": "mac-to-win",
  "project_type": "game",
  "offline_mode": false,
  "summary": {
    "overall_percentage": 1.0,
    "converted_files": 128,
    "total_files": 132,
    "elapsed_seconds": 843,
    "tokens_used": 98542,
    "cost_usd": 23.17
  },
  "stage_progress": {
    "CODE": {"completed": 98, "total": 99, "percentage": 0.99}
  },
  "cleanup_report": {
    "unused_assets": ["Assets/legacy_logo.png"],
    "total_bytes_reclaimed": 4194304,
    "auto_deleted": []
  },
  "cost": {
    "total": 23.17,
    "max_budget": 50.0,
    "percent": 0.46,
    "warnings": []
  },
  "diff_artifacts": [
    {"source": "AppDelegate.swift", "target": "Program.cs", "diff_html": "/reports/AppDelegate.diff.html"}
  ],
  "backups": [{"provider": "gdrive", "remote_url": "https://drive.google.com/..."}],
  "manual_queue": [],
  "notes": ["Conversion finished", "Benchmarks completed without regressions."]
}
```
Custom headers are supported (e.g. `Authorization: Bearer ...`). Webhook retries use exponential backoff (2.5s base, 3 attempts).

### GitHub Actions Sample
```yaml
name: Trigger Conversion
on:
  workflow_dispatch:
jobs:
  convert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Call converter
        run: |
          curl -X POST "http://127.0.0.1:6110/conversion/start" \
            -H 'Content-Type: application/json' \
            -d '{
              "project_path": "${{ github.workspace }}/MyApp",
              "target_path": "${{ github.workspace }}/MyApp.Win",
              "direction": "mac-to-win",
              "provider_id": "openai-compatible",
              "model_identifier": "gpt-5",
              "webhooks": [{
                "url": "${{ secrets.DEPLOY_HOOK }}",
                "headers": {"Authorization": "Bearer ${{ secrets.DEPLOY_TOKEN }}"}
              }]
            }'
```

### GitLab CI Sample
```yaml
convert:
  stage: build
  image: python:3.11
  script:
    - pip install requests
    - |
      python - <<'PY'
      import requests, os
      payload = {
        "project_path": os.getenv("CI_PROJECT_DIR") + "/src",
        "target_path": os.getenv("CI_PROJECT_DIR") + "/src.win",
        "direction": "mac-to-win",
        "provider_id": "ollama",
        "model_identifier": "ollama::llama3",
        "webhooks": [
          {"url": os.getenv("CI_API_V4_URL") + "/projects/${CI_PROJECT_ID}/trigger", "secret_token": os.getenv("WEBHOOK_SECRET")}
        ]
      }
      requests.post("http://converter.internal:6110/conversion/start", json=payload).raise_for_status()
      PY
```

### Jenkinsfile Snippet
```groovy
pipeline {
  agent any
  stages {
    stage('Convert') {
      steps {
        script {
          httpRequest httpMode: 'POST', contentType: 'APPLICATION_JSON', url: 'http://converter.internal:6110/conversion/start',
                      requestBody: groovy.json.JsonOutput.toJson([
                        project_path: env.WORKSPACE + '/app',
                        target_path : env.WORKSPACE + '/app.win',
                        direction   : 'mac-to-win',
                        provider_id : 'openai-compatible',
                        model_identifier: 'gpt-5-mini',
                        cost: [max_budget_usd: 30, warn_percent: 0.7]
                      ])
        }
      }
    }
  }
}
```

## Cost Controls & Preview Mode

- **Preview Conversion** analyses the project without issuing AI calls, estimating cost, time, and impacted files. Exclude specific folders via templates or exclusions.
- **Cost Guardrails** halt sessions when the configured budget is exceeded. Warnings trigger model fallback (e.g. GPT‑5 → GPT‑5 mini → Ollama) if auto-switch is enabled.
- Live spend and percent-of-budget are shown in the dashboard and sent to webhooks.
- Fallbacks can also be configured for quality (AI settings) or manual via the settings panel.

## Manual Fix & Error Recovery

- Provider failures, validation issues, and manual review requests populate the queue automatically.
- Fixes are persisted and re-applied to matching chunks during resume runs.
- The **Resume Failed** button rehydrates previous progress, cost totals, manual fixes, and quality report before resuming the pipeline.
- Error events never abort the entire conversion; failed chunks are flagged for manual action without blocking subsequent stages.

## Batch Conversion & Templates

- Add multiple projects in the **Batch** tab—each entry captures source, target, and direction. The batch runner reuses the settings from the **Settings** tab.
- Batch execution calls the REST API for every project and surfaces new session IDs in the status pill.
- Templates store conversion/performance/AI presets plus optional metadata (owner, tags). Share templates across the team, delete obsolete ones, or load with a single click.

## Community & Sharing

- **Metrics** – anonymised stats (completion rate, average cost/quality, direction mix) sourced from the persistent session store.
- **Leaderboard** – top sessions ranked by quality score. Useful for internal showcases or regression spotting.
- **Report Issue** – bundles logs, latest summary, and optional contact email into `data/community/reports/report_<timestamp>.json`. Users review before sharing.
- **Template Repository** – saved templates live under `data/templates` with metadata tracked in `templates_index.json`.

## Troubleshooting

| Symptom | Resolution |
|---------|------------|
| Conversion stalls at 0% | Verify backend health, ensure AI credentials are valid, and check logs for provider errors. Resume after correcting. |
| Cost budget reached | Increase the limit in settings or enable auto-switch with cheaper fallback models. |
| OAuth window fails to open | Copy the displayed authorization URL into a browser manually; upon success the backend displays the credential. |
| Webhook not invoked | Check retry logs in the console, confirm the URL accepts POST+JSON, ensure secret header matches your service. |
| Manual fix not applied | Ensure code is supplied; the override writes directly to the output file and updates the incremental cache. |

## FAQ

**Do I need the full Apple or Windows SDKs installed?**
Only for optional build/test validation stages. The converter itself operates on source text.

**Can I run entirely offline?**
Yes—select Ollama (or a local model) and enable *Force offline models only*. Cost tracking switches to local-only mode.

**Where are backups stored?**
Per session under `<target>/backups/`. Cloud mirrors (Drive/Dropbox/OneDrive) contain identical archives plus `conversion_metadata.json`.

**How are manual fixes reused?**
Applied fixes update the learning memory. After three identical overrides the converter auto-applies the patch to similar chunks in future sessions.

**What security data is collected?**
Only anonymised aggregate metrics (number of conversions, average quality/cost) for the community dashboard. Disable metrics by clearing `data/community`.

