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
const MSGR_PARTITION = "persist:ball-messenger";
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
  // Facebook は「画面に見えていない」と会話一覧を描かないので、
  // 透明・クリック素通しの状態で実際に表示しておく（片山さんの画面には映らない）
  msgrWin = new BrowserWindow({
    show: false, width: 1200, height: 900, title: "BALL - Messenger 読み取り",
    opacity: 0, skipTaskbar: true, focusable: false, hasShadow: false,
    webPreferences: {
      // 右のブラウザとは保存場所を分ける（Messenger は会話データをブラウザ内に保存するので、
      // 同じ場所で2画面同時に開くと取り合いになって一覧が読み込み中のまま止まることがある）
      partition: MSGR_PARTITION,
      preload: path.join(__dirname, "readers", "messenger.js"),
      contextIsolation: true, nodeIntegration: false, backgroundThrottling: false,
    },
  });
  msgrWin.loadURL(MSGR_URL);
  msgrWin.once("ready-to-show", () => toBackground());
  // 閉じても読み取りは止めない（透明に戻すだけ）
  msgrWin.on("close", (e) => { if (!app.isQuitting) { e.preventDefault(); toBackground(); } });
  // 15分ごとに読み込み直して、一覧を新しくする
  setInterval(() => { if (msgrWin && !msgrWin.isDestroyed()) msgrWin.reload(); }, 15 * 60 * 1000);
}
function toBackground() {
  if (!msgrWin || msgrWin.isDestroyed()) return;
  msgrWin.setOpacity(0); msgrWin.setIgnoreMouseEvents(true); msgrWin.setFocusable(false);
  if (!msgrWin.isVisible()) msgrWin.showInactive();
}
let msgrMiss = 0;
ipcMain.on("msgr-result", (_e, data) => {
  // Messenger 以外のページ（パスキー案内のあとのホームなど）にいたら、Messenger に戻す。
  // ただし片山さんが読み取り画面を見ている間（操作中）は戻さない
  if (data.status === "away") {
    const userIsLooking = msgrWin && !msgrWin.isDestroyed() && msgrWin.getOpacity() > 0;
    if (!userIsLooking && msgrWin && !msgrWin.isDestroyed()) msgrWin.loadURL(msgrUrls[msgrIdx] || MSGR_CANDIDATES[0]);
    data = { ...data, note: userIsLooking ? "読み取り画面で操作中" : "Messenger のページに戻しています" };
    lastMsgr = data;
    if (win && !win.isDestroyed()) win.webContents.send("msgr-update", data);
    return;
  }
  // 一覧が3回続けて読めないときだけ、次の候補 URL に切り替える（読み込み途中で見切らない）
  if (data.status === "nolist") msgrMiss += 1; else msgrMiss = 0;
  if (data.status === "nolist" && msgrMiss >= 3 && msgrIdx < msgrUrls.length - 1 && !process.env.BALL_MSGR_URL) {
    msgrIdx += 1; msgrMiss = 0;
    data = { ...data, note: `別の URL を試しています（${msgrUrls[msgrIdx]}）` };
    if (msgrWin && !msgrWin.isDestroyed()) msgrWin.loadURL(msgrUrls[msgrIdx]);
  } else if (data.status === "nolist") {
    const last = msgrIdx >= msgrUrls.length - 1;
    data = { ...data, note: last ? `一覧が読めません（${msgrMiss}回目・押して診断）` : `読み込み待ち（${msgrMiss}/3）` };
  }
  lastMsgr = data;
  if (win && !win.isDestroyed()) win.webContents.send("msgr-update", data);
});
// 1つの会話の直近メッセージを、裏ウィンドウで読んで返す
let threadReq = 0;
ipcMain.handle("msgr-thread", (_e, arg) => new Promise((resolve) => {
  const { href, name, steps } = typeof arg === "string" ? { href: arg, name: "", steps: 4 } : arg;
  if (!msgrWin || msgrWin.isDestroyed()) return resolve({ ok: false, error: "Messenger の読み取り画面がありません" });
  const reqId = ++threadReq;
  const timer = setTimeout(() => { ipcMain.removeListener("thread-result", onRes); resolve({ ok: false, error: "時間内に読めませんでした" }); }, 30000 + (steps || 4) * 1500);
  function onRes(_ev, data) { if (data.reqId !== reqId) return; clearTimeout(timer); ipcMain.removeListener("thread-result", onRes); resolve(data); }
  ipcMain.on("thread-result", onRes);
  msgrWin.webContents.send("read-thread", { href, name, steps, reqId });
}));
// 右のブラウザで開いている Messenger のページを、読み取りに使う
ipcMain.on("msgr-use-url", (_e, url) => {
  if (!/^https:\/\/(www\.)?(facebook\.com\/messages|messenger\.com)/.test(url)) return;
  saveMsgrPref(url);
  msgrUrls = [url, ...MSGR_CANDIDATES.filter((u) => u !== url)]; msgrIdx = 0;
  if (msgrWin && !msgrWin.isDestroyed()) msgrWin.loadURL(url);
});
ipcMain.handle("msgr-last", () => lastMsgr);
// 確認用に読み取り画面を見えるようにする（閉じるとまた透明に戻る）
ipcMain.on("msgr-show", () => {
  if (!msgrWin || msgrWin.isDestroyed()) return;
  msgrWin.setIgnoreMouseEvents(false); msgrWin.setFocusable(true); msgrWin.setOpacity(1); msgrWin.show(); msgrWin.focus();
});
ipcMain.on("msgr-refresh", () => { if (msgrWin) msgrWin.reload(); });
app.on("before-quit", () => { app.isQuitting = true; });

// ---------- Slack の読み取り（透明な裏ウィンドウ・右のブラウザと同じログイン） ----------
const SLACK_URL = process.env.BALL_SLACK_URL || "https://app.slack.com/client";
let slackWin = null, lastSlack = null;
function startSlack() {
  slackWin = new BrowserWindow({
    show: false, width: 1200, height: 900, title: "BALL - Slack 読み取り",
    opacity: 0, skipTaskbar: true, focusable: false, hasShadow: false,
    webPreferences: { partition: "persist:ball", preload: path.join(__dirname, "readers", "slack.js"), contextIsolation: true, nodeIntegration: false, backgroundThrottling: false },
  });
  slackWin.loadURL(SLACK_URL);
  const toBg = () => { if (!slackWin || slackWin.isDestroyed()) return; slackWin.setOpacity(0); slackWin.setIgnoreMouseEvents(true); slackWin.setFocusable(false); if (!slackWin.isVisible()) slackWin.showInactive(); };
  slackWin.once("ready-to-show", toBg);
  slackWin.on("close", (e) => { if (!app.isQuitting) { e.preventDefault(); toBg(); slackWin.webContents.send("slack-scan-now"); } });
  setInterval(() => { if (slackWin && !slackWin.isDestroyed()) slackWin.reload(); }, 30 * 60 * 1000);
}
ipcMain.on("slack-result", (_e, data) => { lastSlack = data; if (win && !win.isDestroyed()) win.webContents.send("slack-update", data); });
ipcMain.handle("slack-last", () => lastSlack);
ipcMain.on("slack-show", () => { if (!slackWin || slackWin.isDestroyed()) return; slackWin.setIgnoreMouseEvents(false); slackWin.setFocusable(true); slackWin.setOpacity(1); slackWin.show(); slackWin.focus(); });
ipcMain.on("slack-scan", () => { if (slackWin && !slackWin.isDestroyed()) slackWin.webContents.send("slack-scan-now"); });
function askSlack(channel, payload, resultChannel, timeoutMs) {
  return new Promise((resolve) => {
    if (!slackWin || slackWin.isDestroyed()) return resolve({ ok: false, error: "Slack の読み取り画面がありません" });
    const reqId = Math.random().toString(36).slice(2);
    const timer = setTimeout(() => { ipcMain.removeListener(resultChannel, onRes); resolve({ ok: false, error: "時間内に返事がありませんでした" }); }, timeoutMs);
    function onRes(_ev, data) { if (data.reqId !== reqId) return; clearTimeout(timer); ipcMain.removeListener(resultChannel, onRes); resolve(data); }
    ipcMain.on(resultChannel, onRes);
    slackWin.webContents.send(channel, { ...payload, reqId });
  });
}
ipcMain.handle("slack-thread", (_e, a) => askSlack("slack-thread", { channel: a.channel, threadTs: a.threadTs }, "slack-thread-result", 30000));
// Slack の画像（ファイルのサムネイルなど）: BALL の中でログインした Slack（persist:ball）のクッキーで取ってきて、画面に渡す。
// 取りに行くのは Slack のファイルの置き場だけ
const slackImgCache = new Map();
ipcMain.handle("slack-image", async (e, url) => {
  if (!win || e.sender !== win.webContents) return { ok: false };
  url = String(url || "");
  const testHost = /^http:\/\/127\.0\.0\.1:\d+\//.test(SLACK_URL) && url.startsWith(new URL(SLACK_URL).origin + "/"); // 手元のテスト用 Slack だけ
  if (!testHost && !/^https:\/\/(files\.slack\.com|[\w-]+\.slack\.com\/files|[\w.-]*slack-edge\.com)\//.test(url)) return { ok: false, error: "Slack のファイル以外は取りません" };
  if (slackImgCache.has(url)) return { ok: true, data: slackImgCache.get(url) };
  try {
    const r = await session.fromPartition("persist:ball").fetch(url);
    const type = r.headers.get("content-type") || "";
    if (!r.ok || !/^image\//.test(type)) return { ok: false, error: `取れませんでした（${r.status} ${type.split(";")[0]}）` };
    const buf = Buffer.from(await r.arrayBuffer());
    if (buf.length > 8 * 1024 * 1024) return { ok: false, error: "大きすぎます" };
    const data = `data:${type.split(";")[0]};base64,${buf.toString("base64")}`;
    slackImgCache.set(url, data);
    if (slackImgCache.size > 300) slackImgCache.delete(slackImgCache.keys().next().value);
    return { ok: true, data };
  } catch (err) { return { ok: false, error: String(err.message || err) }; }
});
// Messenger の写真: Messenger にログインした裏の読み取り画面（persist:ball-messenger）のクッキーで取ってくる
const msgrImgCache = new Map();
ipcMain.handle("msgr-image", async (e, url) => {
  if (!win || e.sender !== win.webContents) return { ok: false };
  url = String(url || "");
  if (!/^https:\/\/[\w.-]*(fbcdn\.net|fbsbx\.com|facebook\.com|messenger\.com)\//.test(url)) return { ok: false, error: "Facebook の写真以外は取りません" };
  if (msgrImgCache.has(url)) return { ok: true, data: msgrImgCache.get(url) };
  try {
    const r = await session.fromPartition(MSGR_PARTITION).fetch(url);
    const type = (r.headers.get("content-type") || "").split(";")[0];
    if (!r.ok || !/^image\//.test(type)) return { ok: false, error: `取れませんでした（${r.status}）` };
    const buf = Buffer.from(await r.arrayBuffer());
    if (buf.length > 10 * 1024 * 1024) return { ok: false, error: "大きすぎます" };
    const data = `data:${type};base64,${buf.toString("base64")}`;
    msgrImgCache.set(url, data); if (msgrImgCache.size > 300) msgrImgCache.delete(msgrImgCache.keys().next().value);
    return { ok: true, data };
  } catch (err) { return { ok: false, error: String(err.message || err) }; }
});
ipcMain.handle("slack-people", (_e, a) => askSlack("slack-people", { channel: a.channel }, "slack-people-result", 60000));
// 送信: BALL 本体の画面（片山さんが押す確認ボタン）からだけ受け付ける。AI や右のブラウザのページからは呼べない
ipcMain.handle("slack-send", async (e, a) => {
  if (!win || e.sender !== win.webContents) return { ok: false, error: "BALL 本体の画面からの送信だけ受け付けます" };
  const files = (a && Array.isArray(a.files) ? a.files : []).slice(0, 10);
  if (!a || !a.channel || (!String(a.text || "").trim() && !files.length)) return { ok: false, error: "送り先か本文が空です" };
  // 添付: Slack に上げる先を聞いて、BALL の中の Slack のログイン（persist:ball）でここから上げる
  const fileIds = [];
  for (const f of files) {
    const buf = Buffer.from(f.data);
    const u = await askSlack("slack-upload-url", { filename: f.name, length: buf.length }, "slack-upload-url-result", 30000);
    if (!u.ok) return { ok: false, error: `${f.name} を上げられませんでした: ${u.error}` };
    const form = new FormData();
    form.append("file", new Blob([buf], { type: f.type || "application/octet-stream" }), f.name);
    const r = await session.fromPartition("persist:ball").fetch(u.uploadUrl, { method: "POST", body: form, headers: { Authorization: "Bearer " + u.token } }).catch((err) => ({ ok: false, status: String(err.message || err) }));
    if (!r.ok) return { ok: false, error: `${f.name} を上げられませんでした（${r.status}）` };
    fileIds.push({ id: u.fileId, title: f.name });
  }
  return askSlack("slack-send", { channel: a.channel, threadTs: a.threadTs || "", text: a.text || "", fileIds }, "slack-send-result", 60000);
});
// スタンプ: BALL 本体の画面（片山さんのクリック）からだけ
ipcMain.handle("slack-react", (e, a) => {
  if (!win || e.sender !== win.webContents) return { ok: false, error: "BALL 本体の画面からだけ受け付けます" };
  if (!a || !a.channel || !a.ts || !/^[a-z0-9_+'-]+(::skin-tone-\d)?$/i.test(String(a.name || ""))) return { ok: false, error: "スタンプの指定がおかしいです" };
  return askSlack("slack-react", { channel: a.channel, ts: a.ts, name: a.name, remove: !!a.remove }, "slack-react-result", 20000);
});
ipcMain.handle("slack-emoji-all", () => askSlack("slack-emoji-all", {}, "slack-emoji-all-result", 30000));

app.whenReady().then(() => {
  session.fromPartition("persist:ball").setUserAgent(CHROME_UA);
  session.fromPartition(MSGR_PARTITION).setUserAgent(CHROME_UA);
  createWindow();
  if (process.env.BALL_NO_MSGR !== "1") startMessenger();
  if (process.env.BALL_NO_SLACK !== "1") startSlack();
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
ipcMain.handle("calendar-events", wrap((days) => gmail.calendar(days || 2)));
ipcMain.handle("drive-meta", wrap((ids) => gmail.driveMeta(ids)));
ipcMain.handle("gmail-draft", wrap((d) => gmail.saveDraft(d)));
// 送信: BALL 本体の画面（片山さんが押す確認ボタン）からだけ受け付ける。
// 右のブラウザのページや、将来つなぐ AI からは呼べない。AI に送信の手段は渡さない。
ipcMain.handle("gmail-send", async (e, d) => {
  if (!win || e.sender !== win.webContents) return { ok: false, error: "BALL 本体の画面からの送信だけ受け付けます" };
  return wrap((x) => gmail.sendDraft(x))(e, d);
});
ipcMain.handle("gmail-attachment", wrap(async (a) => { const p = await gmail.openAttachment(a); await shell.openPath(p); return p; }));

// ---------- リンクの確認ウィンドウ ----------
// 本文のリンク（申込フォーム・資料など）を、右のブラウザと同じログイン（persist:ball）のまま別ウィンドウで開く。
// BALL 本体の画面からだけ受け付け、http(s) 以外は開かない。ウィンドウには BALL の窓口（preload）を渡さない
let previewSeq = 0;
function openPreview(url, title) {
  if (!/^https?:\/\//i.test(String(url || ""))) return;
  const b = win && !win.isDestroyed() ? win.getBounds() : { x: 80, y: 60, width: 1400, height: 900 };
  const off = (previewSeq++ % 6) * 28;
  const pw = new BrowserWindow({
    width: Math.min(1120, b.width - 80), height: Math.min(880, b.height - 40),
    x: b.x + Math.round(b.width * 0.3) - 40 + off, y: b.y + 40 + off,
    title: title ? `${title} — BALL` : "BALL", backgroundColor: "#FFFFFF",
    webPreferences: { partition: "persist:ball", contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  pw.webContents.setWindowOpenHandler(({ url: u }) => {
    if (/accounts\.google\.com|appleid\.apple\.com|facebook\.com\/(login|dialog)/.test(u)) return { action: "allow" };
    openPreview(u, "");
    return { action: "deny" };
  });
  // Esc で閉じる
  pw.webContents.on("before-input-event", (_e, input) => { if (input.type === "keyDown" && input.key === "Escape" && !input.meta && !input.control) pw.close(); });
  pw.loadURL(url);
}
ipcMain.on("open-preview", (e, a) => {
  if (!win || e.sender !== win.webContents) return;
  openPreview(a && a.url, a && a.title);
});

ipcMain.on("open-external", (_e, url) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});

// ---------- 真ん中の Claude ----------
// 画面（BALL 本体）からの送信で claude を呼び、返事を画面へ流す。道具の呼び出しはここで処理する。
// 送信の道具は無い。下書き・メモは画面に渡して反映するだけ。Sheets の記入は「シート記入まで」のときだけ。
const claude = require("./claude-bridge");
const clip = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n) + `\n…（長いので ${s.length - n} 文字省略）` : s; };
const askRenderer = (() => {
  let seq = 0; const wait = new Map();
  ipcMain.on("claude-tool-done", (e, r) => { if (win && e.sender === win.webContents && wait.has(r.callId)) { wait.get(r.callId)(r); wait.delete(r.callId); } });
  return (payload) => new Promise((resolve) => {
    if (!win || win.isDestroyed()) return resolve({ ok: false, error: "BALL の画面が閉じています" });
    const callId = ++seq; wait.set(callId, resolve);
    win.webContents.send("claude-tool", { callId, ...payload });
    setTimeout(() => { if (wait.has(callId)) { wait.delete(callId); resolve({ ok: false, error: "画面からの返事がありませんでした" }); } }, 10000);
  });
})();
async function claudeTool(ctx, name, a) {
  const g = gmail.ai;
  if (name === "gmail_search") return JSON.stringify(await g.searchMail(a.query, a.max), null, 1);
  if (name === "gmail_read_thread") {
    const t = await g.readThread(a.thread_id);
    return clip(t.messages.map((m) => `差出人: ${m.from}\n宛先: ${m.to}${m.cc ? "\nCC: " + m.cc : ""}\n日時: ${m.date}\n件名: ${m.subject}${(m.attachments || []).length ? "\n添付: " + m.attachments.map((x) => x.filename).join(", ") : ""}\n\n${clip(m.body, 8000)}`).join("\n\n----\n\n"), 60000);
  }
  if (name === "calendar_events") return clip(JSON.stringify((await g.calendar(a.days || 7)).map((e) => ({ 予定: e.summary, 開始: e.start, 終了: e.end, 場所: e.location, 主催: e.organizer, 自分の返事: e.myStatus, 参加者: e.attendees.map((x) => x.name).slice(0, 15), 説明: clip(e.description, 600) })), null, 1), 40000);
  if (name === "drive_search") return JSON.stringify((await g.searchDrive(a.query, a.max)).map((f) => ({ ...f, url: f.webViewLink || `https://drive.google.com/open?id=${f.id}` })), null, 1);
  if (name === "docs_read") return clip(await g.readDoc(a.doc), 80000);
  if (name === "sheets_read") return clip(JSON.stringify(await g.readSheet(a.sheet, a.range)), 60000);
  if (name === "sheets_write") {
    if (ctx.perm === "read") throw new Error("今の権限は「読むだけ」なので書けません");
    await g.writeSheet(a.sheet, a.range, a.values);
    return `${a.range} に書きました`;
  }
  if (name === "ball_set_draft" || name === "ball_set_memo") {
    if (ctx.perm === "read") throw new Error("今の権限は「読むだけ」なので書けません");
    const r = await askRenderer({ ballId: ctx.ballId, name, args: a });
    if (!r.ok) throw new Error(r.error || "書けませんでした");
    return r.text || "OK";
  }
  throw new Error("知らない道具です: " + name);
}
ipcMain.handle("claude-status", async () => ({ ...(await claude.status()), cwd: claude.WORK }));
ipcMain.handle("claude-ask", (e, a) => {
  if (!win || e.sender !== win.webContents) return { ok: false, error: "BALL 本体の画面からだけ受け付けます" };
  const reqId = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const emit = (ev) => { if (win && !win.isDestroyed()) win.webContents.send("claude-event", { reqId, ballId: a.ballId, ...ev }); };
  gmail.gogForClaude().catch(() => null)
    .then((gog) => claude.ask({ reqId, ballId: a.ballId, sessionId: a.sessionId, prompt: a.prompt, model: a.model, perm: a.perm, gog }, emit, claudeTool))
    .catch((err) => emit({ type: "error", error: String(err.message || err) }));
  return { ok: true, reqId };
});
ipcMain.handle("claude-judge", (e, a) => {
  if (!win || e.sender !== win.webContents) return { ok: false, error: "BALL 本体の画面からだけ受け付けます" };
  return claude.judge({ items: (a && a.items) || [], balls: (a && a.balls) || [], model: a && a.model });
});
ipcMain.on("claude-stop", (e, reqId) => { if (win && e.sender === win.webContents) claude.stop(reqId); });
