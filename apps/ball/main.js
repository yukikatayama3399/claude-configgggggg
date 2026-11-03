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
  // Mac 以外は本体を閉じたら終了（裏ウィンドウが残って終わらない、を防ぐ）
  win.on("closed", () => { if (process.platform !== "darwin") { app.isQuitting = true; app.quit(); } });
}

// ---------- Messenger の読み取り（見えない裏ウィンドウ） ----------
// 読みに行く候補。会話一覧が読めなければ次を試す。片山さんが選んだ URL があれば最優先。
const fs = require("fs");
const MSGR_CANDIDATES = ["https://www.facebook.com/messages/t/", "https://www.messenger.com/t/", "https://www.facebook.com/messages/"];
const msgrPrefFile = () => path.join(app.getPath("userData"), "messenger.json");
function loadMsgrPref() { try { return JSON.parse(fs.readFileSync(msgrPrefFile(), "utf8")).url || null; } catch (e) { return null; } }
function saveMsgrPref(url) { try { fs.writeFileSync(msgrPrefFile(), JSON.stringify({ url })); } catch (e) { /* 保存できなくても動く */ } }
let msgrUrls = [], msgrIdx = 0;
let msgrWin = null, lastMsgr = null;
function startMessenger() {
  const pref = process.env.BALL_MSGR_URL || loadMsgrPref();
  msgrUrls = pref ? [pref, ...MSGR_CANDIDATES.filter((u) => u !== pref)] : MSGR_CANDIDATES.slice();
  const MSGR_URL = msgrUrls[0];
  msgrWin = new BrowserWindow({
    show: false, width: 1200, height: 900, title: "BALL - Messenger 読み取り",
    webPreferences: {
      partition: "persist:ball",
      preload: path.join(__dirname, "readers", "messenger.js"),
      contextIsolation: true, nodeIntegration: false, backgroundThrottling: false,
    },
  });
  msgrWin.loadURL(MSGR_URL);
  // 裏ウィンドウを閉じても読み取りは止めない（隠すだけ）
  msgrWin.on("close", (e) => { if (!app.isQuitting) { e.preventDefault(); msgrWin.hide(); } });
  // 15分ごとに読み込み直して、一覧を新しくする
  setInterval(() => { if (msgrWin && !msgrWin.isDestroyed()) msgrWin.reload(); }, 15 * 60 * 1000);
}
ipcMain.on("msgr-result", (_e, data) => {
  // 一覧が読めないときは、次の候補 URL に切り替えてみる（ログイン画面のときは切り替えない）
  if (data.status === "nolist" && msgrIdx < msgrUrls.length - 1 && !process.env.BALL_MSGR_URL) {
    msgrIdx += 1;
    data = { ...data, note: `別の URL を試しています（${msgrUrls[msgrIdx]}）` };
    if (msgrWin && !msgrWin.isDestroyed()) msgrWin.loadURL(msgrUrls[msgrIdx]);
  }
  if (data.status === "ok") msgrIdx = Math.max(0, msgrUrls.indexOf(data.url) >= 0 ? msgrUrls.indexOf(data.url) : msgrIdx);
  lastMsgr = data;
  if (win && !win.isDestroyed()) win.webContents.send("msgr-update", data);
});
// 1つの会話の直近メッセージを、裏ウィンドウで読んで返す
let threadReq = 0;
ipcMain.handle("msgr-thread", (_e, href) => new Promise((resolve) => {
  if (!msgrWin || msgrWin.isDestroyed()) return resolve({ ok: false, error: "Messenger の読み取り画面がありません" });
  const reqId = ++threadReq;
  const timer = setTimeout(() => { ipcMain.removeListener("thread-result", onRes); resolve({ ok: false, error: "時間内に読めませんでした" }); }, 20000);
  function onRes(_ev, data) { if (data.reqId !== reqId) return; clearTimeout(timer); ipcMain.removeListener("thread-result", onRes); resolve(data); }
  ipcMain.on("thread-result", onRes);
  msgrWin.webContents.send("read-thread", { href, reqId });
}));
// 右のブラウザで開いている Messenger のページを、読み取りに使う
ipcMain.on("msgr-use-url", (_e, url) => {
  if (!/^https:\/\/(www\.)?(facebook\.com\/messages|messenger\.com)/.test(url)) return;
  saveMsgrPref(url);
  msgrUrls = [url, ...MSGR_CANDIDATES.filter((u) => u !== url)]; msgrIdx = 0;
  if (msgrWin && !msgrWin.isDestroyed()) msgrWin.loadURL(url);
});
ipcMain.handle("msgr-last", () => lastMsgr);
ipcMain.on("msgr-show", () => { if (msgrWin) { msgrWin.show(); msgrWin.focus(); } });
ipcMain.on("msgr-refresh", () => { if (msgrWin) msgrWin.reload(); });
app.on("before-quit", () => { app.isQuitting = true; });

app.whenReady().then(() => {
  session.fromPartition("persist:ball").setUserAgent(CHROME_UA);
  createWindow();
  if (process.env.BALL_NO_MSGR !== "1") startMessenger();
  // 裏の Messenger ウィンドウは数えずに、本体ウィンドウが無ければ作り直す
  app.on("activate", () => { if (!win || win.isDestroyed()) createWindow(); });
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

// ---------- Gmail（Mac の gog 経由） ----------
const gmail = require("./gmail-bridge");
const wrap = (fn) => async (_e, arg) => { try { return { ok: true, data: await fn(arg) }; } catch (err) { return { ok: false, error: String(err.message || err) }; } };
ipcMain.handle("gmail-status", () => gmail.status());
ipcMain.handle("gmail-inbox", wrap(() => gmail.inbox()));
ipcMain.handle("gmail-thread", wrap((id) => gmail.thread(id)));
ipcMain.handle("gmail-draft", wrap((d) => gmail.saveDraft(d)));
ipcMain.handle("gmail-attachment", wrap(async (a) => { const p = await gmail.openAttachment(a); await shell.openPath(p); return p; }));

ipcMain.on("open-external", (_e, url) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});
