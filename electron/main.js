const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const axios = require('axios');

const BACKEND_PORT = process.env.BACKEND_PORT || 6110;
const BACKEND_HOST = process.env.BACKEND_HOST || '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let mainWindow;
let pythonProcess;

const isDev = process.env.NODE_ENV === 'development';

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    show: false
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  const indexPath = path.join(__dirname, 'src', 'renderer', 'index.html');
  mainWindow.loadFile(indexPath);
};

const resolvePythonExecutable = () => {
  if (process.env.PYTHON_EXECUTABLE) {
    return process.env.PYTHON_EXECUTABLE;
  }
  if (process.platform === 'win32') {
    return 'python';
  }
  return 'python3';
};

const startPythonBackend = () => {
  if (pythonProcess) {
    return;
  }

  const pythonExec = resolvePythonExecutable();
  pythonProcess = spawn(pythonExec, ['-m', 'backend.main', `--port=${BACKEND_PORT}`], {
    cwd: path.join(__dirname, '..'),
    env: {
      ...process.env,
      BACKEND_PORT: BACKEND_PORT
    },
    stdio: isDev ? 'inherit' : 'ignore'
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start backend:', error);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.info(`Backend exited with code ${code} signal ${signal}`);
    pythonProcess = null;
    if (!app.isQuitting && !isDev) {
      setTimeout(startPythonBackend, 2000);
    }
  });
};

const stopPythonBackend = () => {
  if (!pythonProcess) {
    return;
  }
  pythonProcess.kill();
  pythonProcess = null;
};

const setupIpcHandlers = () => {
  ipcMain.handle('backend:health', async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/health`);
      return response.data;
    } catch (error) {
      return { status: 'down', detail: error.message };
    }
  });

  ipcMain.handle('backend:detectProject', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/detect`, payload, {
        timeout: 120000
      });
      return response.data;
    } catch (error) {
      const message =
        error.response?.data?.detail ||
        error.message ||
        'Unexpected error during detection';
      return {
        error: true,
        message
      };
    }
  });

  ipcMain.handle('backend:listModels', async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/ai/models`);
      return response.data;
    } catch (error) {
      return { error: true, message: error.message };
    }
  });

  ipcMain.handle('backend:resourceSnapshot', async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/resources`);
      return response.data;
    } catch (error) {
      return { cpu: null, memory: null, disk: null, network: null, error: error.message };
    }
  });

  ipcMain.handle('backend:startConversion', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/conversion/start`, payload, {
        timeout: 300000
      });
      return response.data;
    } catch (error) {
      return {
        error: true,
        message:
          error.response?.data?.detail || error.message || 'Unable to start conversion session'
      };
    }
  });

  ipcMain.handle('backend:pauseConversion', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/conversion/pause`, payload);
      return response.data;
    } catch (error) {
      return {
        error: true,
        message: error.response?.data?.detail || error.message || 'Pause failed'
      };
    }
  });

  ipcMain.handle('backend:resumeConversion', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/conversion/resume`, payload);
      return response.data;
    } catch (error) {
      return {
        error: true,
        message: error.response?.data?.detail || error.message || 'Resume failed'
      };
    }
  });

  ipcMain.handle('backend:getConversionStatus', async (_event, sessionId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/conversion/status/${sessionId}`);
      return response.data;
    } catch (error) {
      return {
        error: true,
        message: error.response?.data?.detail || error.message || 'Status unavailable'
      };
    }
  });

  ipcMain.handle('backend:listManualFixes', async (_event, sessionId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/conversion/manual/${sessionId}`);
      return response.data;
    } catch (error) {
      return {
        error: true,
        message: error.response?.data?.detail || error.message || 'Manual fixes unavailable'
      };
    }
  });

  ipcMain.handle('backend:submitManualFix', async (_event, payload) => {
    try {
      const { session_id: sessionId, chunk_id: chunkId, code, note, submitted_by: submittedBy } = payload;
      const response = await axios.post(`${BACKEND_URL}/conversion/manual/${sessionId}/${chunkId}`, {
        code,
        note,
        submitted_by: submittedBy
      });
      return response.data;
    } catch (error) {
      return {
        error: true,
        message: error.response?.data?.detail || error.message || 'Manual fix submission failed'
      };
    }
  });

  ipcMain.handle('backend:listTemplates', async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/settings/templates`);
      return response.data;
    } catch (error) {
      return { error: true, message: error.message };
    }
  });

  ipcMain.handle('backend:loadTemplate', async (_event, name) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/settings/templates`, {
        params: { name }
      });
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('backend:saveTemplate', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/settings/templates`, payload);
      return response.data;
    } catch (error) {
      return { error: true, message: error.message };
    }
  });

  ipcMain.handle('backend:listBackupProviders', async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/backups/providers`);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('backend:startBackupOAuth', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/backups/providers/${payload.provider}/oauth/start`, payload.config);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('backend:createBackupCredential', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/backups/providers/${payload.provider}/credentials`, payload.body);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('backend:deleteBackupCredential', async (_event, credentialId) => {
    try {
      const response = await axios.delete(`${BACKEND_URL}/backups/credentials/${credentialId}`);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('backend:listSessionBackups', async (_event, sessionId) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/backups/sessions/${sessionId}`);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });

  ipcMain.handle('app:openExternal', async (_event, url) => {
    await shell.openExternal(url);
    return { success: true };
  });

  ipcMain.handle('app:openPath', async (_event, targetPath) => {
    if (!targetPath) {
      return { error: true, message: 'Path is required' };
    }
    const result = await shell.openPath(targetPath);
    if (result) {
      return { error: true, message: result };
    }
    return { success: true };
  });

  ipcMain.handle('backend:fetchLogs', async (_event, limit = 200) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/logs/recent`, { params: { limit } });
      return response.data;
    } catch (error) {
      return { error: true, message: error.message };
    }
  });

  ipcMain.handle('backend:setDebugMode', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/settings/debug`, payload);
      return response.data;
    } catch (error) {
      return { error: true, message: error.message };
    }
  });

  ipcMain.handle('backend:prepareRollback', async (_event, payload) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/conversion/rollback`, payload);
      return response.data;
    } catch (error) {
      return { error: true, message: error.response?.data?.detail || error.message };
    }
  });
};

app.whenReady().then(() => {
  setupIpcHandlers();
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('before-quit', () => {
  app.isQuitting = true;
  stopPythonBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
