const { app, BrowserWindow, Menu, shell } = require('electron');
const { spawn } = require('node:child_process');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

const DEV_URL = process.env.RADIOTEDU_ADMIN_URL || `http://127.0.0.1:${process.env.FRONTEND_PORT || '5173'}`;
const API_PORT = process.env.API_PORT || '8000';
const FRONTEND_PORT = process.env.FRONTEND_PORT || '5173';
const MANAGE_BACKEND = process.env.RADIOTEDU_MANAGE_BACKEND !== '0';
const MANAGE_FRONTEND = process.env.RADIOTEDU_MANAGE_FRONTEND !== '0' && !process.env.RADIOTEDU_ADMIN_URL;
let backendProcess = null;
let frontendProcess = null;
let mainWindow = null;
let backendLastError = '';

function repoRoot() {
  return path.join(__dirname, '..');
}

function startBackend() {
  if (!MANAGE_BACKEND || backendProcess) {
    return;
  }
  const python = process.env.RADIOTEDU_PYTHON || process.env.PYTHON || 'python';
  backendProcess = spawn(python, ['-m', 'backend.app'], {
    cwd: repoRoot(),
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
    backendLastError = chunk.toString().trim();
    console.error(`[backend] ${backendLastError}`);
  });
  backendProcess.on('exit', (code, signal) => {
    console.log(`[backend] exited code=${code} signal=${signal}`);
    backendProcess = null;
    if (code && mainWindow) {
      loadSetupScreen(mainWindow, `Backend startup failed with code ${code}.`, backendLastError);
    }
  });
}

function startFrontend() {
  if (app.isPackaged || !MANAGE_FRONTEND || frontendProcess) {
    return;
  }
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  frontendProcess = spawn(npmCommand, ['run', 'dev', '--', '--host', '127.0.0.1', '--port', FRONTEND_PORT], {
    cwd: repoRoot(),
    env: {
      ...process.env,
      FRONTEND_PORT,
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  frontendProcess.stdout.on('data', (chunk) => {
    console.log(`[frontend] ${chunk.toString().trim()}`);
  });
  frontendProcess.stderr.on('data', (chunk) => {
    console.error(`[frontend] ${chunk.toString().trim()}`);
  });
  frontendProcess.on('exit', (code, signal) => {
    console.log(`[frontend] exited code=${code} signal=${signal}`);
    frontendProcess = null;
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

function killFrontend() {
  if (!frontendProcess) {
    return;
  }
  const child = frontendProcess;
  frontendProcess = null;
  if (!child.killed) {
    child.kill();
  }
}

function waitForUrl(url, attempts = 60, delayMs = 250) {
  return new Promise((resolve, reject) => {
    let remaining = attempts;
    const probe = () => {
      const client = url.startsWith('https:') ? https : http;
      const request = client.get(url, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode < 500) {
          resolve();
          return;
        }
        retry();
      });
      request.setTimeout(1000, () => {
        request.destroy(new Error('timeout'));
      });
      request.on('error', retry);
    };
    const retry = () => {
      remaining -= 1;
      if (remaining <= 0) {
        reject(new Error(`Timed out waiting for ${url}`));
        return;
      }
      setTimeout(probe, delayMs);
    };
    probe();
  });
}

function htmlEscape(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function loadSetupScreen(win, title, detail) {
  const safeTitle = htmlEscape(title || 'RadioTEDU local setup needs attention.');
  const safeDetail = htmlEscape(detail || 'Check the local terminal logs, then restart the admin app.');
  const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>RadioTEDU Admin Setup</title>
    <style>
      body { margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; background: #f5f7fb; color: #111827; }
      main { min-height: 100vh; display: grid; place-items: center; padding: 40px; box-sizing: border-box; }
      section { width: min(720px, 100%); border: 1px solid #d9e0ea; background: #ffffff; border-radius: 8px; padding: 28px; box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08); }
      .brand { font-size: 13px; letter-spacing: 0.18em; text-transform: uppercase; color: #2563eb; font-weight: 800; }
      h1 { margin: 12px 0 10px; font-size: 30px; line-height: 1.1; }
      p { margin: 0; color: #475569; line-height: 1.55; }
      code { display: block; margin-top: 18px; padding: 14px; border-radius: 6px; background: #eef2f7; color: #334155; white-space: pre-wrap; }
    </style>
  </head>
  <body>
    <main>
      <section>
        <div class="brand">RadioTEDU Admin</div>
        <h1>${safeTitle}</h1>
        <p>The broadcast computer app is local-only. Fix the item below, then reopen the admin panel.</p>
        <code>${safeDetail}</code>
      </section>
    </main>
  </body>
</html>`;
  win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
}

function loadAdminWindow(win) {
  win.webContents.on('did-fail-load', (_event, _code, description, validatedURL) => {
    loadSetupScreen(win, 'Admin frontend could not load.', `${description || 'Load failed'}\n${validatedURL || DEV_URL}`);
  });

  if (app.isPackaged) {
    win.loadFile(path.join(__dirname, '..', 'dist', 'frontend', 'index.html')).catch((error) => {
      loadSetupScreen(win, 'Packaged admin UI is missing.', error.message);
    });
    return;
  }

  waitForUrl(DEV_URL)
    .then(() => win.loadURL(DEV_URL))
    .catch((error) => {
      loadSetupScreen(win, 'Admin frontend dev server did not start.', error.message);
    });
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
  mainWindow = win;

  Menu.setApplicationMenu(null);
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
      return { action: 'allow' };
    }
    shell.openExternal(url);
    return { action: 'deny' };
  });

  loadAdminWindow(win);
}

app.whenReady().then(() => {
  app.setName('RadioTEDU Admin Panel');
  startBackend();
  startFrontend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  killBackend();
  killFrontend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killBackend();
  killFrontend();
});
