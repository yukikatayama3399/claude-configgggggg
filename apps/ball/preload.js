const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ball", {
  isElectron: true,
  platform: process.platform,
  onOpenTab: (cb) => ipcRenderer.on("open-tab", (_e, url) => cb(url)),
  openExternal: (url) => ipcRenderer.send("open-external", url),
  openPreview: (a) => ipcRenderer.send("open-preview", a),
  // Messenger の読み取り結果
  onMessenger: (cb) => ipcRenderer.on("msgr-update", (_e, data) => cb(data)),
  messengerLast: () => ipcRenderer.invoke("msgr-last"),
  messengerShow: () => ipcRenderer.send("msgr-show"),
  messengerRefresh: () => ipcRenderer.send("msgr-refresh"),
  messengerUseUrl: (url) => ipcRenderer.send("msgr-use-url", url),
  messengerThread: (href) => ipcRenderer.invoke("msgr-thread", href),
  // Gmail（gog 経由）
  gmailStatus: () => ipcRenderer.invoke("gmail-status"),
  gmailInbox: () => ipcRenderer.invoke("gmail-inbox"),
  gmailThread: (id) => ipcRenderer.invoke("gmail-thread", id),
  gmailDraft: (d) => ipcRenderer.invoke("gmail-draft", d),
  gmailSend: (d) => ipcRenderer.invoke("gmail-send", d),
  gmailAttachment: (a) => ipcRenderer.invoke("gmail-attachment", a),
  calendarEvents: (days) => ipcRenderer.invoke("calendar-events", days),
  driveMeta: (ids) => ipcRenderer.invoke("drive-meta", ids),
  // Slack（BALL の中でログインした Slack から読む）
  onSlack: (cb) => ipcRenderer.on("slack-update", (_e, data) => cb(data)),
  slackLast: () => ipcRenderer.invoke("slack-last"),
  slackShow: () => ipcRenderer.send("slack-show"),
  slackScan: () => ipcRenderer.send("slack-scan"),
  slackThread: (a) => ipcRenderer.invoke("slack-thread", a),
  slackPeople: (a) => ipcRenderer.invoke("slack-people", a),
  slackImage: (url) => ipcRenderer.invoke("slack-image", url),
  slackReact: (a) => ipcRenderer.invoke("slack-react", a),
  slackEmojiAll: () => ipcRenderer.invoke("slack-emoji-all"),
  slackSend: (a) => ipcRenderer.invoke("slack-send", a),
  // 真ん中の Claude（Mac の Claude Code）。送信の道具は持たせていない
  claudeStatus: () => ipcRenderer.invoke("claude-status"),
  claudeAsk: (a) => ipcRenderer.invoke("claude-ask", a),
  claudeStop: (reqId) => ipcRenderer.send("claude-stop", reqId),
  claudeJudge: (a) => ipcRenderer.invoke("claude-judge", a),
  onClaude: (cb) => ipcRenderer.on("claude-event", (_e, ev) => cb(ev)),
  onClaudeTool: (cb) => ipcRenderer.on("claude-tool", (_e, req) => cb(req, (r) => ipcRenderer.send("claude-tool-done", { callId: req.callId, ...r }))),
});
