const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PORT = 47321;
let engine = null;
let windowRef = null;

function pythonCommands() {
  const local = process.env.LOCALAPPDATA || "";
  const versions = ["313", "312", "311", "310", "39"];
  const found = [
    { cmd: "py", args: ["-3"] },
    { cmd: "python", args: [] },
    { cmd: "python3", args: [] },
  ];
  for (const version of versions) {
    const installed = path.join(local, "Programs", "Python", `Python${version}`, "python.exe");
    if (local && fs.existsSync(installed)) found.push({ cmd: installed, args: [] });
  }
  return found;
}

function spawnEngine() {
  const script = path.join(ROOT, "polka_serve.py");
  const candidates = pythonCommands();
  return new Promise((resolve, reject) => {
    const tryNext = (index) => {
      if (index >= candidates.length) {
        reject(new Error("Не найден Python 3. Поставь его с python.org."));
        return;
      }
      const candidate = candidates[index];
      const child = spawn(candidate.cmd, [...candidate.args, script], {
        cwd: ROOT,
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
      });
      let settled = false;
      const giveUp = () => {
        if (settled) return;
        settled = true;
        child.kill();
        tryNext(index + 1);
      };
      child.once("error", giveUp);
      child.once("exit", () => {
        if (!settled) giveUp();
      });
      const started = Date.now();
      const probe = () => {
        if (settled) return;
        const request = http.get(
          { hostname: "127.0.0.1", port: PORT, path: "/api/health", timeout: 400 },
          (response) => {
            response.resume();
            if (settled) return;
            if (response.statusCode === 200) {
              settled = true;
              engine = child;
              resolve();
              return;
            }
            if (Date.now() - started > 25000) giveUp();
            else setTimeout(probe, 300);
          },
        );
        request.on("error", () => {
          if (settled) return;
          if (Date.now() - started > 25000) giveUp();
          else setTimeout(probe, 300);
        });
      };
      setTimeout(probe, 300);
    };
    tryNext(0);
  });
}

function callEngine(method, urlPath, payload) {
  return new Promise((resolve, reject) => {
    const raw = payload ? Buffer.from(JSON.stringify(payload)) : null;
    const request = http.request(
      {
        hostname: "127.0.0.1",
        port: PORT,
        path: urlPath,
        method,
        headers: raw
          ? { "Content-Type": "application/json", "Content-Length": raw.length }
          : {},
        timeout: 120000,
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          try {
            const data = text ? JSON.parse(text) : {};
            if (response.statusCode >= 400) reject(new Error(data.error || text));
            else resolve(data);
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    request.on("error", reject);
    request.on("timeout", () => {
      request.destroy(new Error("Движок не ответил"));
    });
    if (raw) request.write(raw);
    request.end();
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: Number(process.env.POLKA_WIDTH) || 1220,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#1a140f",
    frame: false,
    autoHideMenuBar: true,
    title: "Полка",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  windowRef = win;
  win.loadFile(path.join(__dirname, "renderer", "index.html"), process.env.POLKA_PAGE ? { query: { page: process.env.POLKA_PAGE, ...(process.env.POLKA_SEARCH ? { q: process.env.POLKA_SEARCH } : {}), ...(process.env.POLKA_DL_OPEN ? { dl: "1" } : {}), ...(process.env.POLKA_JOBS_OPEN ? { jobs: "1" } : {}), ...(process.env.POLKA_ROOTWARN ? { rootwarn: "1" } : {}) } } : undefined);
}

app.whenReady().then(async () => {
  try {
    await spawnEngine();
  } catch (error) {
    dialog.showErrorBox("Полка", String(error.message || error));
  }
  createWindow();
});

app.on("window-all-closed", () => {
  if (engine) engine.kill();
  app.quit();
});

ipcMain.handle("polka:get", (_event, urlPath) => callEngine("GET", urlPath));
ipcMain.handle("polka:post", (_event, urlPath, payload) => callEngine("POST", urlPath, payload || {}));
ipcMain.handle("polka:folder", async () => {
  const parent = windowRef || BrowserWindow.getFocusedWindow();
  const result = await dialog.showOpenDialog(parent, { properties: ["openDirectory"] });
  if (result.canceled || !result.filePaths[0]) return "";
  return result.filePaths[0];
});
ipcMain.handle("polka:file", async () => {
  const parent = windowRef || BrowserWindow.getFocusedWindow();
  const result = await dialog.showOpenDialog(parent, {
    properties: ["openFile"],
    filters: [{ name: "Текст", extensions: ["txt"] }],
  });
  if (result.canceled || !result.filePaths[0]) return "";
  return result.filePaths[0];
});
ipcMain.handle("polka:open", (_event, url) => {
  if (typeof url === "string" && url.startsWith("http")) return shell.openExternal(url);
  return false;
});
ipcMain.handle("polka:reveal", (_event, target) => {
  if (typeof target !== "string" || !target) return false;
  const fs = require("fs");
  const path = require("path");
  if (fs.existsSync(target)) { shell.showItemInFolder(target); return true; }
  const dir = path.dirname(target);
  if (fs.existsSync(dir)) return shell.openPath(dir);
  return false;
});
ipcMain.handle("polka:win", (_event, action) => {
  const win = windowRef;
  if (!win) return false;
  if (action === "minimize") win.minimize();
  if (action === "maximize") {
    if (win.isMaximized()) win.unmaximize();
    else win.maximize();
  }
  if (action === "close") win.close();
  return true;
});
