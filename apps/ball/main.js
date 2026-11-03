// BALL デスクトップアプリ本体（Electron）。
// 右ペインのブラウザは <webview> で、ログイン状態は partition "persist:ball" に保存される。
const { app, BrowserWindow, session, shell, ipcMain } = require("electron");
const path = require("path");

// Google は Electron の UA だとログインを弾くことがあるので、普通の Chrome と同じ UA にする
const CHROME_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/" +
  process.versions.chrome.split(".")[0] + ".0.0.0 Safari/537.36";
app.userAgentFallback = CHROME_UA;

let win;
function createWindow() {
  win = new BrowserWindow({
    width: 1600, height: 1000, minWidth: 1100, minHeight: 680,
    title: "BALL",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    trafficLightPosition: { x: 14, y: 12 },
    backgroundColor: "#1C2632",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  session.fromPartition("persist:ball").setUserAgent(CHROME_UA);
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

// webview の安全設定と、ポップアップを BALL のタブで開く処理
app.on("web-contents-created", (_e, contents) => {
  contents.on("will-attach-webview", (_ev, webPreferences) => {
    delete webPreferences.preload;
    webPreferences.nodeIntegration = false;
    webPreferences.contextIsolation = true;
  });
  if (contents.getType() === "webview") {
    contents.setWindowOpenHandler(({ url }) => {
      // Google ログインなどの小窓はそのまま許可し、それ以外はタブで開く
      if (/accounts\.google\.com|appleid\.apple\.com|facebook\.com\/(login|dialog)/.test(url)) return { action: "allow" };
      if (win) win.webContents.send("open-tab", url);
      return { action: "deny" };
    });
  }
});

ipcMain.on("open-external", (_e, url) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});
