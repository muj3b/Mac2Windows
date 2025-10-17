const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const state = {
  direction: 'mac-to-win',
  projectPath: null,
  detection: null,
  sessionId: null,
  progressTimer: null,
  logTimer: null,
  templates: [],
  webhooks: [],
  manualFixes: [],
  selectedManualFix: null,
  previewEstimate: null,
  batchQueue: [],
  community: null,
  backupProviders: [],
  costSettings: {
    enabled: true,
    max_budget_usd: 50,
    warn_percent: 0.8,
    auto_switch_model: true,
    fallback_model_identifier: 'gpt-5-nano',
    fallback_provider_id: 'ollama'
  }
};

const elements = {
  tabButtons: $$('.tab-button'),
  tabContents: $$('.tab-content'),
  backendStatus: $('#backend-status'),
  resourceStatus: $('#resource-status'),
  offlineIndicator: $('#session-offline-indicator'),
  directionButtons: $$('.direction-button'),
  dropzone: $('#dropzone'),
  folderInput: $('#folder-input'),
  selectedPath: $('#selected-path'),
  btnRescan: $('#btn-rescan'),
  btnPreview: $('#btn-preview'),
  btnStart: $('#btn-start'),
  btnResumeFailed: $('#btn-resume-failed'),
  btnPause: $('#btn-pause'),
  btnResume: $('#btn-resume'),
  btnViewLogs: $('#btn-view-logs'),
  btnRefreshLogs: $('#btn-refresh-logs'),
  btnApplyFix: $('#btn-apply-fix'),
  btnSkipFix: $('#btn-skip-fix'),
  btnSaveTemplate: $('#btn-save-template'),
  btnLoadTemplate: $('#btn-load-template'),
  btnShareTemplate: $('#btn-share-template'),
  btnAddWebhook: $('#btn-add-webhook'),
  btnTestWebhooks: $('#btn-test-webhooks'),
  btnImportTemplate: $('#btn-import-template'),
  btnExportTemplate: $('#btn-export-template'),
  btnBatchAdd: $('#btn-batch-add'),
  btnBatchClear: $('#btn-batch-clear'),
  btnBatchStart: $('#btn-batch-start'),
  btnRefreshCommunity: $('#btn-refresh-community'),
  btnSubmitIssue: $('#btn-submit-issue'),
  modelProvider: $('#model-provider'),
  modelIdentifier: $('#model-identifier'),
  apiKey: $('#api-key'),
  targetFramework: $('#target-framework'),
  languageOutput: $('#language-output'),
  debugToggle: $('#debug-toggle'),
  detectionSummary: $('#detection-summary'),
  detectionResults: $('#detection-results'),
  previewSummary: $('#preview-summary'),
  previewCards: $('#preview-cards'),
  progressStats: $('#progress-stats'),
  progressTime: $('#progress-time'),
  progressLog: $('#progress-log'),
  stageProgress: $('#stage-progress'),
  qualityScorePill: $('#quality-score-pill'),
  manualFixList: $('#manual-fix-list'),
  manualFixCount: $('#manual-fix-count'),
  manualFixNote: $('#manual-fix-note'),
  manualFixCode: $('#manual-fix-code'),
  manualFixAuthor: $('#manual-fix-author'),
  btnApplyLearned: $('#btn-apply-learned'),
  vulnerabilityList: $('#vulnerability-list'),
  vulnerabilityCount: $('#vulnerability-count'),
  costSummary: $('#cost-summary'),
  costBudgetPill: $('#cost-budget-pill'),
  buildConsole: $('#build-console'),
  webhookRows: $('#webhook-rows'),
  templateList: $('#template-list'),
  batchQueue: $('#batch-queue'),
  batchStatus: $('#batch-status'),
  batchProjectPath: $('#batch-project-path'),
  batchTargetPath: $('#batch-target-path'),
  batchDirection: $('#batch-direction'),
  communityMetrics: $('#community-metrics'),
  communityLeaderboard: $('#community-leaderboard'),
  issueSession: $('#issue-session-id'),
  issueEmail: $('#issue-email'),
  issueDescription: $('#issue-description'),
  issueIncludeLogs: $('#issue-include-logs'),
  issueResponse: $('#issue-response'),
  templateName: $('#template-name'),
  templateDescription: $('#template-description'),
  templateOwner: $('#template-owner'),
  templateTags: $('#template-tags'),
  costEnabled: $('#cost-enabled'),
  costMax: $('#cost-max'),
  costWarn: $('#cost-warn'),
  costAutoSwitch: $('#cost-auto-switch'),
  costFallbackModel: $('#cost-fallback-model'),
  costFallbackProvider: $('#cost-fallback-provider'),
  aiTemp: $('#ai-temp'),
  aiStrategy: $('#ai-strategy'),
  aiRetries: $('#ai-retries'),
  aiOffline: $('#ai-offline'),
  aiPromptTone: $('#ai-prompt-tone'),
  aiFallbackModel: $('#ai-fallback-model'),
  aiFallbackProvider: $('#ai-fallback-provider'),
  aiSmartPrompts: $('#ai-smart-prompts'),
  codeStyle: $('#code-style'),
  commentStyle: $('#comment-style'),
  namingStyle: $('#naming-style'),
  errorStyle: $('#error-style'),
  cleanupUnused: $('#cleanup-unused'),
  cleanupAutodelete: $('#cleanup-autodelete'),
  cleanupMinBytes: $('#cleanup-min-bytes'),
  qualityThreshold: $('#quality-threshold'),
  enableLearning: $('#enable-learning'),
  learningTrigger: $('#learning-trigger'),
  maxCpu: $('#max-cpu'),
  maxRam: $('#max-ram'),
  threads: $('#threads'),
  apiRate: $('#api-rate'),
  parallelConversions: $('#parallel-conversions'),
  buildTimeout: $('#build-timeout'),
  preferOffline: $('#prefer-offline'),
  backupEnabled: $('#backup-enabled'),
  backupProvider: $('#backup-provider'),
  backupCredential: $('#backup-credential'),
  backupRemotePath: $('#backup-remote-path'),
  backupRetention: $('#backup-retention'),
  backupCredentialLabel: $('#backup-credential-label'),
  backupClientId: $('#backup-client-id'),
  backupClientSecret: $('#backup-client-secret'),
  backupScopes: $('#backup-scopes'),
  backupRootFolder: $('#backup-root-folder'),
  backupTenant: $('#backup-tenant'),
  backupLocalPath: $('#backup-local-path'),
  btnBackupConnect: $('#btn-backup-connect'),
  btnBackupRefresh: $('#btn-backup-refresh'),
  btnBackupSaveLocal: $('#btn-backup-save-local'),
  buildConsolePre: $('#build-console'),
  communityMetricsPanel: $('#community-metrics'),
  progressSummary: $('#progress-summary'),
  loadingOverlay: $('#loading-overlay'),
  webhookFeedback: $('#webhook-feedback')
};

function setLoading(isLoading, message = 'Working…') {
  if (!elements.loadingOverlay) return;
  const label = elements.loadingOverlay.querySelector('.spinner-label');
  if (label) label.textContent = message;
  if (isLoading) {
    elements.loadingOverlay.classList.remove('hidden');
  } else {
    elements.loadingOverlay.classList.add('hidden');
  }
}

function clearTimers() {
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
  if (state.logTimer) {
    clearInterval(state.logTimer);
    state.logTimer = null;
  }
}

function initTabs() {
  elements.tabButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const tabId = button.dataset.tab;
      elements.tabButtons.forEach((btn) => btn.classList.toggle('active', btn === button));
      elements.tabContents.forEach((content) => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
      });
    });
  });
}

function setDirection(direction) {
  state.direction = direction;
  elements.directionButtons.forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.direction === direction);
  });
  hydrateTargetFrameworks();
}

function hydrateTargetFrameworks() {
  const frameworks =
    state.direction === 'mac-to-win'
      ? [
          { value: 'winui3', label: 'WinUI 3 (.NET 8)' },
          { value: 'wpf-net8', label: 'WPF (.NET 8)' },
          { value: 'wpf-legacy', label: 'WPF (.NET 4.8)' },
          { value: 'maui', label: '.NET MAUI (cross-platform)' },
          { value: 'winforms', label: 'WinForms (modernized)' }
        ]
      : [
          { value: 'swiftui', label: 'SwiftUI (macOS 14+)' },
          { value: 'appkit', label: 'AppKit (macOS 11+)' },
          { value: 'catalyst', label: 'Mac Catalyst (shared iOS/macOS)' }
        ];
  elements.targetFramework.innerHTML = '';
  frameworks.forEach((framework) => {
    const option = document.createElement('option');
    option.value = framework.value;
    option.textContent = framework.label;
    elements.targetFramework.appendChild(option);
  });
}

function initDirectionButtons() {
  elements.directionButtons.forEach((button) => {
    button.addEventListener('click', () => setDirection(button.dataset.direction));
  });
  setDirection(state.direction);
}

function initDropzone() {
  elements.dropzone.addEventListener('click', () => elements.folderInput.click());
  ['dragenter', 'dragover'].forEach((eventName) => {
    elements.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropzone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((eventName) => {
    elements.dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.dropzone.classList.remove('dragover');
    });
  });
  elements.dropzone.addEventListener('drop', (event) => {
    const { files } = event.dataTransfer;
    if (!files || files.length === 0) return;
    const path = files[0].path;
    handleProjectSelected(path);
  });
  elements.folderInput.addEventListener('change', (event) => {
    const { files } = event.target;
    if (!files || files.length === 0) return;
    handleProjectSelected(files[0].webkitRelativePath.split('/')[0] ? files[0].path.split(files[0].webkitRelativePath)[0] : files[0].path);
  });
}

function handleProjectSelected(projectPath) {
  if (!projectPath) return;
  state.projectPath = projectPath;
  elements.selectedPath.textContent = projectPath;
  elements.btnRescan.disabled = false;
  elements.btnPreview.disabled = false;
  elements.btnStart.disabled = false;
  detectProject();
}

async function detectProject() {
  if (!state.projectPath) return;
  elements.detectionSummary.textContent = 'Scanning…';
  elements.detectionSummary.className = 'summary-pill summary-pill--muted';
  try {
    const result = await window.macWinBridge.detectProject(state.projectPath, { direction: state.direction });
    state.detection = result;
    renderDetection(result);
    elements.detectionSummary.textContent = 'Scan Complete';
    elements.detectionSummary.className = 'summary-pill status-pill--ok';
  } catch (error) {
    elements.detectionSummary.textContent = 'Scan Failed';
    elements.detectionSummary.className = 'summary-pill status-pill--error';
    elements.detectionResults.innerHTML = `<div class="placeholder">${error?.message || 'Detection failed.'}</div>`;
  }
}

function renderDetection(result) {
  if (!result || result.error) {
    elements.detectionResults.innerHTML = '<div class="placeholder">Detection failed. Check logs for details.</div>';
    return;
  }
  const languages = (result.languages || [])
    .map((lang) => `<div><strong>${lang.name}</strong> • ${lang.files} files • ${lang.lines} lines</div>`)
    .join('');
  const frameworks = [...(result.frameworks?.mac || []), ...(result.frameworks?.windows || [])]
    .map((item) => `<span class="chip">${item.name} ${item.version ? `(${item.version})` : ''}</span>`)
    .join('');
  const dependencies = (result.dependencies || [])
    .map((dep) => `<li>${dep.name}${dep.version ? `@${dep.version}` : ''} (${dep.manager})</li>`)
    .join('');
  elements.detectionResults.innerHTML = `
    <div class="detection-grid">
      <div>
        <h3>Languages</h3>
        <div class="detection-list">${languages || '<span class="muted">n/a</span>'}</div>
      </div>
      <div>
        <h3>Frameworks</h3>
        <div class="chip-row">${frameworks || '<span class="muted">n/a</span>'}</div>
      </div>
      <div>
        <h3>Dependencies</h3>
        <ul>${dependencies || '<span class="muted">n/a</span>'}</ul>
      </div>
    </div>
  `;
}

async function updateBackendHealth() {
  try {
    const status = await window.macWinBridge.getBackendHealth();
    if (status.status === 'ok') {
      elements.backendStatus.textContent = 'Backend: ok';
      elements.backendStatus.className = 'status-pill status-pill--ok';
    } else {
      elements.backendStatus.textContent = 'Backend: down';
      elements.backendStatus.className = 'status-pill status-pill--error';
    }
  } catch (error) {
    elements.backendStatus.textContent = 'Backend: error';
    elements.backendStatus.className = 'status-pill status-pill--error';
  }
}

async function updateResourceSnapshot() {
  try {
    const snapshot = await window.macWinBridge.getResourceSnapshot();
    if (snapshot.error) throw new Error(snapshot.error);
    const cpu = snapshot.cpu?.percent != null ? `${snapshot.cpu.percent}% CPU` : 'CPU n/a';
    const memory = snapshot.memory?.percent != null ? `${snapshot.memory.percent}% RAM` : 'RAM n/a';
    const disk = snapshot.disk?.free_gb != null ? `${snapshot.disk.free_gb.toFixed(1)} GB free` : 'Disk n/a';
    elements.resourceStatus.textContent = `Resources: ${cpu}, ${memory}, ${disk}`;
    elements.resourceStatus.className = 'status-pill status-pill--ok';
  } catch (error) {
    elements.resourceStatus.textContent = 'Resources: unavailable';
    elements.resourceStatus.className = 'status-pill status-pill--warn';
  }
}

function gatherConversionSettings() {
  return {
    code_style: elements.codeStyle.value,
    comments: elements.commentStyle.value,
    naming: elements.namingStyle.value,
    error_handling: elements.errorStyle.value,
    cleanup_unused_assets: elements.cleanupUnused.checked,
    cleanup_auto_delete: elements.cleanupAutodelete.checked,
    cleanup_min_bytes: Number(elements.cleanupMinBytes.value || 0) * 1024,
    preview_mode: false,
    exclusions: [],
    quality_score_threshold: Number(elements.qualityThreshold.value || 0.7),
    enable_learning: elements.enableLearning.checked,
    learning_trigger_count: Number(elements.learningTrigger.value || 3)
  };
}

function gatherPerformanceSettings() {
  return {
    max_cpu: Number(elements.maxCpu.value || 80),
    max_ram_gb: Number(elements.maxRam.value || 16),
    threads: Number(elements.threads.value || 4),
    api_rate_limit: Number(elements.apiRate.value || 30),
    parallel_conversions: Number(elements.parallelConversions.value || 1),
    build_timeout_seconds: Number(elements.buildTimeout.value || 600),
    prefer_offline: elements.preferOffline.checked
  };
}

function gatherAISettings() {
  return {
    temperature: Number(elements.aiTemp.value || 0.2),
    strategy: elements.aiStrategy.value,
    retries: Number(elements.aiRetries.value || 3),
    offline_only: elements.aiOffline.checked,
    prompt_tone: elements.aiPromptTone.value,
    fallback_model_identifier: elements.aiFallbackModel.value || null,
    fallback_provider_id: elements.aiFallbackProvider.value || null,
    smart_prompting: elements.aiSmartPrompts.checked
  };
}

function gatherCostSettings() {
  state.costSettings = {
    enabled: elements.costEnabled.checked,
    max_budget_usd: Number(elements.costMax.value || 0),
    warn_percent: Number(elements.costWarn.value || 80) / 100,
    auto_switch_model: elements.costAutoSwitch.checked,
    fallback_model_identifier: elements.costFallbackModel.value || null,
    fallback_provider_id: elements.costFallbackProvider.value || null
  };
  return state.costSettings;
}

function gatherBackupSettings() {
  return {
    enabled: elements.backupEnabled.checked,
    provider: elements.backupProvider.value,
    retention_count: Number(elements.backupRetention.value || 10),
    remote_path: elements.backupRemotePath.value || '{project}/{direction}',
    credential_id: elements.backupCredential.value || null
  };
}

function gatherWebhooks() {
  return state.webhooks
    .filter((hook) => hook.url)
    .map((hook) => ({
      url: hook.url,
      events: hook.events,
      headers: hook.headers,
      secret_token: hook.secret
    }));
}

function ensureWebhooksInitialized() {
  if (state.webhooks.length === 0) {
    state.webhooks.push({ url: '', headers: {}, events: ['conversion.completed'], secret: '' });
  }
  if (elements.webhookFeedback) {
    elements.webhookFeedback.textContent = '';
  }
  renderWebhooks();
}

function renderWebhooks() {
  elements.webhookRows.removeEventListener('input', handleWebhookInput);
  elements.webhookRows.removeEventListener('click', handleWebhookRemove);
  elements.webhookRows.innerHTML = '';
  state.webhooks.forEach((hook, index) => {
    const row = document.createElement('div');
    row.className = 'webhook-row';
    row.innerHTML = `
      <input type="text" placeholder="https://example.com/webhook" value="${hook.url || ''}" data-field="url" data-index="${index}" />
      <input type="text" placeholder="Headers (key:value, one per line)" value="${serializeHeaders(hook.headers)}" data-field="headers" data-index="${index}" />
      <input type="text" placeholder="Events (comma separated)" value="${(hook.events || []).join(', ')}" data-field="events" data-index="${index}" />
      <div class="input-with-actions">
        <input type="text" placeholder="Secret token" value="${hook.secret || ''}" data-field="secret" data-index="${index}" />
        <button class="secondary-button secondary-button--danger" data-remove="${index}">×</button>
      </div>
    `;
    elements.webhookRows.appendChild(row);
  });
  elements.webhookRows.addEventListener('input', handleWebhookInput);
  elements.webhookRows.addEventListener('click', handleWebhookRemove);
}

function handleWebhookInput(event) {
  const target = event.target;
  const index = Number(target.dataset.index);
  if (Number.isNaN(index)) return;
  const field = target.dataset.field;
  if (!field) return;
  const hook = state.webhooks[index];
  if (!hook) return;
  if (field === 'url') {
    hook.url = target.value.trim();
  } else if (field === 'headers') {
    hook.headers = parseHeaders(target.value);
  } else if (field === 'events') {
    hook.events = target.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  } else if (field === 'secret') {
    hook.secret = target.value.trim();
  }
}

function handleWebhookRemove(event) {
  const button = event.target.closest('button[data-remove]');
  if (!button) return;
  const index = Number(button.dataset.remove);
  state.webhooks.splice(index, 1);
  ensureWebhooksInitialized();
}

function serializeHeaders(headers = {}) {
  return Object.entries(headers)
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n');
}

function parseHeaders(input) {
  const lines = input.split(/\n|;/).map((line) => line.trim()).filter(Boolean);
  const headers = {};
  lines.forEach((line) => {
    const [key, ...rest] = line.split(':');
    if (!key || rest.length === 0) return;
    headers[key.trim()] = rest.join(':').trim();
  });
  return headers;
}

function addWebhookRow() {
  state.webhooks.push({ url: '', headers: {}, events: ['conversion.completed'], secret: '' });
  renderWebhooks();
}

function showWebhookFeedback(message, tone = 'info') {
  if (!elements.webhookFeedback) return;
  elements.webhookFeedback.textContent = message;
  elements.webhookFeedback.classList.remove('success', 'error');
  if (tone === 'success') {
    elements.webhookFeedback.classList.add('success');
  } else if (tone === 'error') {
    elements.webhookFeedback.classList.add('error');
  }
}

async function testWebhooks() {
  const webhooks = gatherWebhooks();
  if (!webhooks.length) {
    showWebhookFeedback('Add at least one webhook URL before testing.', 'error');
    return;
  }
  try {
    setLoading(true, 'Testing webhooks…');
    const response = await window.macWinBridge.testWebhook({ webhooks });
    if (response.error) {
      throw new Error(response.message);
    }
    const results = response.results || [];
    const successCount = results.length;
    if (successCount === webhooks.length) {
      showWebhookFeedback(`Webhook test succeeded (${successCount}/${webhooks.length}).`, 'success');
    } else {
      showWebhookFeedback(`Webhook test partially succeeded (${successCount}/${webhooks.length}). Check logs for details.`, 'error');
    }
  } catch (error) {
    console.error('Webhook test failed', error);
    showWebhookFeedback(error.message || 'Webhook test failed', 'error');
  } finally {
    setLoading(false);
  }
}

function renderManualFixes() {
  const pendingFixes = (state.manualFixes || []).filter(
    (entry) => entry.status !== 'applied' && entry.status !== 'skipped'
  );
  if (state.selectedManualFix && !pendingFixes.find((fix) => fix.chunk_id === state.selectedManualFix.chunk_id)) {
    state.selectedManualFix = null;
  }
  elements.manualFixList.innerHTML = '';
  if (!pendingFixes.length) {
    elements.manualFixList.innerHTML = '<div class="placeholder">No manual fixes pending 🎉</div>';
    elements.manualFixCount.textContent = '0 pending';
  } else {
    pendingFixes.forEach((fix) => {
      const item = document.createElement('div');
      item.className = 'manual-fix-item';
      item.dataset.chunkId = fix.chunk_id;
      item.innerHTML = `
        <strong>${fix.file_path}</strong>
        <div class="muted">${fix.reason}</div>
      `;
      if (state.selectedManualFix && state.selectedManualFix.chunk_id === fix.chunk_id) {
        item.classList.add('active');
      }
      elements.manualFixList.appendChild(item);
    });
    elements.manualFixCount.textContent = `${pendingFixes.length} pending`;
  }
  elements.btnApplyFix.disabled = !state.selectedManualFix;
  if (elements.btnSkipFix) {
    elements.btnSkipFix.disabled = !state.selectedManualFix;
  }
  if (elements.btnApplyLearned) {
    elements.btnApplyLearned.disabled = !state.sessionId || !pendingFixes.length;
  }
}

function handleManualFixSelection(event) {
  const target = event.target.closest('.manual-fix-item');
  if (!target) return;
  const chunkId = target.dataset.chunkId;
  const fix = state.manualFixes.find((entry) => entry.chunk_id === chunkId);
  state.selectedManualFix = fix || null;
  elements.manualFixCode.value = '';
  elements.manualFixNote.value = fix?.notes?.join('\n') || '';
  elements.manualFixAuthor.value = fix?.submitted_by || '';
  renderManualFixes();
}

async function applyManualFix() {
  if (!state.sessionId || !state.selectedManualFix) return;
  const payload = {
    code: elements.manualFixCode.value,
    note: elements.manualFixNote.value,
    submitted_by: elements.manualFixAuthor.value || undefined
  };
  try {
    setLoading(true, 'Applying manual fix…');
    await window.macWinBridge.submitManualFix(state.sessionId, state.selectedManualFix.chunk_id, payload);
    await refreshManualFixes();
    elements.manualFixCode.value = '';
    elements.manualFixNote.value = '';
  } catch (error) {
    console.error('Manual fix failed', error);
  } finally {
    setLoading(false);
  }
}

async function refreshManualFixes() {
  if (!state.sessionId) return;
  const response = await window.macWinBridge.listManualFixes(state.sessionId);
  state.manualFixes = response.manual_fixes || [];
  renderManualFixes();
}

async function skipManualFix() {
  if (!state.sessionId || !state.selectedManualFix) return;
  try {
    setLoading(true, 'Skipping manual fix…');
    await window.macWinBridge.skipManualFix(state.sessionId, state.selectedManualFix.chunk_id, elements.manualFixNote.value || undefined);
    state.selectedManualFix = null;
    elements.manualFixCode.value = '';
    elements.manualFixNote.value = '';
    await refreshManualFixes();
  } catch (error) {
    console.error('Skip manual fix failed', error);
  } finally {
    setLoading(false);
  }
}

async function applyLearnedPatterns() {
  if (!state.sessionId) return;
  try {
    setLoading(true, 'Applying learned patterns…');
    const response = await window.macWinBridge.applyLearnedPatterns(state.sessionId);
    if (response.error) {
      throw new Error(response.message);
    }
    await refreshManualFixes();
    if (response.summary) {
      renderProgress(response.summary);
    } else {
      await refreshSummary();
    }
  } catch (error) {
    console.error('Apply learned patterns failed', error);
  } finally {
    setLoading(false);
  }
}

function renderVulnerabilities(issues) {
  const alerts = (issues || []).filter((issue) => issue.severity && issue.severity.toLowerCase() !== 'info');
  elements.vulnerabilityCount.textContent = alerts.length ? `${alerts.length} alerts` : 'No alerts';
  if (alerts.length === 0) {
    elements.vulnerabilityList.innerHTML = '<div class="placeholder">All clear! 🎉</div>';
    return;
  }
  elements.vulnerabilityList.innerHTML = alerts
    .map(
      (issue) => `
        <div class="alert">
          <strong>${issue.category}</strong><br />
          ${issue.message}${issue.file_path ? ` • <span class="muted">${issue.file_path}</span>` : ''}
        </div>
      `
    )
    .join('');
}

function renderCost(summary) {
  if (!summary || !summary.cost_settings) {
    elements.costSummary.innerHTML = '<div class="placeholder">Budget tracking not enabled.</div>';
    elements.costBudgetPill.textContent = 'Budget idle';
    return;
  }
  const total = summary.cost_usd || 0;
  const max = summary.cost_settings.max_budget_usd || 0;
  const percent = summary.cost_percent_consumed != null ? summary.cost_percent_consumed : max ? total / max : 0;
  const percentDisplay = Math.min(percent * 100, 999).toFixed(1);
  elements.costBudgetPill.textContent = max ? `$${total.toFixed(2)} / $${max.toFixed(2)}` : `$${total.toFixed(2)} spent`;
  elements.costBudgetPill.className = `summary-pill ${percent > 0.9 ? 'status-pill--warn' : 'status-pill--muted'}`;
  const warnings = summary.warnings && summary.warnings.length ? summary.warnings.map((w) => `<li>${w}</li>`).join('') : '';
  elements.costSummary.innerHTML = `
    <div class="cost-details">
      <div>Tokens used: ${summary.tokens_used || 0}</div>
      <div>Budget used: ${percentDisplay}%</div>
      <div class="cost-bar"><span style="width:${Math.min(percent, 1) * 100}%"></span></div>
      ${warnings ? `<ul class="muted">${warnings}</ul>` : ''}
    </div>
  `;
}

async function refreshVulnerabilities(summary) {
  if (!state.sessionId) {
    renderVulnerabilities(summary?.quality_report?.issues || []);
    return;
  }
  try {
    const response = await window.macWinBridge.getVulnerabilities(state.sessionId);
    if (response.error) {
      throw new Error(response.message);
    }
    renderVulnerabilities(response.issues || []);
  } catch (error) {
    renderVulnerabilities(summary?.quality_report?.issues || []);
  }
}

function renderProgress(summary) {
  if (!summary) return;
  elements.qualityScorePill.textContent = summary.quality_score != null ? `Quality: ${(summary.quality_score * 100).toFixed(0)}%` : 'Quality: –';
  elements.progressStats.textContent = `${summary.converted_files || 0} / ${summary.total_files || 0} files converted`;
  elements.progressTime.textContent = `Elapsed: ${formatDuration(summary.elapsed_seconds)} • ETA: ${formatDuration(summary.estimated_seconds_remaining)}`;
  if (summary.current_chunk) {
    elements.progressLog.innerHTML = `<div><strong>${summary.current_chunk.file_path}</strong> • ${summary.current_chunk.summary || ''}</div>`;
  }
  renderStageProgress(summary);
  renderCost(summary);
  renderPreview(summary.preview_estimate);
  updateOfflineIndicator(summary.offline_mode);
}

function renderStageProgress(summary) {
  const stageEntries = Object.entries(summary.stage_progress || {});
  if (!stageEntries.length) {
    elements.stageProgress.innerHTML = '<div class="placeholder">No progress yet.</div>';
    return;
  }
  elements.stageProgress.innerHTML = stageEntries
    .map(([stage, progress]) => {
      const pct = Math.min(progress.percentage || 0, 1) * 100;
      return `
        <div class="stage-row">
          <div><strong>${stage}</strong></div>
          <div>${progress.completed_units}/${progress.total_units}</div>
          <div class="progress-meter"><span style="width:${pct}%"></span></div>
        </div>
      `;
    })
    .join('');
}

function renderPreview(estimate) {
  state.previewEstimate = estimate;
  if (!estimate) {
    elements.previewSummary.classList.add('hidden');
    elements.previewCards.innerHTML = '';
    return;
  }
  elements.previewSummary.classList.remove('hidden');
  elements.previewCards.innerHTML = `
    <div class="card">
      <div class="muted">Estimated Cost</div>
      <strong>$${(estimate.estimated_cost_usd || 0).toFixed(2)}</strong>
    </div>
    <div class="card">
      <div class="muted">Estimated Time</div>
      <strong>${formatDuration((estimate.estimated_minutes || 0) * 60)}</strong>
    </div>
    <div class="card">
      <div class="muted">Impacted Files</div>
      <strong>${estimate.impacted_files || 0}</strong>
    </div>
  `;
}

function formatDuration(seconds) {
  if (seconds == null) return '–';
  const totalSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  const hours = Math.floor(minutes / 60);
  const minsDisplay = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${minsDisplay}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

function updateOfflineIndicator(offline) {
  elements.offlineIndicator.textContent = offline ? 'Mode: Offline' : 'Mode: Online';
  elements.offlineIndicator.className = `status-pill ${offline ? 'status-pill--warn' : 'status-pill--ok'}`;
}

function renderTemplates(templates) {
  state.templates = templates || [];
  if (!templates.length) {
    elements.templateList.innerHTML = '<div class="placeholder">No templates saved yet.</div>';
    return;
  }
  elements.templateList.innerHTML = templates
    .map((tpl) => {
      const tags = (tpl.tags || []).map((tag) => `<span class="chip">${tag}</span>`).join(' ');
      return `
        <div class="template-card">
          <div class="template-card__header">
            <strong>${tpl.name}</strong>
            <span class="muted">${tpl.owner || 'local'}</span>
          </div>
          <p>${tpl.description || 'No description provided.'}</p>
          <div class="chip-row">${tags}</div>
          <div class="template-card__actions">
            <button class="secondary-button" data-template-load="${tpl.name}">Load</button>
            <button class="secondary-button secondary-button--danger" data-template-delete="${tpl.name}">Delete</button>
          </div>
        </div>
      `;
    })
    .join('');
}

function renderBatchQueue() {
  if (!state.batchQueue.length) {
    elements.batchQueue.innerHTML = '<div class="placeholder">Queue is empty. Add multiple projects to convert them sequentially.</div>';
    elements.btnBatchStart.disabled = true;
    return;
  }
  elements.batchQueue.innerHTML = state.batchQueue
    .map((item, index) => `
      <div class="batch-item">
        <div><strong>${item.project_path}</strong> → ${item.target_path}</div>
        <div class="muted">${item.direction}</div>
        <button class="secondary-button secondary-button--danger" data-batch-remove="${index}">Remove</button>
      </div>
    `)
    .join('');
  elements.btnBatchStart.disabled = false;
}

function renderCommunityMetrics() {
  const metrics = state.community;
  if (!metrics) {
    elements.communityMetrics.innerHTML = '<div class="placeholder">Refresh to load community stats.</div>';
    elements.communityLeaderboard.innerHTML = '<div class="placeholder">No leaderboard data yet.</div>';
    return;
  }
  const stats = metrics.stats || {};
  const directions = stats.directions || {};
  elements.communityMetrics.innerHTML = `
    <div class="metric-card"><div class="muted">Total Sessions</div><strong>${stats.total_sessions || 0}</strong></div>
    <div class="metric-card"><div class="muted">Completed</div><strong>${stats.completed_sessions || 0}</strong></div>
    <div class="metric-card"><div class="muted">Avg Cost</div><strong>$${(stats.avg_cost_usd || 0).toFixed(2)}</strong></div>
    <div class="metric-card"><div class="muted">Avg Quality</div><strong>${stats.avg_quality_score != null ? (stats.avg_quality_score * 100).toFixed(0) : '–'}%</strong></div>
    <div class="metric-card"><div class="muted">Mac → Win</div><strong>${directions['mac-to-win'] || 0}</strong></div>
    <div class="metric-card"><div class="muted">Win → Mac</div><strong>${directions['win-to-mac'] || 0}</strong></div>
  `;
  const leaderboard = stats.leaderboard || [];
  if (!leaderboard.length) {
    elements.communityLeaderboard.innerHTML = '<div class="placeholder">No leaderboard data yet.</div>';
  } else {
    elements.communityLeaderboard.innerHTML = leaderboard
      .map((entry) => `
        <div class="entry">
          <span>${entry.session_id}</span>
          <span>${(entry.score * 100).toFixed(0)}%</span>
        </div>
      `)
      .join('');
  }
}

async function previewConversion() {
  if (!state.projectPath) return;
  const payload = {
    project_path: state.projectPath,
    direction: state.direction,
    exclusions: []
  };
  try {
    setLoading(true, 'Analyzing project…');
    const response = await window.macWinBridge.previewConversion(payload);
    if (response.error) {
      throw new Error(response.message);
    }
    renderPreview(response.preview);
  } catch (error) {
    console.error('Preview failed', error);
    elements.previewSummary.classList.remove('hidden');
    elements.previewCards.innerHTML = `<div class="card">Preview failed: ${error?.message || 'Unknown error'}</div>`;
  }
  setLoading(false);
}

function collectStartPayload() {
  const { conversion, performance, ai } = collectTemplateSettings();
  return {
    project_path: state.projectPath,
    target_path: state.projectPath && state.direction === 'mac-to-win' ? `${state.projectPath}-windows` : `${state.projectPath}-mac`,
    direction: state.direction,
    provider_id: elements.modelProvider.value || 'openai-compatible',
    model_identifier: elements.modelIdentifier.value || 'gpt-5',
    api_key: elements.apiKey.value || undefined,
    conversion,
    performance,
    ai,
    cost: gatherCostSettings(),
    webhooks: gatherWebhooks(),
    incremental: false,
    git: null,
    backup: gatherBackupSettings()
  };
}

function collectTemplateSettings() {
  return {
    conversion: gatherConversionSettings(),
    performance: gatherPerformanceSettings(),
    ai: gatherAISettings()
  };
}

async function startConversion() {
  if (!state.projectPath) return;
  setLoading(true, 'Starting conversion…');
  const payload = collectStartPayload();
  payload.target_path = await promptForTargetPath(payload.target_path);
  if (!payload.target_path) {
    setLoading(false);
    return;
  }
  try {
    const response = await window.macWinBridge.startConversion(payload);
    if (response.error) {
      throw new Error(response.message);
    }
    state.sessionId = response.session_id;
    state.manualFixes = [];
    state.selectedManualFix = null;
    elements.manualFixCode.value = '';
    elements.manualFixNote.value = '';
    renderManualFixes();
    elements.btnPause.disabled = false;
    elements.btnResume.disabled = true;
    elements.btnPreview.disabled = false;
    elements.btnResumeFailed.disabled = false;
    clearTimers();
    startProgressTimer();
  } catch (error) {
    console.error('Unable to start conversion', error);
  } finally {
    setLoading(false);
  }
}

async function resumeFailedConversion() {
  if (!state.sessionId) return;
  setLoading(true, 'Resuming conversion…');
  const payload = {
    session_id: state.sessionId,
    provider_id: elements.modelProvider.value || undefined,
    model_identifier: elements.modelIdentifier.value || undefined,
    api_key: elements.apiKey.value || undefined
  };
  try {
    const response = await window.macWinBridge.resumeFailedConversion(payload);
    if (response.error) {
      throw new Error(response.message);
    }
    state.sessionId = response.session_id;
    elements.btnResumeFailed.disabled = false;
    clearTimers();
    startProgressTimer();
  } catch (error) {
    console.error('Unable to resume conversion', error);
  } finally {
    setLoading(false);
  }
}

async function pauseConversion() {
  if (!state.sessionId) return;
  await window.macWinBridge.pauseConversion(state.sessionId);
  elements.btnPause.disabled = true;
  elements.btnResume.disabled = false;
}

async function resumeConversion() {
  if (!state.sessionId) return;
  await window.macWinBridge.resumeConversion(state.sessionId);
  elements.btnPause.disabled = false;
  elements.btnResume.disabled = true;
}

async function startProgressTimer() {
  clearTimers();
  await refreshSummary();
  state.progressTimer = setInterval(refreshSummary, 4000);
  state.logTimer = setInterval(refreshLogs, 6000);
}

async function refreshSummary() {
  if (!state.sessionId) return;
  const response = await window.macWinBridge.getConversionStatus(state.sessionId);
  if (response.error) {
    console.error(response.message);
    return;
  }
  const summary = response.summary;
  if (!summary) return;
  renderProgress(summary);
  await refreshVulnerabilities(summary);
  await refreshManualFixes();
  await refreshLogs();
  if (!summary.paused) {
    elements.btnPause.disabled = false;
    elements.btnResume.disabled = true;
  }
  if (summary.paused) {
    elements.btnPause.disabled = true;
    elements.btnResume.disabled = false;
  }
  if (summary.overall_percentage >= 1) {
    clearTimers();
    elements.btnPause.disabled = true;
    elements.btnResume.disabled = true;
    setLoading(false);
  }
}

async function promptForTargetPath(defaultPath) {
  return defaultPath;
}

async function refreshLogs() {
  const response = await window.macWinBridge.getBuildOutput(200);
  if (response.error) return;
  const entries = response.entries || [];
  if (!entries.length) {
    elements.buildConsole.textContent = 'No build output yet.';
  } else {
    elements.buildConsole.textContent = entries.map((entry) => `${entry.timestamp || ''} ${entry.message}`).join('\n');
  }
  elements.buildConsole.scrollTop = elements.buildConsole.scrollHeight;
}

async function loadTemplates() {
  const response = await window.macWinBridge.listTemplates();
  if (response.error) return;
  renderTemplates(response.templates || []);
}

async function loadModelProviders() {
  try {
    const response = await window.macWinBridge.listModels();
    let providers = response.providers || [];
    if (!Array.isArray(providers) && typeof providers === 'object') {
      providers = Object.values(providers);
    }
    if (!providers.length) {
      providers = [
        { id: 'openai-compatible', display_name: 'OpenAI Compatible' },
        { id: 'ollama', display_name: 'Ollama (local)' }
      ];
    }
    elements.modelProvider.innerHTML = '';
    providers.forEach((provider) => {
      const option = document.createElement('option');
      if (typeof provider === 'string') {
        option.value = provider;
        option.textContent = provider;
      } else {
        option.value = provider.id || provider.name;
        option.textContent = provider.display_name || provider.name || provider.id;
      }
      elements.modelProvider.appendChild(option);
    });
  } catch (error) {
    console.error('Failed to load providers', error);
  }
}

async function loadBackupProviders() {
  try {
    const response = await window.macWinBridge.listBackupProviders();
    if (response.error) {
      throw new Error(response.message);
    }
    const providers = response.providers || [];
    state.backupProviders = providers;
    elements.backupProvider.innerHTML = '';
    const previousSelection = elements.backupProvider.value;
    providers.forEach((provider) => {
      const option = document.createElement('option');
      option.value = provider.id;
      option.textContent = provider.name || provider.id;
      elements.backupProvider.appendChild(option);
    });
    if (providers.length) {
      const defaultProviderId = providers.find((provider) => provider.id === previousSelection)?.id || providers[0].id;
      elements.backupProvider.value = defaultProviderId;
      populateBackupCredentials(defaultProviderId);
    } else {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No providers configured';
      elements.backupProvider.appendChild(option);
      populateBackupCredentials('');
    }
  } catch (error) {
    console.error('Failed to load backup providers', error);
  }
}

function populateBackupCredentials(providerId) {
  const provider = state.backupProviders.find((item) => item.id === providerId);
  elements.backupCredential.innerHTML = '';
  if (provider && Array.isArray(provider.credentials) && provider.credentials.length) {
    provider.credentials.forEach((credential) => {
      const option = document.createElement('option');
      option.value = credential.id;
      option.textContent = credential.label || credential.id;
      elements.backupCredential.appendChild(option);
    });
  } else {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No credentials linked';
    elements.backupCredential.appendChild(option);
  }
  updateBackupForm(provider);
}

function updateBackupForm(provider) {
  const requiresOAuth = provider?.requires_oauth;
  const isLocal = provider?.id === 'local';
  ['backup-client-field', 'backup-secret-field', 'backup-scopes-field', 'backup-root-field', 'backup-tenant-field'].forEach((clazz) => {
    $$('.' + clazz).forEach((node) => {
      node.style.display = requiresOAuth ? 'flex' : 'none';
    });
  });
  $$('.backup-local-field').forEach((node) => {
    node.style.display = isLocal ? 'flex' : 'none';
  });
}

async function connectBackupProvider() {
  const providerId = elements.backupProvider.value;
  const provider = state.backupProviders.find((item) => item.id === providerId);
  if (!provider) return;
  try {
    if (provider.requires_oauth) {
      const config = {
        client_id: elements.backupClientId.value,
        client_secret: elements.backupClientSecret.value,
        label: elements.backupCredentialLabel.value || `${providerId}-oauth`,
        scopes: elements.backupScopes.value ? elements.backupScopes.value.split(',').map((scope) => scope.trim()).filter(Boolean) : provider.scopes,
        root_folder: elements.backupRootFolder.value || undefined,
        tenant: elements.backupTenant.value || undefined
      };
      const result = await window.macWinBridge.startBackupOAuth(providerId, config);
      if (result?.auth_url) {
        window.macWinBridge.openExternal(result.auth_url);
      }
    } else {
      const body = {
        label: elements.backupCredentialLabel.value || `${providerId}-credential`,
        data: {}
      };
      if (providerId === 'local') {
        body.data.base_path = elements.backupLocalPath.value || undefined;
      }
      await window.macWinBridge.createBackupCredential(providerId, body);
    }
    await loadBackupProviders();
  } catch (error) {
    console.error('Failed to connect backup provider', error);
  }
}

async function saveTemplate() {
  const { conversion, performance, ai } = collectTemplateSettings();
  const payload = {
    name: elements.templateName.value || 'default-template',
    description: elements.templateDescription.value || '',
    owner: elements.templateOwner.value || 'local',
    tags: elements.templateTags.value ? elements.templateTags.value.split(',').map((tag) => tag.trim()).filter(Boolean) : [],
    conversion,
    performance,
    ai
  };
  const response = await window.macWinBridge.saveTemplate(payload);
  if (response.error) {
    console.error(response.message);
    return;
  }
  await loadTemplates();
}

async function loadTemplateByName(name) {
  const response = await window.macWinBridge.loadTemplate(name);
  if (response.error || !response.template) return;
  const tpl = response.template;
  applyTemplateSettings(tpl);
}

async function shareTemplate() {
  try {
    const payload = {
      name: elements.templateName.value,
      description: elements.templateDescription.value,
      owner: elements.templateOwner.value || 'community',
      tags: elements.templateTags.value ? elements.templateTags.value.split(',').map((tag) => tag.trim()).filter(Boolean) : []
    };
    const response = await window.macWinBridge.shareTemplate(payload);
    if (response.error) {
      console.error(response.message);
    }
  } catch (error) {
    console.error(error);
  }
}

async function deleteTemplate(name) {
  const response = await window.macWinBridge.deleteTemplate(name);
  if (response.error) {
    console.error(response.message);
    return;
  }
  await loadTemplates();
}

async function importTemplate() {
  const response = await window.macWinBridge.importTemplate();
  if (response.cancelled) {
    return;
  }
  if (response.error) {
    console.error(response.message);
    return;
  }
  if (response.template) {
    applyTemplateSettings(response.template);
    if (response.template.name) {
      elements.templateName.value = response.template.name;
    }
  }
  await loadTemplates();
}

async function exportTemplate() {
  const { conversion, performance, ai } = collectTemplateSettings();
  await window.macWinBridge.exportTemplate(elements.templateName.value || 'template', {
    conversion,
    performance,
    ai,
    metadata: {
      description: elements.templateDescription.value || '',
      owner: elements.templateOwner.value || 'local',
      tags: elements.templateTags.value ? elements.templateTags.value.split(',').map((tag) => tag.trim()).filter(Boolean) : []
    }
  });
}

function applyTemplateSettings(template) {
  if (template.conversion) {
    elements.codeStyle.value = template.conversion.code_style || elements.codeStyle.value;
    elements.commentStyle.value = template.conversion.comments || elements.commentStyle.value;
    elements.namingStyle.value = template.conversion.naming || elements.namingStyle.value;
    elements.errorStyle.value = template.conversion.error_handling || elements.errorStyle.value;
    elements.cleanupUnused.checked = template.conversion.cleanup_unused_assets ?? elements.cleanupUnused.checked;
    elements.cleanupAutodelete.checked = template.conversion.cleanup_auto_delete ?? elements.cleanupAutodelete.checked;
    elements.cleanupMinBytes.value = Math.round((template.conversion.cleanup_min_bytes || 1024 * 1024) / 1024);
    elements.qualityThreshold.value = template.conversion.quality_score_threshold ?? elements.qualityThreshold.value;
    elements.enableLearning.checked = template.conversion.enable_learning ?? elements.enableLearning.checked;
    elements.learningTrigger.value = template.conversion.learning_trigger_count ?? elements.learningTrigger.value;
  }
  if (template.performance) {
    elements.maxCpu.value = template.performance.max_cpu ?? elements.maxCpu.value;
    elements.maxRam.value = template.performance.max_ram_gb ?? elements.maxRam.value;
    elements.threads.value = template.performance.threads ?? elements.threads.value;
    elements.apiRate.value = template.performance.api_rate_limit ?? elements.apiRate.value;
    elements.parallelConversions.value = template.performance.parallel_conversions ?? elements.parallelConversions.value;
    elements.buildTimeout.value = template.performance.build_timeout_seconds ?? elements.buildTimeout.value;
    elements.preferOffline.checked = template.performance.prefer_offline ?? elements.preferOffline.checked;
  }
  if (template.ai) {
    elements.aiTemp.value = template.ai.temperature ?? elements.aiTemp.value;
    elements.aiStrategy.value = template.ai.strategy ?? elements.aiStrategy.value;
    elements.aiRetries.value = template.ai.retries ?? elements.aiRetries.value;
    elements.aiOffline.checked = template.ai.offline_only ?? elements.aiOffline.checked;
    elements.aiPromptTone.value = template.ai.prompt_tone || elements.aiPromptTone.value;
    elements.aiFallbackModel.value = template.ai.fallback_model_identifier || '';
    elements.aiFallbackProvider.value = template.ai.fallback_provider_id || '';
    elements.aiSmartPrompts.checked = template.ai.smart_prompting ?? elements.aiSmartPrompts.checked;
  }
}

async function loadCommunityMetrics() {
  const response = await window.macWinBridge.getCommunityMetrics();
  if (response.error) {
    console.error(response.message);
    return;
  }
  state.community = response;
  renderCommunityMetrics();
}

async function submitIssueReport() {
  const payload = {
    session_id: elements.issueSession.value || undefined,
    email: elements.issueEmail.value || undefined,
    description: elements.issueDescription.value,
    include_logs: elements.issueIncludeLogs.checked
  };
  const response = await window.macWinBridge.submitIssueReport(payload);
  if (response.error) {
    elements.issueResponse.textContent = response.message;
  } else {
    elements.issueResponse.textContent = `Report saved to ${response.report_path}`;
  }
}

function addBatchItem() {
  if (!elements.batchProjectPath.value || !elements.batchTargetPath.value) return;
  state.batchQueue.push({
    project_path: elements.batchProjectPath.value,
    target_path: elements.batchTargetPath.value,
    direction: elements.batchDirection.value
  });
  elements.batchProjectPath.value = '';
  elements.batchTargetPath.value = '';
  renderBatchQueue();
}

function clearBatchQueue() {
  state.batchQueue = [];
  renderBatchQueue();
}

async function startBatchConversion() {
  if (!state.batchQueue.length) {
    elements.batchStatus.textContent = 'Queue is empty';
    return;
  }
  setLoading(true, 'Scheduling batch conversion…');
  const payload = collectStartPayload();
  const batchPayload = {
    projects: state.batchQueue,
    provider_id: payload.provider_id,
    model_identifier: payload.model_identifier,
    api_key: payload.api_key,
    conversion: payload.conversion,
    performance: payload.performance,
    ai: payload.ai,
    cost: payload.cost,
    incremental: payload.incremental,
    backup: payload.backup
  };
  try {
    const response = await window.macWinBridge.startBatchConversion(batchPayload);
    if (response.error) {
      throw new Error(response.message);
    }
    elements.batchStatus.textContent = `Scheduled sessions: ${response.scheduled_sessions.length}`;
    clearBatchQueue();
  } catch (error) {
    console.error('Batch conversion failed', error);
  } finally {
    setLoading(false);
  }
}

function attachEventListeners() {
  elements.btnRescan.addEventListener('click', detectProject);
  elements.btnPreview.addEventListener('click', previewConversion);
  elements.btnStart.addEventListener('click', startConversion);
  elements.btnResumeFailed.addEventListener('click', resumeFailedConversion);
  elements.btnPause.addEventListener('click', pauseConversion);
  elements.btnResume.addEventListener('click', resumeConversion);
  elements.btnViewLogs.addEventListener('click', refreshLogs);
  elements.btnRefreshLogs.addEventListener('click', refreshLogs);
  elements.btnApplyFix.addEventListener('click', applyManualFix);
  if (elements.btnSkipFix) {
    elements.btnSkipFix.addEventListener('click', skipManualFix);
  }
  if (elements.btnApplyLearned) {
    elements.btnApplyLearned.addEventListener('click', applyLearnedPatterns);
  }
  elements.manualFixList.addEventListener('click', handleManualFixSelection);
  elements.btnSaveTemplate.addEventListener('click', saveTemplate);
  elements.btnLoadTemplate.addEventListener('click', () => {
    const name = elements.templateName.value;
    if (name) loadTemplateByName(name);
  });
  if (elements.btnImportTemplate) {
    elements.btnImportTemplate.addEventListener('click', importTemplate);
  }
  if (elements.btnExportTemplate) {
    elements.btnExportTemplate.addEventListener('click', exportTemplate);
  }
  elements.templateList.addEventListener('click', (event) => {
    const loadButton = event.target.closest('button[data-template-load]');
    const deleteButton = event.target.closest('button[data-template-delete]');
    if (loadButton) loadTemplateByName(loadButton.dataset.templateLoad);
    if (deleteButton) deleteTemplate(deleteButton.dataset.templateDelete);
  });
  elements.btnShareTemplate.addEventListener('click', shareTemplate);
  elements.btnAddWebhook.addEventListener('click', addWebhookRow);
  if (elements.btnTestWebhooks) {
    elements.btnTestWebhooks.addEventListener('click', testWebhooks);
  }
  if (elements.backupProvider) {
    elements.backupProvider.addEventListener('change', (event) => populateBackupCredentials(event.target.value));
  }
  if (elements.btnBackupConnect) {
    elements.btnBackupConnect.addEventListener('click', connectBackupProvider);
  }
  if (elements.btnBackupRefresh) {
    elements.btnBackupRefresh.addEventListener('click', loadBackupProviders);
  }
  if (elements.btnBackupSaveLocal) {
    elements.btnBackupSaveLocal.addEventListener('click', () => {
      if (elements.backupLocalPath.value) {
        window.macWinBridge.openPath(elements.backupLocalPath.value);
      }
    });
  }
  if (elements.debugToggle) {
    elements.debugToggle.addEventListener('change', (event) => {
      window.macWinBridge.setDebugMode(event.target.checked);
    });
  }
  elements.btnBatchAdd.addEventListener('click', addBatchItem);
  elements.batchQueue.addEventListener('click', (event) => {
    const removeButton = event.target.closest('button[data-batch-remove]');
    if (!removeButton) return;
    const index = Number(removeButton.dataset.batchRemove);
    state.batchQueue.splice(index, 1);
    renderBatchQueue();
  });
  elements.btnBatchClear.addEventListener('click', clearBatchQueue);
  elements.btnBatchStart.addEventListener('click', startBatchConversion);
  elements.btnRefreshCommunity.addEventListener('click', loadCommunityMetrics);
  elements.btnSubmitIssue.addEventListener('click', submitIssueReport);
}

async function loadInitialData() {
  await updateBackendHealth();
  await updateResourceSnapshot();
  await loadModelProviders();
  await loadTemplates();
  await loadBackupProviders();
  await loadCommunityMetrics();
  ensureWebhooksInitialized();
}

async function detectAndAutoPreview() {
  if (state.projectPath) {
    await detectProject();
    await previewConversion();
  }
}

function init() {
  initTabs();
  initDirectionButtons();
  initDropzone();
  attachEventListeners();
  ensureWebhooksInitialized();
  loadInitialData();
  detectAndAutoPreview();
  setInterval(updateResourceSnapshot, 10000);
}

document.addEventListener('DOMContentLoaded', init);
window.addEventListener('beforeunload', clearTimers);
