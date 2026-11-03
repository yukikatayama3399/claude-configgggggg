// Messenger 読み取り係（見えない裏ウィンドウの preload）。
// 右側のブラウザとは別の保存場所（partition "persist:ball-messenger"）で facebook.com/messages を開き、
// （初回だけ、この読み取り画面で Facebook にログインが必要）
// 会話一覧を1分ごとに読んで、アプリ本体に送る。書き込み・送信は一切しない。
const { ipcRenderer } = require("electron");

// 一覧の時刻表示（「5日」「3時間」「火」「10/30」「14:05」など）。行全体が時刻のときだけ一致させる
const TIME_RE = /^(\d+\s*(秒|分|時間|日|週|か月|年|m|h|d|w|y)|(月|火|水|木|金|土|日)(曜日?)?|\d{1,2}\/\d{1,2}|\d{1,2}:\d{2})$/;

function isLoginPage() {
  return /login|checkpoint/.test(location.pathname) ||
    !!document.querySelector('input[name="email"], input[name="pass"], form[action*="login"]');
}

// 一覧の1行（リンクでも、リンクでない行でもよい）から、名前・最後のメッセージ・時刻・未読を読む
function linesOf(el) {
  let lines = (el.innerText || "").split("\n").map((s) => s.trim()).filter((s) => s && s !== "·");
  if (lines.length < 2) {
    // 1行に詰まっている作りのときは、文字の入った末端の要素を順に拾う
    lines = [...el.querySelectorAll("*")].filter((x) => x.childElementCount === 0)
      .map((x) => x.textContent.trim()).filter((s) => s && s !== "·");
  }
  return lines;
}
function absUrl(href) {
  try { return new URL(href, location.href.startsWith("http") ? location.origin : "https://www.facebook.com").href; }
  catch (e) { return "https://www.facebook.com" + href; }
}
// 名前の代わりに出てくる状態表示（アイコンの「オンライン中」など）。名前としては使わない
const STATUS_RE = /^(オンライン中|オンライン|アクティブ|アクティブ中|Active now|Online|\d+\s*(分|時間)前にアクティブ|Active \d+\w* ago)$/i;
function readItem(el, href) {
  let lines = linesOf(el).filter((l) => !STATUS_RE.test(l));
  // 読み上げ用の「未読メッセージ:」は外して、未読の印として使う
  let unreadMark = false;
  lines = lines.map((l) => { const x = l.replace(/^(未読メッセージ|Unread message)\s*[:：]\s*/i, ""); if (x !== l) unreadMark = true; return x; }).filter(Boolean);
  if (lines.length < 2) return null;
  let name = lines[0];
  if (name.length > 60) return null;
  let rest = lines.slice(1);
  let time = "";
  if (rest.length && TIME_RE.test(rest[rest.length - 1])) time = rest.pop();
  // 名前の途中に絵文字があると名前が2行に割れる（例: オーリーズ✖alpaka）。短くて「:」の無い行は名前の続きとみなす
  while (rest.length >= 2 && !/[:：]/.test(rest[0]) && rest[0].length <= 24) name += " " + rest.shift();
  let snippet = rest.join(" ").replace(/\s*·\s*$/, "");
  const mt = snippet.match(/\s·\s([^·]+)$/);
  if (!time && mt && TIME_RE.test(mt[1].trim())) { time = mt[1].trim(); snippet = snippet.slice(0, mt.index); }
  snippet = snippet.replace(/\s*·?\s*返信しますか？\s*$/, "").trim();
  // 自分が最後に送った / 相手が自分のメッセージにリアクションしただけ → こちらの返事は要らない
  const reactedOnly = /あなたのメッセージに.*リアクション|reacted .* to your message/i.test(snippet);
  const mine = /^(あなた|You)\s*[:：]/.test(snippet) || reactedOnly;
  // 未読の判定: 「未読メッセージ:」、aria-label に「未読」、または名前が太字
  const row = el.closest('[role="row"], [role="listitem"], [role="gridcell"]') || el;
  const label = (el.getAttribute("aria-label") || "") + " " + (row.getAttribute("aria-label") || "");
  let unread = unreadMark || /未読|unread/i.test(label) || !!el.querySelector('[aria-label*="未読"], [aria-label*="nread"]');
  if (!unread) {
    const first = lines[0];
    const nameSpan = [...el.querySelectorAll("*")].find((x) => x.childElementCount === 0 && x.textContent.trim() === first);
    if (nameSpan && parseInt(getComputedStyle(nameSpan).fontWeight, 10) >= 600) unread = true;
  }
  if (reactedOnly) unread = false; // リアクションだけなら返事は要らないので、未読でもボールにしない
  const m = (href || "").match(/\/t\/([^/?#]+)/);
  return { id: m ? m[1] : "n:" + name, name, snippet, time, unread, mine, href: m ? absUrl(href) : location.href, byRow: !m };
}
// リンクの無い作りのための候補: 画面の左側にある、会話一覧らしい高さの行
function listRows() {
  const w = window.innerWidth || 1200;
  return [...document.querySelectorAll('[role="row"], [role="listitem"], [role="gridcell"] > div')].filter((r) => {
    const b = r.getBoundingClientRect();
    return b.height >= 36 && b.height <= 160 && b.left < w * 0.45 && b.width > 120;
  });
}

// 目印（role やリンク）が無い作りのための候補: 見た目で探す。
// 画面の左側にあって、高さが1行ぶん、アイコン画像と2〜5行の文字を含む部品のうち、いちばん内側のもの。
function visualRows() {
  const w = window.innerWidth || 1200;
  const isCand = (el) => {
    const b = el.getBoundingClientRect();
    if (b.height < 48 || b.height > 130 || b.width < 200 || b.width > w * 0.6 || b.left > w * 0.4 || b.top < 120) return false;
    const n = linesOf(el).length;
    if (n < 2 || n > 6) return false;
    return [...el.querySelectorAll("img, svg image, [style*='background-image']")].some((im) => { const r = im.getBoundingClientRect(); return r.width >= 24 && r.width <= 80; });
  };
  const all = [...document.querySelectorAll("div, a, li")].filter(isCand);
  return all.filter((el) => !all.some((o) => o !== el && el.contains(o)));
}

// 診断: 名前やメッセージの中身は入れず、画面の作りだけを数える
function diagnose(anchors) {
  const shape = (s) => String(s).replace(/\d+/g, "#");
  const w = window.innerWidth || 1;
  const sample = (el) => {
    const b = el.getBoundingClientRect();
    return { lines: linesOf(el).length, h: Math.round(b.height), left: Math.round((b.left / w) * 100) + "%", width: Math.round(b.width), role: el.getAttribute("role") || (el.closest("[role]") || { getAttribute: () => "-" }).getAttribute("role"),
      link: !!el.querySelector("a[href]") || el.tagName === "A", href: shape((el.getAttribute("href") || (el.querySelector("a[href]") || { getAttribute: () => "" }).getAttribute("href") || "").slice(0, 40)),
      aria: !!el.getAttribute("aria-label"), img: el.querySelectorAll("img, svg image").length };
  };
  const rows = [...document.querySelectorAll('[role="row"], [role="listitem"]')];
  return {
    path: shape(location.pathname), title: document.title.replace(/\(\d+\)/, "(#)").slice(0, 40),
    visibility: document.visibilityState, secondsSinceLoad: Math.round(performance.now() / 1000), width: w,
    anchorsT: document.querySelectorAll('a[href*="/t/"]').length,
    anchorsMessages: document.querySelectorAll('a[href*="/messages/"]').length,
    links: document.querySelectorAll("a[href]").length, iframes: document.querySelectorAll("iframe").length,
    grids: document.querySelectorAll('[role="grid"], [role="list"], [role="navigation"]').length,
    rows: rows.length, listRows: listRows().length, visualRows: visualRows().length,
    visualSamples: visualRows().slice(0, 4).map((el) => ({ tag: el.tagName, role: el.getAttribute("role") || "-", tabindex: el.getAttribute("tabindex") || "-", lines: linesOf(el).length, h: Math.round(el.getBoundingClientRect().height), clickable: !!el.closest('a, [role="link"], [role="button"], [tabindex]') })),
    anchorSamples: anchors.slice(0, 4).map(sample), rowSamples: rows.slice(0, 8).map(sample),
  };
}

// Messenger のページにいるか（パスキー案内やホームに飛ばされていないか）
const onMessages = () => location.protocol === "file:" /* 練習用の画面 */ || /^\/(messages|t)(\/|$)/.test(location.pathname) || /messenger\.com$/.test(location.hostname);

function scrape() {
  const at = Date.now();
  if (isLoginPage()) return ipcRenderer.send("msgr-result", { at, status: "login", url: location.href, convos: [] });
  if (!onMessages()) return ipcRenderer.send("msgr-result", { at, status: "away", url: location.href, convos: [] });
  const anchors = [...document.querySelectorAll('a[href*="/t/"]')];
  const seen = new Set(), convos = [];
  const push = (r) => { if (r && !seen.has(r.id) && convos.length < 30) { seen.add(r.id); convos.push(r); } };
  anchors.forEach((a) => push(readItem(a, a.getAttribute("href"))));
  // リンクで1件も取れないときは、一覧の行から読む
  if (!convos.length) listRows().forEach((r) => { const a = r.querySelector('a[href*="/t/"]'); push(readItem(r, a ? a.getAttribute("href") : "")); });
  // それでも取れないときは、見た目の形で探す
  if (!convos.length) visualRows().forEach((r) => { const a = r.querySelector('a[href*="/t/"]') || r.closest('a[href*="/t/"]'); push(readItem(r, a ? a.getAttribute("href") : "")); });
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
  // 吹き出しに目印（role=row）が無い作りのときは、見た目の位置で読む:
  // 画面の右側（会話欄）にある文字のかたまりを上から順に、中央より右なら自分、左なら相手
  if (!out.length) {
    const w = window.innerWidth || 1200, h = window.innerHeight || 900;
    const left = main === document.body ? w * 0.35 : mrect.left;
    const center = main === document.body ? left + (w - left) / 2 : mid;
    const blocks = [...document.querySelectorAll('div[dir="auto"], span[dir="auto"]')].filter((el) => {
      if (el.closest('[contenteditable="true"], [role="textbox"], [role="navigation"], [role="banner"]')) return false;
      if (el.querySelector('div[dir="auto"], span[dir="auto"]')) return false; // いちばん内側だけ
      const b = el.getBoundingClientRect();
      return b.width > 0 && b.height > 0 && b.left >= left && b.top > 140 && b.bottom < h - 60;
    }).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    for (const el of blocks) {
      const text = el.innerText.trim();
      if (!text || /^(\d{1,2}:\d{2}|\d+月\d+日.*|今日|昨日|既読|送信済み|Seen|Sent)$/.test(text)) continue;
      const b = el.getBoundingClientRect();
      const mine = b.left + b.width / 2 > center;
      const prev = out[out.length - 1];
      if (prev && prev.text === text) continue;
      out.push({ mine, text });
    }
  }
  const name = (document.querySelector('[role="main"] h1, [role="main"] h2, h1, h2') || {}).innerText || "";
  return { name: name.trim(), messages: out.slice(-12), rows: rows.length };
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let readingThread = false;
ipcRenderer.on("read-thread", async (_e, { href, name, reqId }) => {
  readingThread = true;
  const back = location.href;
  try {
    // 会話のリンクを押して開く（ページを読み込み直すより速く、ログイン状態も崩れない）
    const path = new URL(href).pathname;
    const link = /\/t\//.test(path) && [...document.querySelectorAll('a[href*="/t/"]')].find((a) => (a.getAttribute("href") || "").startsWith(path) || href.includes(a.getAttribute("href")));
    // リンクの無い作りでは、名前が一致する一覧の行を押す
    // 「オンライン中」などを外したあとの名前で一覧の行を探す
    const row = !link && name && [...listRows(), ...visualRows()].find((r) => { const it = readItem(r, ""); return it && it.name === name; });
    const target = link || (row && (row.closest('a, [role="link"], [role="button"], [tabindex="0"]') || row.querySelector('[role="link"], [role="button"], [tabindex="0"]') || row));
    if (target) target.click();
    else if (/\/t\//.test(path)) { history.pushState({}, "", path); window.dispatchEvent(new PopStateEvent("popstate")); }
    else throw new Error("一覧に " + (name ? "その名前の" : "") + "会話が見つかりませんでした");
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
  // 読み込みが遅いことがあるので、最初は何度か読む
  setTimeout(scrape, 5000);
  setTimeout(scrape, 15000);
  setTimeout(scrape, 30000);
  setInterval(scrape, 60 * 1000);
});
ipcRenderer.on("scrape-now", scrape);
