const { contextBridge, ipcRenderer } = require('electron');

const safeInvoke = (channel, payload) => ipcRenderer.invoke(channel, payload);

contextBridge.exposeInMainWorld('macWinBridge', {
  getBackendHealth: () => safeInvoke('backend:health'),
  detectProject: (projectPath, options = {}) =>
    safeInvoke('backend:detectProject', {
      project_path: projectPath,
      direction: options.direction || null
    }),
  listModels: () => safeInvoke('backend:listModels'),
  getResourceSnapshot: () => safeInvoke('backend:resourceSnapshot'),
  startConversion: (payload) => safeInvoke('backend:startConversion', payload),
  pauseConversion: (sessionId) => safeInvoke('backend:pauseConversion', { session_id: sessionId }),
  resumeConversion: (sessionId) => safeInvoke('backend:resumeConversion', { session_id: sessionId }),
  getConversionStatus: (sessionId) => safeInvoke('backend:getConversionStatus', sessionId),
  listTemplates: () => safeInvoke('backend:listTemplates'),
  loadTemplate: (name) => safeInvoke('backend:loadTemplate', name),
  saveTemplate: (payload) => safeInvoke('backend:saveTemplate', payload),
  shareTemplate: (payload) => safeInvoke('backend:shareTemplate', payload),
  deleteTemplate: (name) => safeInvoke('backend:deleteTemplate', name),
  fetchLogs: (limit = 200) => safeInvoke('backend:fetchLogs', limit),
  setDebugMode: (enabled) => safeInvoke('backend:setDebugMode', { enabled }),
  prepareRollback: (sessionId, backupPath = null) => safeInvoke('backend:prepareRollback', { session_id: sessionId, backup_path: backupPath }),
  listManualFixes: (sessionId) => safeInvoke('backend:listManualFixes', sessionId),
  submitManualFix: (sessionId, chunkId, payload) => safeInvoke('backend:submitManualFix', {
    session_id: sessionId,
    chunk_id: chunkId,
    ...payload
  }),
  listBackupProviders: () => safeInvoke('backend:listBackupProviders'),
  startBackupOAuth: (provider, config) => safeInvoke('backend:startBackupOAuth', { provider, config }),
  createBackupCredential: (provider, body) => safeInvoke('backend:createBackupCredential', { provider, body }),
  deleteBackupCredential: (credentialId) => safeInvoke('backend:deleteBackupCredential', credentialId),
  listSessionBackups: (sessionId) => safeInvoke('backend:listSessionBackups', sessionId),
  previewConversion: (payload) => safeInvoke('backend:previewConversion', payload),
  resumeFailedConversion: (payload) => safeInvoke('backend:resumeFailedConversion', payload),
  startBatchConversion: (payload) => safeInvoke('backend:startBatchConversion', payload),
  getCommunityMetrics: () => safeInvoke('backend:getCommunityMetrics'),
  submitIssueReport: (payload) => safeInvoke('backend:submitIssueReport', payload),
  openExternal: (url) => safeInvoke('app:openExternal', url),
  openPath: (targetPath) => safeInvoke('app:openPath', targetPath)
});
