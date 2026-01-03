const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

function parseMode(argv) {
  const raw = (argv || []).find(a => a.startsWith('--mode='));
  const value = raw ? raw.split('=')[1] : null;
  const mode = (value || 'desktop').toLowerCase();
  if (mode === 'desktop' || mode === 'browser' || mode === 'server') return mode;
  return 'desktop';
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = http.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function waitForHealth(url, timeoutMs = 20000) {
  const started = Date.now();
  return new Promise((resolve) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          resolve(true);
          return;
        }
        if (Date.now() - started > timeoutMs) {
          resolve(false);
          return;
        }
        setTimeout(tick, 300);
      });
      req.on('error', () => {
        if (Date.now() - started > timeoutMs) {
          resolve(false);
          return;
        }
        setTimeout(tick, 300);
      });
      req.end();
    };
    tick();
  });
}

let backendProcess = null;

app.setName('VixfloStream Downloader');

function resolveBackendCommand() {
  // Dev mode: run python from repo venv.
  // Packaged mode: expected backend EXE at resources/backend/VixfloStreamBackend.exe
  const isPackaged = app.isPackaged;
  if (isPackaged) {
    const exe = path.join(process.resourcesPath, 'backend', 'VixfloStreamBackend.exe');
    return { command: exe, args: [] };
  }

  const repoRoot = path.resolve(__dirname, '..', '..');
  const py = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
  const serverLauncher = path.join(repoRoot, 'server_launcher.py');
  return { command: py, args: [serverLauncher] };
}

async function startBackend(port) {
  const { command, args } = resolveBackendCommand();

  const cwd = app.isPackaged ? path.dirname(command) : undefined;

  backendProcess = spawn(command, args, {
    env: {
      ...process.env,
      AVE_HOST: '127.0.0.1',
      AVE_PORT: String(port),
      AVE_LOG_LEVEL: 'warning'
    },
    stdio: 'ignore',
    cwd,
    windowsHide: true
  });

  backendProcess.on('exit', (code) => {
    backendProcess = null;
    // If backend exits unexpectedly, close app.
    if (code !== 0) app.quit();
  });

  await waitForHealth(`http://127.0.0.1:${port}/health`);
}

function stopBackend() {
  if (!backendProcess) return;
  try {
    backendProcess.kill();
  } catch {
    // ignore
  }
  backendProcess = null;
}

async function createWindow() {
  const port = await getFreePort();
  await startBackend(port);

  const repoRoot = path.resolve(__dirname, '..', '..');
  const devIcon = path.join(repoRoot, 'assets', 'app-icon.ico');

  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    show: true,
    icon: app.isPackaged ? undefined : devIcon,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  await win.loadURL(`http://127.0.0.1:${port}/`);
}

async function runApp() {
  const mode = parseMode(process.argv);

  if (mode === 'server') {
    const port = Number(process.env.AVE_PORT || 8000);
    await startBackend(port);
    return;
  }

  if (mode === 'browser') {
    const port = await getFreePort();
    await startBackend(port);
    await shell.openExternal(`http://127.0.0.1:${port}/`);
    return;
  }

  await createWindow();
}

app.whenReady().then(runApp);

app.on('window-all-closed', () => {
  const mode = parseMode(process.argv);
  if (mode === 'desktop') {
    stopBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  stopBackend();
});
