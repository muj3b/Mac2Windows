const state = {
  direction: 'mac-to-win',
  projectPath: null,
  detection: null,
  providerMap: new Map(),
  resourceTimer: null,
  healthTimer: null,
  sessionId: null,
  progressTimer: null,
  targetPath: null,
  templates: []
};

const STAGE_DISPLAY_ORDER = [
  'RESOURCES',
  'DEPENDENCIES',
  'PROJECT_SETUP',
  'CODE',
  'TESTS',
  'QUALITY'
];

const elements = {
  directionButtons: document.querySelectorAll('.direction-button'),
  dropzone: document.getElementById('dropzone'),
  folderInput: document.getElementById('folder-input'),
  selectedPath: document.getElementById('selected-path'),
  rescanButton: document.getElementById('btn-rescan'),
  detectionResults: document.getElementById('detection-results'),
  detectionSummary: document.getElementById('detection-summary'),
  modelProviderSelect: document.getElementById('model-provider'),
  targetFrameworkSelect: document.getElementById('target-framework'),
  languageOutputSelect: document.getElementById('language-output'),
  modelIdentifierInput: document.getElementById('model-identifier'),
  apiKeyInput: document.getElementById('api-key'),
  startButton: document.getElementById('btn-start'),
  backendStatus: document.getElementById('backend-status'),
  resourceStatus: document.getElementById('resource-status'),
  progressLog: document.getElementById('progress-log'),
  progressSummary: document.getElementById('progress-summary'),
  progressTime: document.getElementById('progress-time'),
  analysisReport: document.getElementById('analysis-report'),
  progressStats: document.getElementById('progress-stats'),
  pauseButton: document.getElementById('btn-pause'),
  resumeButton: document.getElementById('btn-resume'),
  codeStyle: document.getElementById('code-style'),
  commentStyle: document.getElementById('comment-style'),
  namingStyle: document.getElementById('naming-style'),
  errorStyle: document.getElementById('error-style'),
  maxCpu: document.getElementById('max-cpu'),
  maxRam: document.getElementById('max-ram'),
  threads: document.getElementById('threads'),
  apiRate: document.getElementById('api-rate'),
  aiTemp: document.getElementById('ai-temp'),
  aiStrategy: document.getElementById('ai-strategy'),
  aiRetries: document.getElementById('ai-retries'),
  templateName: document.getElementById('template-name'),
  saveTemplateButton: document.getElementById('btn-save-template'),
  loadTemplateButton: document.getElementById('btn-load-template'),
  webhooksInput: document.getElementById('webhooks'),
  debugToggle: document.getElementById('debug-toggle'),
  viewLogsButton: document.getElementById('btn-view-logs'),
  logsPanel: document.getElementById('logs-panel'),
  reportLinks: document.getElementById('report-links')
};

const formatPercent = (value) => `${Math.round(value * 100)}%`;

const formatOverallPercent = (value) => `${Math.round((value || 0) * 100)}%`;

const formatDuration = (seconds) => {
  if (!seconds && seconds !== 0) return '–';
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
};

const setDirection = (direction) => {
  state.direction = direction;
  elements.directionButtons.forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.direction === direction);
  });
  hydrateTargetFrameworks();
};

const hydrateTargetFrameworks = () => {
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

  elements.targetFrameworkSelect.innerHTML = '';
  frameworks.forEach((framework) => {
    const option = document.createElement('option');
    option.value = framework.value;
    option.textContent = framework.label;
    elements.targetFrameworkSelect.appendChild(option);
  });
};

const updateBackendStatus = async () => {
  const status = await window.macWinBridge.getBackendHealth();
  if (status.status === 'ok') {
    elements.backendStatus.textContent = `Backend: ${status.status}`;
    elements.backendStatus.className = 'status-pill status-pill--ok';
  } else {
    elements.backendStatus.textContent = `Backend: ${status.status ?? 'down'}`;
    elements.backendStatus.className = 'status-pill status-pill--error';
  }
};

const updateResourceStatus = async () => {
  const snapshot = await window.macWinBridge.getResourceSnapshot();
  if (snapshot.error) {
    elements.resourceStatus.textContent = 'Resources: unavailable';
    elements.resourceStatus.className = 'status-pill status-pill--warn';
    return;
  }

  const cpu = snapshot.cpu?.percent != null ? `${snapshot.cpu.percent}% CPU` : 'CPU n/a';
  const memory =
    snapshot.memory?.percent != null ? `${snapshot.memory.percent}% RAM` : 'RAM n/a';
  const disk =
    snapshot.disk?.free_gb != null
      ? `${snapshot.disk.free_gb.toFixed(1)} GB free`
      : 'Disk n/a';

  elements.resourceStatus.textContent = `Resources: ${cpu}, ${memory}, ${disk}`;
  elements.resourceStatus.className = 'status-pill status-pill--ok';
};

const renderDetectionResults = (result) => {
  if (!result || result.error) {
    elements.detectionResults.innerHTML =
      '<div class="placeholder">Detection failed. Check logs for details.</div>';
    elements.detectionSummary.textContent = 'Error';
    elements.detectionSummary.className = 'summary-pill warn';
    return;
  }

  elements.detectionSummary.textContent = 'Scan Complete';
  elements.detectionSummary.className = 'summary-pill success';

  const languages = result.languages?.map((lang) => {
    const percentage =
      result.summary?.total_files > 0
        ? Math.round((lang.files / result.summary.total_files) * 100)
        : 0;
    return `<li>${lang.name} • ${lang.files} files • ${lang.lines} lines • ${percentage}%</li>`;
  });

  const frameworks = [
    ...(result.frameworks?.mac ?? []).map((item) => `${item.name} (${item.version ?? '?'})`),
    ...(result.frameworks?.windows ?? []).map(
      (item) => `${item.name} (${item.version ?? '?'})`
    )
  ];

  const dependencies = result.dependencies?.map((dep) => {
    const version = dep.version ? `@${dep.version}` : '';
    return `<li>${dep.name}${version} (${dep.manager})</li>`;
  });

  const infoCards = [
    {
      title: 'Languages',
      content: languages?.length
        ? `<ul>${languages.join('')}</ul>`
        : '<div class="muted">None detected</div>'
    },
    {
      title: 'Frameworks',
      content: frameworks.length
        ? `<ul>${frameworks.map((item) => `<li>${item}</li>`).join('')}</ul>`
        : '<div class="muted">None detected</div>'
    },
    {
      title: 'Dependencies',
      content: dependencies?.length
        ? `<ul>${dependencies.join('')}</ul>`
        : '<div class="muted">No external dependencies</div>'
    },
    {
      title: 'Project Size',
      content: `
        <div class="stat">${result.summary?.total_files ?? 0} files</div>
        <div class="muted">${result.summary?.total_lines ?? 0} lines</div>
        <div class="muted">Estimated time ${result.summary?.estimated_minutes ?? '–'} min</div>
      `
    }
  ];

  elements.detectionResults.innerHTML = `
    <div class="result-grid">
      ${infoCards
        .map(
          (card) => `
            <div class="result-card">
              <h3>${card.title}</h3>
              ${card.content}
            </div>
          `
        )
        .join('')}
    </div>
  `;
};

const renderAnalysisReport = (result) => {
  if (!result || result.error) {
    elements.analysisReport.innerHTML =
      '<div class="placeholder">No analysis available.</div>';
    return;
  }
  const metrics = result.analysis;
  elements.analysisReport.innerHTML = `
    <div class="analysis-metrics">
      <div class="analysis-metric">
        <h4>Auto-convertible</h4>
        <span>${formatPercent(metrics.auto_convertible)}</span>
      </div>
      <div class="analysis-metric">
        <h4>Manual Review</h4>
        <span>${formatPercent(metrics.manual_review)}</span>
      </div>
      <div class="analysis-metric">
        <h4>Unsupported</h4>
        <span>${formatPercent(metrics.unsupported)}</span>
      </div>
      <div class="analysis-metric">
        <h4>Risk Level</h4>
        <span>${metrics.risk_level}</span>
      </div>
      <div class="analysis-metric">
        <h4>Est. Duration</h4>
        <span>${metrics.time_estimate_minutes} min</span>
      </div>
      <div class="analysis-metric">
        <h4>Tokens / Cost</h4>
        <span>${metrics.estimated_tokens} tokens • $${metrics.estimated_cost_usd}</span>
      </div>
    </div>
  `;
};

const resetProgressLog = () => {
  elements.progressLog.innerHTML =
    '<div class="placeholder">Conversion progress will stream here with per-file status updates.</div>';
  elements.progressSummary.textContent = 'Idle';
  elements.progressTime.textContent = '–';
  elements.progressStats.innerHTML = '';
};

const populateModelProviders = (payload) => {
  elements.modelProviderSelect.innerHTML = '';
  state.providerMap.clear();
  if (!payload?.providers?.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No providers available';
    elements.modelProviderSelect.appendChild(option);
    return;
  }
  payload.providers.forEach((provider) => {
    state.providerMap.set(provider.id, provider);
    const option = document.createElement('option');
    option.value = provider.id;
    option.textContent = provider.label;
    elements.modelProviderSelect.appendChild(option);
  });
  elements.modelProviderSelect.dispatchEvent(new Event('change'));
};

const triggerDetection = async () => {
  if (!state.projectPath) {
    return;
  }
  elements.detectionSummary.textContent = 'Scanning…';
  elements.detectionSummary.className = 'summary-pill running';
  elements.progressSummary.textContent = 'Analyzing project…';
  elements.progressTime.textContent = new Date().toLocaleTimeString();

  const response = await window.macWinBridge.detectProject(state.projectPath, {
    direction: state.direction
  });
  if (response.error) {
    renderDetectionResults(response);
    renderAnalysisReport(response);
    return;
  }

  state.detection = response;
  renderDetectionResults(response);
  renderAnalysisReport(response);
  hydrateSuggestedTargets(response);
  elements.startButton.disabled = false;
};

const hydrateSuggestedTargets = (result) => {
  if (!result?.suggested_targets?.length) {
    hydrateTargetFrameworks();
    return;
  }
  elements.targetFrameworkSelect.innerHTML = '';
  result.suggested_targets.forEach((target) => {
    const option = document.createElement('option');
    option.value = target.id;
    option.textContent = target.label;
    elements.targetFrameworkSelect.appendChild(option);
  });
};

const initDragDrop = () => {
  elements.dropzone.addEventListener('click', () => elements.folderInput.click());

  elements.folderInput.addEventListener('change', (event) => {
    const folder = event.target?.files?.[0];
    if (folder?.path) {
      state.projectPath = folder.path;
      elements.selectedPath.textContent = folder.path;
      elements.rescanButton.disabled = false;
      triggerDetection();
    }
  });

  elements.dropzone.addEventListener('dragover', (event) => {
    event.preventDefault();
    event.stopPropagation();
    elements.dropzone.classList.add('dragover');
  });

  elements.dropzone.addEventListener('dragleave', (event) => {
    event.preventDefault();
    event.stopPropagation();
    elements.dropzone.classList.remove('dragover');
  });

  elements.dropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    event.stopPropagation();
    elements.dropzone.classList.remove('dragover');

    const item = event.dataTransfer?.files?.[0];
    if (item?.path) {
      state.projectPath = item.path;
      elements.selectedPath.textContent = item.path;
      elements.rescanButton.disabled = false;
      resetConversionState();
      triggerDetection();
    }
  });
};

const initDirectionButtons = () => {
  elements.directionButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const direction = btn.dataset.direction;
      setDirection(direction);
      if (state.projectPath) {
        triggerDetection();
      }
    });
  });
  setDirection(state.direction);
};

const initRescanButton = () => {
  elements.rescanButton.addEventListener('click', () => {
    triggerDetection();
  });
};

const initModelProviderSelect = () => {
  elements.modelProviderSelect.addEventListener('change', () => {
    const provider = state.providerMap.get(elements.modelProviderSelect.value);
    if (provider?.default_identifier) {
      elements.modelIdentifierInput.value = provider.default_identifier;
    }
    if (provider?.requires_api_key) {
      elements.apiKeyInput.placeholder = 'API key required';
    } else {
      elements.apiKeyInput.placeholder = 'API key optional';
    }
  });
};

const boot = async () => {
  initDirectionButtons();
  initDragDrop();
  initRescanButton();
  initModelProviderSelect();
  hydrateTargetFrameworks();
  resetProgressLog();

  elements.startButton.addEventListener('click', onStartConversion);
  elements.pauseButton.addEventListener('click', onPauseConversion);
  elements.resumeButton.addEventListener('click', onResumeConversion);
  elements.saveTemplateButton.addEventListener('click', saveTemplate);
  elements.loadTemplateButton.addEventListener('click', loadTemplate);
  elements.viewLogsButton.addEventListener('click', viewLogs);
  elements.debugToggle.addEventListener('change', onToggleDebug);

  await updateBackendStatus();
  await updateResourceStatus();

  const providerResponse = await window.macWinBridge.listModels();
  populateModelProviders(providerResponse);
  await refreshTemplates();

  state.healthTimer = setInterval(updateBackendStatus, 15000);
  state.resourceTimer = setInterval(updateResourceStatus, 10000);
};

const computeTargetPath = () => {
  if (!state.projectPath) return null;
  const separator = state.projectPath.includes('\\') ? '\\' : '/';
  const idx = state.projectPath.lastIndexOf(separator);
  const baseDir = idx > 0 ? state.projectPath.slice(0, idx) : state.projectPath;
  const projectName = idx > 0 ? state.projectPath.slice(idx + 1) : state.projectPath;
  const suffix = state.direction === 'mac-to-win' ? 'windows' : 'mac';
  const targetName = `${projectName}.${suffix}.converted`;
  const targetPath = idx > 0 ? `${baseDir}${separator}${targetName}` : `${targetName}`;
  state.targetPath = targetPath;
  return targetPath;
};

const collectConversionSettings = () => ({
  code_style: elements.codeStyle.value,
  comments: elements.commentStyle.value,
  naming: elements.namingStyle.value,
  error_handling: elements.errorStyle.value
});

const collectPerformanceSettings = () => ({
  max_cpu: Number.parseInt(elements.maxCpu.value, 10) || 80,
  max_ram_gb: Number.parseInt(elements.maxRam.value, 10) || 16,
  threads: Number.parseInt(elements.threads.value, 10) || 4,
  api_rate_limit: Number.parseInt(elements.apiRate.value, 10) || 30
});

const collectAISettings = () => ({
  temperature: Number.parseFloat(elements.aiTemp.value) || 0.2,
  strategy: elements.aiStrategy.value,
  retries: Number.parseInt(elements.aiRetries.value, 10) || 3
});

const collectWebhooks = () => {
  const raw = elements.webhooksInput.value.trim();
  if (!raw) return [];
  return raw.split(',').map((item) => item.trim()).filter(Boolean);
};

const updateReportLinks = (summary) => {
  elements.reportLinks.innerHTML = '';
  if (summary.conversion_report) {
    const link = document.createElement('div');
    link.textContent = `Conversion report: ${summary.conversion_report}`;
    elements.reportLinks.appendChild(link);
  }
  if (summary.quality_report?.ai_review_notes?.length) {
    summary.quality_report.ai_review_notes.forEach((note) => {
      const item = document.createElement('div');
      item.textContent = `AI review: ${note}`;
      elements.reportLinks.appendChild(item);
    });
  }
  if (summary.diff_links?.length) {
    summary.diff_links.forEach((href) => {
      const item = document.createElement('div');
      item.innerHTML = `<a href="${href}" target="_blank">Diff: ${href.split('/').pop()}</a>`;
      elements.reportLinks.appendChild(item);
    });
  }
};

const resetConversionState = () => {
  stopStatusPolling();
  state.sessionId = null;
  state.targetPath = null;
  elements.startButton.disabled = false;
  elements.pauseButton.disabled = true;
  elements.resumeButton.disabled = true;
  resetProgressLog();
  elements.reportLinks.innerHTML = '';
  elements.logsPanel.textContent = '';
};

const onStartConversion = async () => {
  if (!state.projectPath) {
    alert('Select a project before starting conversion.');
    return;
  }
  const providerId = elements.modelProviderSelect.value;
  if (!providerId) {
    alert('Pick an AI provider to continue.');
    return;
  }
  const modelIdentifier = elements.modelIdentifierInput.value.trim();
  if (!modelIdentifier) {
    alert('Specify a model identifier or path.');
    return;
  }
  const targetPath = computeTargetPath();
  const conversionSettings = collectConversionSettings();
  const performanceSettings = collectPerformanceSettings();
  const aiSettings = collectAISettings();
  const webhooks = collectWebhooks();
  const payload = {
    project_path: state.projectPath,
    target_path: targetPath,
    direction: state.direction,
    provider_id: providerId,
    model_identifier: modelIdentifier,
    api_key: elements.apiKeyInput.value.trim() || null,
    conversion: conversionSettings,
    performance: performanceSettings,
    ai: aiSettings,
    webhooks
  };

  elements.startButton.disabled = true;
  elements.pauseButton.disabled = true;
  elements.resumeButton.disabled = true;
  elements.progressSummary.textContent = 'Preparing…';
  elements.progressTime.textContent = '–';

  const response = await window.macWinBridge.startConversion(payload);
  if (response.error || !response.session_id) {
    elements.progressSummary.textContent = 'Failed to start';
    elements.progressLog.innerHTML = `<div class="placeholder">${response.message || 'Backend rejected conversion start.'}</div>`;
    elements.startButton.disabled = false;
    return;
  }

  state.sessionId = response.session_id;
  elements.pauseButton.disabled = false;
  elements.resumeButton.disabled = true;
  elements.progressLog.innerHTML = '<div class="placeholder">Conversion queued…</div>';
  renderProgress(response.summary);
  startStatusPolling();
};

const onPauseConversion = async () => {
  if (!state.sessionId) return;
  const response = await window.macWinBridge.pauseConversion(state.sessionId);
  if (response.error) {
    alert(response.message || 'Pause failed');
    return;
  }
  renderProgress(response.summary);
};

const onResumeConversion = async () => {
  if (!state.sessionId) return;
  const response = await window.macWinBridge.resumeConversion(state.sessionId);
  if (response.error) {
    alert(response.message || 'Resume failed');
    return;
  }
  renderProgress(response.summary);
};

const startStatusPolling = () => {
  stopStatusPolling();
  const poll = async () => {
    if (!state.sessionId) return;
    const response = await window.macWinBridge.getConversionStatus(state.sessionId);
    if (response?.error) {
      elements.progressSummary.textContent = 'Status unavailable';
      elements.progressLog.innerHTML = `<div class="placeholder">${response.message}</div>`;
      return;
    }
    renderProgress(response.summary);
  };
  poll();
  state.progressTimer = setInterval(poll, 5000);
};

const stopStatusPolling = () => {
  if (state.progressTimer) {
    clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
};

const renderProgress = (summary) => {
  if (!summary) return;
  const overallPct = formatOverallPercent(summary.overall_percentage);
  const total = summary.total_files || 0;
  const converted = summary.converted_files || 0;
  elements.progressSummary.textContent = `${overallPct} (${converted}/${total} files)`;

  const elapsed = formatDuration(summary.elapsed_seconds);
  const remaining = summary.estimated_seconds_remaining != null
    ? formatDuration(summary.estimated_seconds_remaining)
    : 'estimating…';
  elements.progressTime.textContent = `Elapsed ${elapsed} • ETA ${remaining}`;

  const stageEntries = STAGE_DISPLAY_ORDER.map((stageName) => {
    const data = summary.stage_progress?.[stageName];
    if (!data) return '';
    const completed = data.completed_units || 0;
    const units = data.total_units || 0;
    const stagePct = Math.round((data.percentage || 0) * 100);
    let statusClass = 'pending';
    if (data.status === 'running' || data.status === 'paused') {
      statusClass = 'processing';
    } else if (data.status === 'completed' || data.status === 'skipped') {
      statusClass = 'done';
    }
    return `
      <div class="progress-entry ${statusClass}">
        <div>
          <div class="status">${stageName.replace('_', ' ')}</div>
          <div class="muted">${completed}/${units} • ${stagePct}%</div>
        </div>
        <span class="muted">${data.status}</span>
      </div>
    `;
  }).filter(Boolean).join('');

  const current = summary.current_chunk;
  const currentBlock = current
    ? `<div class="progress-entry processing">
        <div>
          <div class="status">Current</div>
          <div class="muted">${current.file_path.split(/[\\/]/).slice(-2).join('/')}</div>
        </div>
        <span class="muted">${current.stage}</span>
      </div>`
    : '';

  elements.progressLog.innerHTML = `<div class="progress-log-list">${currentBlock}${stageEntries}</div>`;

  const stats = [
    `Tokens: ${summary.tokens_used || 0}`,
    `Cost: $${(summary.cost_usd || 0).toFixed(4)}`,
    `Session: ${state.sessionId || 'n/a'}`,
    state.targetPath ? `Target: ${state.targetPath}` : null,
    summary.conversion_report ? `Report: ${summary.conversion_report}` : null
  ].filter(Boolean);
  elements.progressStats.innerHTML = stats
    .map((item) => `<span class="stat-item">${item}</span>`)
    .join('');

  if (summary.quality_report) {
    const issues = summary.quality_report.issues || [];
    const qualityList = issues
      .map((issue) => `<div class="stat-item">[${issue.severity}] ${issue.category}: ${issue.message}</div>`)
      .join('');
    if (qualityList) {
      elements.progressStats.innerHTML += qualityList;
    }
  }

  updateReportLinks(summary);

  if (summary.paused) {
    elements.pauseButton.disabled = true;
    elements.resumeButton.disabled = false;
  } else {
    elements.pauseButton.disabled = false;
    elements.resumeButton.disabled = true;
  }

  if (summary.overall_percentage >= 1) {
    elements.pauseButton.disabled = true;
    elements.resumeButton.disabled = true;
    stopStatusPolling();
  }
};

const refreshTemplates = async () => {
  const response = await window.macWinBridge.listTemplates();
  if (response?.templates) {
    state.templates = response.templates;
  }
};

const saveTemplate = async () => {
  const name = elements.templateName.value.trim();
  if (!name) {
    alert('Enter a template name.');
    return;
  }
  const payload = {
    name,
    conversion: collectConversionSettings(),
    performance: collectPerformanceSettings(),
    ai: collectAISettings()
  };
  const response = await window.macWinBridge.saveTemplate(payload);
  if (response.error) {
    alert(response.message || 'Failed to save template');
    return;
  }
  await refreshTemplates();
  alert('Template saved');
};

const loadTemplate = async () => {
  let name = elements.templateName.value.trim();
  if (!name && state.templates.length) {
    name = state.templates[0];
  }
  if (!name) {
    alert('No template name provided.');
    return;
  }
  const response = await window.macWinBridge.loadTemplate(name);
  if (response.error || !response.template) {
    alert(response.message || 'Template not found');
    return;
  }
  const template = response.template;
  applyTemplate(template);
};

const applyTemplate = (template) => {
  const conversion = template.conversion || {};
  const performance = template.performance || {};
  const ai = template.ai || {};
  if (conversion.code_style) elements.codeStyle.value = conversion.code_style;
  if (conversion.comments) elements.commentStyle.value = conversion.comments;
  if (conversion.naming) elements.namingStyle.value = conversion.naming;
  if (conversion.error_handling) elements.errorStyle.value = conversion.error_handling;
  if (performance.max_cpu) elements.maxCpu.value = performance.max_cpu;
  if (performance.max_ram_gb) elements.maxRam.value = performance.max_ram_gb;
  if (performance.threads) elements.threads.value = performance.threads;
  if (performance.api_rate_limit) elements.apiRate.value = performance.api_rate_limit;
  if (ai.temperature != null) elements.aiTemp.value = ai.temperature;
  if (ai.strategy) elements.aiStrategy.value = ai.strategy;
  if (ai.retries) elements.aiRetries.value = ai.retries;
};

const viewLogs = async () => {
  const response = await window.macWinBridge.fetchLogs(200);
  if (response.error) {
    elements.logsPanel.textContent = response.message || 'Failed to load logs';
    return;
  }
  const entries = response.entries || [];
  elements.logsPanel.innerHTML = entries
    .map((entry) => `<div>[${entry.timestamp}] ${entry.category}: ${entry.message}</div>`)
    .join('');
};

const onToggleDebug = async (event) => {
  const response = await window.macWinBridge.setDebugMode(event.target.checked);
  if (response.error) {
    alert(response.message || 'Unable to update debug mode');
  }
};

document.addEventListener('DOMContentLoaded', () => {
  boot().catch((error) => {
    console.error('Failed to start renderer', error);
  });
});
