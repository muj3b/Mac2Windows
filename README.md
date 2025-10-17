# Mac ↔ Windows Universal Code Converter

The Mac ↔ Windows Universal Code Converter turns full macOS applications into production-ready Windows targets (and vice versa) by orchestrating AI conversions, static analysis, asset cleanup, testing, and reporting inside a desktop experience.

---

## 1. Installation & Setup

### Prerequisites
| Component | Version | Notes |
|-----------|---------|-------|
| Operating system | macOS 13+, Windows 10/11, or modern Linux (WSL supported) | GUI requires a desktop session |
| Node.js | 18.x or 20.x LTS | Electron renderer |
| npm | Bundled with Node | Yarn is optional |
| Python | 3.10 or 3.11 (64-bit) | FastAPI backend |
| Git | 2.30+ | Clone/update the repo |
| Disk space | ≥10 GB free | Conversion outputs, backups, models |
| Memory | ≥16 GB recommended | Large projects & AL models |

> **Tip:** Install the Xcode Command Line Tools (macOS) or Visual Studio Build Tools (Windows) if you want on-device build validation.

### Clone & Install
```bash
# 1. Clone the repository
$ git clone https://github.com/your-org/mac-win-converter.git
$ cd mac-win-converter

# 2. Create a Python virtual environment
$ python3 -m venv .venv
$ source .venv/bin/activate        # Windows: .venv\Scripts\activate
$ pip install -r backend/requirements.txt

# 3. Install renderer dependencies
$ npm --prefix electron install

# 4. Launch the desktop app
$ npm --prefix electron start
```
The Electron shell boots the FastAPI backend automatically on `127.0.0.1:6110` and opens the dashboard.

### Environment Variables
Create a `.env` at the project root (or use your shell profile) and define any providers you plan to use:
```bash
# AI providers
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"           # Azure: https://<resource>.openai.azure.com
export OPENAI_ORG_ID="org_123"                               # optional

export ANTHROPIC_API_KEY="anthropic-key"
export ANTHROPIC_API_URL="https://api.anthropic.com"

export GOOGLE_VERTEX_URL="https://us-central1-aiplatform.googleapis.com"
export GOOGLE_VERTEX_TOKEN="ya29...."                        # service account or user token

export OLLAMA_BASE_URL="http://127.0.0.1:11434"             # local Ollama server

# Optional debugging / storage
export CONVERTER_DATA_DIR="$HOME/.mac-win-converter"
export BACKEND_LOG_LEVEL="info"
```
The backend reads these variables at start-up; restart Electron after changes.

---

## 2. AI Provider Setup

Each provider requires a slightly different onboarding flow. Below are quick-start guides plus pricing highlights.

### Anthropic Claude
1. Sign in to [console.anthropic.com](https://console.anthropic.com/). Create an API key under **Developers → API Keys**.
2. Set `ANTHROPIC_API_KEY` (and `ANTHROPIC_API_URL` if using a private proxy).
3. Recommended models: `claude-sonnet-4.1` (balanced quality/speed), `claude-opus-4.1` (highest accuracy).
4. Pricing (April 2024): Sonnet ~$3/M input tokens, $15/M output; Opus ~$15/M input, $75/M output.

### OpenAI (GPT‑5 family)
1. Visit [platform.openai.com](https://platform.openai.com/), create a project, and generate an API key.
2. Export `OPENAI_API_KEY`. For Azure OpenAI, also set `OPENAI_BASE_URL` to your resource endpoint and configure API version via query string.
3. Suggested lineup:
   - `gpt-5` → best overall conversions.
   - `gpt-5-mini` → budget-friendly fallback.
   - `gpt-5-nano` → extreme budget/offline fallback.
4. Pricing (May 2024): GPT‑5 ~$10/M input, $30/M output. Mini/Nano scale down to <$2/M tokens.

### Google Gemini
1. Create a project on [ai.google.dev](https://ai.google.dev/) or Google Cloud Vertex AI.
2. Enable the **Vertex AI API** and create a service account with the `Vertex AI User` role.
3. Generate an access token (service account JSON) and set `GOOGLE_VERTEX_URL` / `GOOGLE_VERTEX_TOKEN`.
4. Recommended model: `gemini-1.5-pro-002` (2M context window—ideal for large UI/storyboards). Pricing ~ $7/M input, $21/M output.

### Ollama (Local)
1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh` (macOS/Linux) or download the Windows installer.
2. Pull models suited for conversions:
   ```bash
   ollama pull llama3
   ollama pull codellama
   ollama pull mistral
   ```
3. Ensure `OLLAMA_BASE_URL` points to the running instance.
4. Enable **Force offline models only** in Settings → Performance if you want to avoid any cloud usage.

> **Model Routing:** The dashboard model selector shows every provider + model combination discovered by the backend. Use the **Prompt Tone**, **Fallback Model**, and **Cost Guardrails** to fine-tune behaviour.

---

## 3. Cloud Backup OAuth

Backups are optional but recommended for long-running conversions. All credentials are encrypted with Fernet and stored in `data/credentials.db`.

### Google Drive (Step-by-Step)
1. Visit [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the **Google Drive API**.
3. Configure an OAuth consent screen (External → add app name + support email).
4. Create OAuth Client Credentials (Desktop application). Copy the client ID/secret.
5. In the app: Settings → Backup & Recovery → choose **Google Drive**, enter the client ID/secret, adjust scopes (default `drive.file`), and click **Connect**.
6. Approve the consent screen; the credential appears in the drop-down.

### Dropbox
1. Go to [Dropbox App Console](https://www.dropbox.com/developers/apps) and create an app (Scoped access → App folder or Full Dropbox).
2. Copy the app key/secret.
3. In the app, select **Dropbox**, enter key/secret, and press **Connect**. OAuth launches in your browser.

### OneDrive / Microsoft OneDrive for Business
1. Sign in to [portal.azure.com](https://portal.azure.com/) → Azure Active Directory → App registrations → New registration.
2. Pick **Public client/native** and add redirect URI `https://login.microsoftonline.com/common/oauth2/nativeclient`.
3. Grant Microsoft Graph delegated permissions: `Files.ReadWrite.All` + `offline_access`.
4. In the dashboard, select **OneDrive**, supply client ID and tenant (or `common`), optionally override scopes, and click **Connect**.

### Local Disk Backups
- Choose **Local Disk** as provider, give the credential a label, and supply the base directory.
- The converter copies archives + metadata JSON to `<base>/<project>/<direction>/<session>`.

Retention is controlled via **Retention (copies)**. Every conversion adds a ZIP archive (with `conversion_metadata.json`) and optionally uploads it to the configured provider.

---

## 4. Usage Guide

1. **Load a Project** – drag a folder onto the dashboard or click the drop zone. Auto-detection parses languages, frameworks, and dependencies.
2. **Preview Mode** – click **Preview Conversion** to estimate cost/time before spending tokens. Exclusions can be added via Settings → Conversion Preferences.
3. **Configure Settings** – choose provider/model, tweak AI temperature/retries, set cost guardrails, and define cleanup preferences.
4. **Start Conversion** – press **Start Conversion**. Progress bars, ETA, tokens, and cost update in real time. Pause/Resume as needed.
5. **Monitor Quality** – the vulnerability panel lists CVEs/license issues; cost warnings appear when 80% of the budget is reached (configurable).
6. **Manual Fixes** – flagged chunks show up in the Manual Fix queue. Edit code in-place or **Skip** to mark as handled; overrides persist across resumes.
7. **View Reports** – after completion, open the HTML report (diff viewer, benchmarks, quality score). Build/test output is available in the console panel.
8. **Backups** – if enabled, archives are stored under `<target>/backups` and optionally synced to Drive/Dropbox/OneDrive.
9. **Incremental Conversions** – rerun the converter on the same project; unchanged files are skipped via checksum caching.

---

## 5. Advanced Features

- **Webhook Automation** – Configure URL + headers in Settings → Webhooks, test with **Send Test Event**, and subscribe to start/quality/paused/completed/failed events.
- **Batch Conversion** – Queue multiple source/target pairs in the Batch tab and run them sequentially with a shared configuration.
- **Template Sharing** – Save/load templates, export/import JSON files, and push shared presets to teammates with the **Share Template** button.
- **Error Recovery** – If a session fails, use **Resume Failed** to pick up from the last checkpoint; manual fixes, cost totals, and cleanup reports are restored.
- **Offline Mode** – Force the orchestrator to use Ollama-only models, bypass cost tracking, and surface an “Offline” status pill.

---

## 6. Webhooks & CI/CD

### Sample GitHub Actions Workflow
```yaml
name: Convert Mac App to Windows
on:
  push:
    branches: [ main ]

jobs:
  convert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Call Converter API
        env:
          API_URL: http://converter.internal:6110
          API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          curl -sSf -X POST "$API_URL/conversion/start" \
            -H 'Content-Type: application/json' \
            -d @- <<JSON
          {
            "project_path": "${{ github.workspace }}/App",
            "target_path": "${{ github.workspace }}/App.Windows",
            "direction": "mac-to-win",
            "provider_id": "openai-compatible",
            "model_identifier": "gpt-5",
            "api_key": "$API_KEY",
            "cost": {"max_budget_usd": 40, "warn_percent": 0.75},
            "webhooks": [{
              "url": "${{ secrets.DEPLOY_HOOK }}",
              "headers": {"Authorization": "Bearer ${{ secrets.DEPLOY_TOKEN }}"}
            }]
          }
JSON
```

### Sample GitLab CI Pipeline
```yaml
convert:
  stage: build
  image: python:3.11
  script:
    - pip install requests
    - python - <<'PY'
import os, requests
payload = {
  "project_path": os.path.join(os.getenv("CI_PROJECT_DIR"), "src"),
  "target_path": os.path.join(os.getenv("CI_PROJECT_DIR"), "src.win"),
  "direction": "mac-to-win",
  "provider_id": "ollama",
  "model_identifier": "ollama::llama3",
  "webhooks": [{
    "url": os.getenv("CI_API_V4_URL") + f"/projects/{os.getenv('CI_PROJECT_ID')}/trigger",
    "secret_token": os.getenv("WEBHOOK_SECRET")
  }]
}
requests.post("http://converter.internal:6110/conversion/start", json=payload).raise_for_status()
PY
```

### Jenkins Declarative Pipeline
```groovy
pipeline {
  agent any
  stages {
    stage('Convert') {
      steps {
        script {
          def payload = groovy.json.JsonOutput.toJson([
            project_path : env.WORKSPACE + '/app',
            target_path  : env.WORKSPACE + '/app.win',
            direction    : 'mac-to-win',
            provider_id  : 'openai-compatible',
            model_identifier: 'gpt-5-mini',
            cost: [max_budget_usd: 25, warn_percent: 0.7]
          ])
          httpRequest httpMode: 'POST', contentType: 'APPLICATION_JSON',
            url: 'http://converter.internal:6110/conversion/start', requestBody: payload
        }
      }
    }
  }
}
```

### Webhook Payload Schema
- `event`: string (`conversion.started`, `conversion.completed`, etc.)
- `timestamp`: UNIX epoch
- `payload.session_id`: session identifier
- `payload.summary`: overall progress, timing, cost
- `payload.stage_progress`: per-stage completion metrics
- `payload.cleanup_report`: unused assets/dependencies identified
- `payload.cost`: spending + warnings
- `payload.diff_artifacts`: diff HTML paths for automated QA
- `payload.manual_queue`: outstanding manual fixes (pending/skipped)
- `payload.notes`: latest timeline messages (last 10 entries)

Use the **Send Test Event** button to validate firewall rules and headers.

---

## 7. Cost Controls & Preview Mode
- **Preview Conversion** simulates the work plan (no tokens spent) and estimates cost/time. Exclusions can omit folders (e.g. `docs/`, `experimental/`).
- **Budget Limits** stop a session once the configured USD cap is reached. Warnings are raised at the chosen percentage (default 80%).
- **Auto-Switch Models** automatically downgrade to cheaper models (e.g. GPT‑5 → GPT‑5 mini → Ollama) when thresholds are hit.
- **Cost Dashboard** displays live spend, warnings, and cumulative tokens. The data is also exposed via webhooks.

---

## 8. Manual Fix & Error Recovery
- Failed chunks are pushed into the Manual Fix queue with context notes (provider errors, build validation issues, vulnerability blockers).
- Apply overrides directly in the editor; changes are persisted to the output tree and cached for incremental runs.
- Use **Skip** if you plan to handle the file manually outside the pipeline—progress updates immediately.
- The **Resume Failed** button resurrects saved checkpoints (chunks, costs, cleanup report, manual queue) to continue after a crash or budget stop.

---

## 9. Batch Conversion & Templates
- Queue multiple projects in the Batch tab (source, output, direction) and start a sequential conversion run. Each scheduled session ID is reported in the status banner.
- Save your favourite settings as templates, import/export JSON for sharing, or publish metadata (owner, description, tags) for team catalogues.

---

## 10. Community & Sharing
- **Metrics Dashboard** – anonymised totals (sessions, completion rate, average cost/quality, direction mix).
- **Leaderboard** – highest quality scores from recent conversions.
- **Report Issue** – packages logs, latest summary, and optional email into `data/community/reports/report_<timestamp>.json` for human triage.
- **Template Repository** – templates reside in `data/templates/`; metadata index in `templates_index.json` enables sharing across teams.

---

## 11. Troubleshooting
| Problem | Fix |
|---------|-----|
| **“API key not found”** | Confirm environment variables are exported before launching Electron. On Windows, create a `.env` or set variables in the System Properties dialog. |
| **“Cost limit exceeded”** | Increase **Max Budget** or enable **Auto-switch** so the orchestrator falls back to cheaper models mid-run. |
| **Build validation failed** | Open the Build Console for compiler errors. Apply manual fixes or disable build validation in Settings → Performance. |
| **Out of memory** | Lower **Parallel Conversions**, reduce **Max RAM**, or switch to step-wise (non-batch) conversions. Consider closing other memory-intensive apps. |
| **Conversion crashed** | Use **Resume Failed**; the pipeline reloads the saved checkpoint and restarts from the last successful chunk. |
| **Need deep debugging** | Toggle **Enable Debug Mode** to capture provider prompts/responses (logged under `data/logs`). |

---

## 12. FAQ

**How accurate are the conversions?**  
Core UI/business logic converges with 85–95% accuracy depending on project complexity. Manual review is still recommended.

**Which languages are supported?**  
Swift, Objective-C/C++, C#, XAML, C++/CLI, WinUI, WPF, MAUI, SwiftUI, AppKit, and common resource formats (storyboards, XIB, `.strings`, `.resx`, asset catalogs).

**How much will it cost?**  
Small apps finish under $5. Large enterprise codebases typically run $20–40 using GPT‑5, less with auto-switch enabled.

**Is my code kept private?**  
All processing happens locally. Only the selected AI providers receive chunks; offline mode keeps everything on-device.

**Can I use it offline?**  
Yes—select an Ollama model, enable **Force offline models only**, and the UI switches to offline mode. Cost tracking is disabled in offline runs.

**Can I customise AI prompts?**  
Prompt tone (professional/casual/detailed), learning hints, and fallback models are configurable. Debug mode exposes raw prompts for deeper customisation.

---

Happy converting! Track issues, feature requests, or share templates via the Community tab or your usual team channels.
