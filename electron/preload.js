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
  fetchLogs: (limit = 200) => safeInvoke('backend:fetchLogs', limit),
  setDebugMode: (enabled) => safeInvoke('backend:setDebugMode', { enabled }),
  prepareRollback: (sessionId, backupPath = null) => safeInvoke('backend:prepareRollback', { session_id: sessionId, backup_path: backupPath })
});
