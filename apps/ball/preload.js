const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ball", {
  isElectron: true,
  platform: process.platform,
  onOpenTab: (cb) => ipcRenderer.on("open-tab", (_e, url) => cb(url)),
  openExternal: (url) => ipcRenderer.send("open-external", url),
});
