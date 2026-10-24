const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("polka", {
  get: (urlPath) => ipcRenderer.invoke("polka:get", urlPath),
  post: (urlPath, payload) => ipcRenderer.invoke("polka:post", urlPath, payload),
  folder: () => ipcRenderer.invoke("polka:folder"),
  file: () => ipcRenderer.invoke("polka:file"),
  open: (url) => ipcRenderer.invoke("polka:open", url),
  reveal: (target) => ipcRenderer.invoke("polka:reveal", target),
  minimize: () => ipcRenderer.invoke("polka:win", "minimize"),
  maximize: () => ipcRenderer.invoke("polka:win", "maximize"),
  close: () => ipcRenderer.invoke("polka:win", "close"),
});
