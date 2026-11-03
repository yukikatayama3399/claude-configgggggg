// Messenger 読み取り係（見えない裏ウィンドウの preload）。
// 右側のブラウザと同じログイン状態（partition "persist:ball"）で facebook.com/messages を開き、
// 会話一覧を1分ごとに読んで、アプリ本体に送る。書き込み・送信は一切しない。
const { ipcRenderer } = require("electron");

const TIME_RE = /(\d+\s*(秒|分|時間|日|週|か月|年|m|h|d|w|y))$|^(月|火|水|木|金|土|日)(曜日?)?$|^\d{1,2}\/\d{1,2}$|^\d{1,2}:\d{2}$/;

function isLoginPage() {
  return /login|checkpoint/.test(location.pathname) ||
    !!document.querySelector('input[name="email"], input[name="pass"], form[action*="login"]');
}

function readRow(a) {
  const href = a.getAttribute("href") || "";
  const m = href.match(/\/t\/([^/?#]+)/);
  if (!m) return null;
  let lines = (a.innerText || "").split("\n").map((s) => s.trim()).filter((s) => s && s !== "·");
  if (lines.length < 2) {
    // 1行に詰まっている作りのときは、文字の入った末端の要素を順に拾う
    lines = [...a.querySelectorAll("*")].filter((el) => el.childElementCount === 0)
      .map((el) => el.textContent.trim()).filter((s) => s && s !== "·");
  }
  if (lines.length < 2) return null;
  const name = lines[0];
  let rest = lines.slice(1);
  let time = "";
  if (rest.length && TIME_RE.test(rest[rest.length - 1])) time = rest.pop();
  let snippet = rest.join(" ").replace(/\s*·\s*$/, "");
  const mt = snippet.match(/\s·\s([^·]+)$/);
  if (!time && mt && TIME_RE.test(mt[1].trim())) { time = mt[1].trim(); snippet = snippet.slice(0, mt.index); }
  const mine = /^(あなた|You)\s*[:：]/.test(snippet);

  // 未読の判定: aria-label に「未読」、または名前が太字
  const row = a.closest('[role="row"], [role="listitem"], [role="gridcell"]');
  const label = (a.getAttribute("aria-label") || "") + " " + ((row && row.getAttribute("aria-label")) || "");
  let unread = /未読|unread/i.test(label) || !!a.querySelector('[aria-label*="未読"], [aria-label*="nread"]');
  if (!unread) {
    const nameSpan = [...a.querySelectorAll("span")].find((s) => s.childElementCount === 0 && s.textContent.trim() === name);
    if (nameSpan && parseInt(getComputedStyle(nameSpan).fontWeight, 10) >= 600) unread = true;
  }
  let abs;
  try { abs = new URL(href, location.href.startsWith("http") ? location.origin : "https://www.facebook.com").href; }
  catch (e) { abs = "https://www.facebook.com" + href; }
  return { id: m[1], name, snippet, time, unread, mine, href: abs };
}

// 診断: 名前やメッセージの中身は入れず、画面の作りだけを数える
function diagnose(anchors) {
  const shape = (s) => String(s).replace(/\d+/g, "#");
  const roles = {};
  const samples = anchors.slice(0, 8).map((a) => {
    const lines = (a.innerText || "").split("\n").map((s) => s.trim()).filter(Boolean);
    const leaves = [...a.querySelectorAll("*")].filter((el) => el.childElementCount === 0 && el.textContent.trim()).length;
    const row = a.closest("[role]");
    const role = row ? row.getAttribute("role") : "-";
    roles[role] = (roles[role] || 0) + 1;
    return { href: shape(a.getAttribute("href") || ""), lines: lines.length, leaves, role, aria: !!a.getAttribute("aria-label"), visible: a.getBoundingClientRect().height > 0 };
  });
  return {
    path: shape(location.pathname), title: document.title.replace(/\(\d+\)/, "(#)").slice(0, 40),
    anchorsT: document.querySelectorAll('a[href*="/t/"]').length,
    anchorsMessages: document.querySelectorAll('a[href*="/messages/"]').length,
    grids: document.querySelectorAll('[role="grid"], [role="list"], [role="navigation"]').length,
    rows: document.querySelectorAll('[role="row"], [role="listitem"]').length,
    samples, roles,
  };
}

function scrape() {
  const at = Date.now();
  if (isLoginPage()) return ipcRenderer.send("msgr-result", { at, status: "login", url: location.href, convos: [] });
  const anchors = [...document.querySelectorAll('a[href*="/t/"]')];
  const seen = new Set(), convos = [];
  for (const a of anchors) {
    const r = readRow(a);
    if (!r || seen.has(r.id)) continue;
    seen.add(r.id); convos.push(r);
    if (convos.length >= 30) break;
  }
  ipcRenderer.send("msgr-result", { at, status: convos.length ? "ok" : "nolist", url: location.href, convos, diag: diagnose(anchors) });
}

// ---------- 1つの会話の直近メッセージを読む ----------
// 会話のページ（/t/<id>）で、メッセージ欄（role=main）の行を上から読む。
// 右寄せの吹き出し＝自分、左寄せ＝相手、として判定する。
function readConversation() {
  const main = document.querySelector('[role="main"]') || document.body;
  const mrect = main.getBoundingClientRect();
  const mid = mrect.left + mrect.width / 2;
  const rows = [...main.querySelectorAll('[role="row"]')];
  const out = [];
  for (const row of rows) {
    const textEls = [...row.querySelectorAll('div[dir="auto"], span[dir="auto"]')].filter((el) => el.childElementCount === 0 || el.querySelector("br"));
    let text = textEls.map((el) => el.innerText.trim()).filter(Boolean).join("\n");
    const imgs = [...row.querySelectorAll("img")].filter((im) => im.getBoundingClientRect().width > 80).length;
    if (!text && !imgs) continue;
    if (/^(\d{1,2}:\d{2}|\d+月\d+日.*|今日|昨日|月|火|水|木|金|土|日曜日?)$/.test(text)) continue; // 日付・時刻の区切り
    const anchor = textEls[0] || row.querySelector("img") || row;
    const r = anchor.getBoundingClientRect();
    const mine = r.width > 0 ? r.left + r.width / 2 > mid : false;
    if (imgs && !text) text = imgs > 1 ? `📷 画像 ${imgs}枚` : "📷 画像";
    else if (imgs) text += `\n📷 画像 ${imgs}枚`;
    const prev = out[out.length - 1];
    if (prev && prev.text === text && prev.mine === mine) continue;
    out.push({ mine, text });
  }
  const name = (document.querySelector('[role="main"] h1, [role="main"] h2') || {}).innerText || "";
  return { name: name.trim(), messages: out.slice(-12), rows: rows.length };
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let readingThread = false;
ipcRenderer.on("read-thread", async (_e, { href, reqId }) => {
  readingThread = true;
  const back = location.href;
  try {
    // 会話のリンクを押して開く（ページを読み込み直すより速く、ログイン状態も崩れない）
    const path = new URL(href).pathname;
    const link = [...document.querySelectorAll('a[href*="/t/"]')].find((a) => (a.getAttribute("href") || "").startsWith(path) || href.includes(a.getAttribute("href")));
    if (link) link.click(); else { history.pushState({}, "", path); window.dispatchEvent(new PopStateEvent("popstate")); }
    let res = { messages: [] };
    for (let i = 0; i < 12; i++) { await sleep(700); res = readConversation(); if (res.messages.length) break; }
    ipcRenderer.send("thread-result", { reqId, ok: true, ...res });
  } catch (err) {
    ipcRenderer.send("thread-result", { reqId, ok: false, error: String(err && err.message || err) });
  } finally {
    readingThread = false;
    if (location.href !== back) { try { history.back(); } catch (e) { /* そのままでよい */ } }
  }
});

window.addEventListener("DOMContentLoaded", () => {
  setTimeout(scrape, 8000);
  setInterval(scrape, 60 * 1000);
});
ipcRenderer.on("scrape-now", scrape);
