const { app, BrowserWindow, Menu, shell } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');

const DEV_URL = process.env.RADIOTEDU_ADMIN_URL || `http://127.0.0.1:${process.env.FRONTEND_PORT || '5173'}`;
const API_PORT = process.env.API_PORT || '8000';
const MANAGE_BACKEND = process.env.RADIOTEDU_MANAGE_BACKEND !== '0';
let backendProcess = null;

function startBackend() {
  if (!MANAGE_BACKEND || backendProcess) {
    return;
  }
  const python = process.env.RADIOTEDU_PYTHON || process.env.PYTHON || 'python';
  backendProcess = spawn(python, ['-m', 'backend.app'], {
    cwd: path.join(__dirname, '..'),
    env: {
      ...process.env,
      API_PORT,
      PYTHONUNBUFFERED: '1',
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  backendProcess.stdout.on('data', (chunk) => {
    console.log(`[backend] ${chunk.toString().trim()}`);
  });
  backendProcess.stderr.on('data', (chunk) => {
    console.error(`[backend] ${chunk.toString().trim()}`);
  });
  backendProcess.on('exit', (code, signal) => {
    console.log(`[backend] exited code=${code} signal=${signal}`);
    backendProcess = null;
  });
}

function killBackend() {
  if (!backendProcess) {
    return;
  }
  const child = backendProcess;
  backendProcess = null;
  if (!child.killed) {
    child.kill();
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 980,
    minHeight: 720,
    title: 'RadioTEDU Admin Panel',
    backgroundColor: '#f5f7fb',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  Menu.setApplicationMenu(null);
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  if (app.isPackaged) {
    win.loadFile(path.join(__dirname, '..', 'dist', 'frontend', 'index.html'));
  } else {
    win.loadURL(DEV_URL);
  }
}

app.whenReady().then(() => {
  app.setName('RadioTEDU Admin Panel');
  startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  killBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killBackend();
});
