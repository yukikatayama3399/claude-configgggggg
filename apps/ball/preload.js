const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ball", {
  isElectron: true,
  platform: process.platform,
  onOpenTab: (cb) => ipcRenderer.on("open-tab", (_e, url) => cb(url)),
  openExternal: (url) => ipcRenderer.send("open-external", url),
  // Messenger の読み取り結果
  onMessenger: (cb) => ipcRenderer.on("msgr-update", (_e, data) => cb(data)),
  messengerLast: () => ipcRenderer.invoke("msgr-last"),
  messengerShow: () => ipcRenderer.send("msgr-show"),
  messengerRefresh: () => ipcRenderer.send("msgr-refresh"),
  messengerUseUrl: (url) => ipcRenderer.send("msgr-use-url", url),
  // Gmail（gog 経由）
  gmailStatus: () => ipcRenderer.invoke("gmail-status"),
  gmailInbox: () => ipcRenderer.invoke("gmail-inbox"),
  gmailThread: (id) => ipcRenderer.invoke("gmail-thread", id),
  gmailDraft: (d) => ipcRenderer.invoke("gmail-draft", d),
  gmailAttachment: (a) => ipcRenderer.invoke("gmail-attachment", a),
});
