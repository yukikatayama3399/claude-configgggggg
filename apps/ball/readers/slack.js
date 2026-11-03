// Slack 読み取り係（透明な裏ウィンドウの preload）。
// BALL の中で Slack にログインした画面（app.slack.com）の中から、Slack のウェブ版が使っている API を呼んで読む。
// 読むのは: 自分宛てのメンション（直近7日）と、相手の発言で止まっている DM。
// 書き込みは chat.postMessage の1か所だけで、片山さんが BALL 本体で「この内容で送信」を押したときにしか呼ばれない。
const { ipcRenderer } = require("electron");

const DONE_RE = /^(white_check_mark|heavy_check_mark|ballot_box_with_check|done|kanryo|kanryou|sumi|zumi|済|完了|finish|finished|ok_done)/i;
const ACK_RE = /^(\+1|thumbsup|ok|ok_hand|pray|eyes|bow|raised_hands|ryoukai|shouchi|kakunin|roger|承知|了解|確認)/i;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ログイン情報（Slack ウェブ版が localStorage に置いているもの）から、試す候補を作る。
// Enterprise Grid（FreakOut Group など）だと、組織全体とワークスペースの両方が入っているので、全部を順に試す
function configs() {
  try {
    const c = JSON.parse(localStorage.getItem("localConfig_v2") || "null");
    if (!c || !c.teams) return [];
    const ids = Object.keys(c.teams);
    ids.sort((x, y) => (x === c.lastActiveTeamId ? -1 : y === c.lastActiveTeamId ? 1 : 0));
    return ids.map((id) => ({ teamId: id, t: c.teams[id] })).filter((x) => x.t && x.t.token).map(({ teamId, t }) => ({
      teamId, token: t.token, url: (t.url || "https://slack.com/").replace(/\/?$/, "/"), userId: t.user_id, name: t.name || "", enterprise: t.enterprise_id || "",
    }));
  } catch (e) { return []; }
}
let chosen = null; // 読めた組み合わせ（ワークスペースと取り先）を覚えておく
function config() { return chosen || configs()[0] || null; }
// 取り先のアドレスは、ワークスペースのアドレス → app.slack.com → slack.com の順に試す
function hostsOf(cfg) { return [...new Set([cfg.host, cfg.url, location.origin + "/", "https://app.slack.com/", "https://slack.com/"].filter((h) => h && /^https?:/.test(h)))]; }
async function api(cfg, method, params = {}) {
  let lastErr = null;
  for (const host of hostsOf(cfg)) {
    const fd = new FormData();
    fd.append("token", cfg.token);
    Object.entries(params).forEach(([k, v]) => v != null && fd.append(k, String(v)));
    let j;
    try {
      const r = await fetch(host + "api/" + method, { method: "POST", body: fd, credentials: "include" });
      j = await r.json();
    } catch (e) { lastErr = new Error(`${method}: 通信できませんでした（${host.replace(/^https?:\/\//, "").replace(/\/$/, "")}）`); continue; }
    if (j.ok) { cfg.host = host; return j; }
    lastErr = new Error(method + ": " + (j.error || "error"));
    // 認証まわりのエラーは別の取り先なら通ることがあるので次を試す。それ以外はその場で止める
    if (!/invalid_auth|not_authed|not_allowed_token_type|team_access_not_granted|enterprise_is_restricted|account_inactive/.test(j.error || "")) throw lastErr;
  }
  throw lastErr || new Error(method + ": error");
}

// 速度制限などで落ちたら、少し待って同じ取り先で取り直す
async function apiRetry(cfg, method, params, waits = [1500, 5000, 12000]) {
  for (let k = 0; ; k++) {
    try { return await api(cfg, method, params); }
    catch (e) { if (k >= waits.length || /invalid_auth|not_authed|token_revoked|missing_scope/.test(e.message)) throw e; await sleep(waits[k]); }
  }
}
// DM・グループ DM の一覧。conversations.list → users.conversations の順に試す
async function listDMs(cfg) {
  const errs = [];
  for (const method of ["conversations.list", "users.conversations"]) {
    try {
      const ims = [];
      let cursor = "";
      for (let page = 0; page < 3; page++) {
        const r = await apiRetry(cfg, method, { types: "im,mpim", exclude_archived: true, limit: 200, cursor });
        ims.push(...(r.channels || []));
        cursor = r.response_metadata && r.response_metadata.next_cursor;
        if (!cursor) break;
        await sleep(400);
      }
      return ims;
    } catch (e) { errs.push(String(e.message || e)); }
  }
  throw new Error(errs.join(" / "));
}

// 相手の最後の一言が「締め」（お礼・了解・見てみます など）で、質問もお願いも無ければ、返事は要らないとみなす
const CLOSING_RE = /(ありがと|有難|有り難|承知|了解|りょうかい|かしこまり|助かり|確認しました|見てみます|拝見します|おつかれ|お疲れ|thanks|thank you|\bthx\b|\bok\b|おけ|👍|🙏)/i;
const ASKING_RE = /[?？]|お願い|ください|下さい|いただけ|頂け|もらえ|でしょうか|ますか|ませんか|どう(なり|です|でしょ)|いつ|教えて/;
function isClosing(text) {
  const t = String(text || "").replace(/:[a-z0-9_+-]+:/gi, "").replace(/\s+/g, " ").trim();
  return t.length <= 40 && CLOSING_RE.test(t) && !ASKING_RE.test(t);
}
// 検索で DM を拾う（DM の一覧が取れない Slack 用）: 自分宛ての DM（to:me）を直近 30 日で探し、
// DM ごとに直近のやり取りを読んで、相手の発言で止まっているものだけ返す。
// 直近のやり取りが読めないときは、自分の発言（from:me・最大 400 件）と突き合わせる
async function dmsBySearch(cfg, already) {
  const since = new Date(Date.now() - 30 * 86400e3 + 9 * 3600e3).toISOString().slice(0, 10);
  const find = async (query, page = 1) => {
    const r = await api(cfg, "search.messages", { query: `${query} after:${since}`, count: 100, page, sort: "timestamp", sort_dir: "desc" });
    return { list: (r.messages && r.messages.matches) || [], pages: (r.messages && r.messages.paging && r.messages.paging.pages) || 1 };
  };
  const toMe = (await find("to:me")).list;
  const theirLast = new Map();
  for (const m of toMe) {
    const ch = m.channel || {};
    if (!ch.id || !(ch.is_im || ch.is_mpim) || m.user === cfg.userId) continue;
    if (!theirLast.has(ch.id) || parseFloat(m.ts) > parseFloat(theirLast.get(ch.id).ts)) theirLast.set(ch.id, m);
  }
  let myLast = null; // 必要になったときだけ読む
  const loadMine = async () => {
    myLast = new Map();
    for (let page = 1; page <= 4; page++) {
      let r; try { r = await find("from:me", page); } catch (e) { break; }
      for (const m of r.list) { const ch = (m.channel || {}).id; if (ch && !(parseFloat(myLast.get(ch) || 0) >= parseFloat(m.ts))) myLast.set(ch, m.ts); }
      if (page >= r.pages || r.list.length < 100) break;
      await sleep(400);
    }
  };
  const out = [];
  const cands = [...theirLast.entries()].sort((x, y) => parseFloat(y[1].ts) - parseFloat(x[1].ts)).slice(0, 30);
  for (const [chId, hit] of cands) {
    if (already.some((x) => x.channel === chId)) continue;
    let last = hit;
    try {
      // 直近のやり取り（スタンプ込み）。最後が自分なら返信済み
      const h = await api(cfg, "conversations.history", { channel: chId, limit: 5 });
      const msgs = (h.messages || []).filter((x) => !x.subtype || x.subtype === "file_share" || x.subtype === "thread_broadcast");
      if (msgs.length) {
        if (msgs[0].user === cfg.userId) continue;
        last = msgs[0];
      }
    } catch (e) {
      if (!myLast) await loadMine();
      if (parseFloat(myLast.get(chId) || 0) > parseFloat(hit.ts)) continue;
    }
    if (!last.user || last.bot_id) continue;
    const st = stateOf(cfg, last, false);
    if (st.state === "done") continue;
    if (st.state === "open" && isClosing(last.text)) continue; // 「ありがとうございます！」などの締めは返事不要
    const ch = hit.channel;
    let text = await plain(cfg, last.text);
    if (!text.trim() && (last.files || []).length) text = "📎 " + last.files.map((f) => f.name || f.title || "ファイル").join(", ");
    out.push({ kind: "dm", channel: chId, channelName: ch.is_mpim ? (ch.name || "グループDM") : "", ts: last.ts, threadTs: last.thread_ts || "",
      user: last.user, userName: hit.username || (await userName(cfg, last.user)), text: text || "（スタンプ・ファイル）", permalink: hit.permalink || "",
      state: st.state, emoji: st.emoji, unsureEmoji: !!st.unsure, at: Math.round(parseFloat(last.ts) * 1000) });
    await sleep(150);
  }
  return out;
}

const users = new Map();
const avatars = new Map(); // 人 → アイコンの画像（avatars.slack-edge.com。ログイン無しで見られる）
async function userName(cfg, id) {
  if (!id) return "";
  if (users.has(id)) return users.get(id);
  try {
    const j = await api(cfg, "users.info", { user: id });
    const p = j.user.profile || {};
    const n = p.display_name || p.real_name || j.user.real_name || j.user.name || id;
    users.set(id, n); avatars.set(id, p.image_72 || p.image_48 || ""); return n;
  } catch (e) { users.set(id, id); return id; }
}
// Slack の書式（<@U123>、<url|ラベル>、&amp; など）を読みやすい文字に直す
async function plain(cfg, text) {
  let t = String(text || "");
  const ids = [...new Set([...t.matchAll(/<@([UW][A-Z0-9]+)>/g)].map((m) => m[1]))];
  for (const id of ids) t = t.split(`<@${id}>`).join("@" + (await userName(cfg, id)));
  return t.replace(/<mailto:[^|>]+\|([^>]+)>/g, "$1").replace(/<mailto:([^>]+)>/g, "$1").replace(/<tel:[^|>]+\|([^>]+)>/g, "$1")
    .replace(/<!subteam\^[A-Z0-9]+\|([^>]+)>/g, "$1").replace(/<!subteam\^[A-Z0-9]+>/g, "@グループ")
    .replace(/<#[A-Z0-9]+\|([^>]+)>/g, "#$1").replace(/<#[A-Z0-9]+>/g, "#チャンネル").replace(/<(https?:[^|>]+)\|([^>]+)>/g, (m, u, l) => (l === u ? u : `[${l.replace(/[\[\]]/g, "")}](${u})`)).replace(/<(https?:[^>]+)>/g, "$1")
    .replace(/<!(here|channel|everyone)>/g, "@$1").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}
// 自分の反応（返信・スタンプ）からボールの状態を決める: done（閉じる）/ ack（了解済み・作業は残る）/ open
function stateOf(cfg, msg, laterMine) {
  if (laterMine) return { state: "done", emoji: "" };
  const mine = (msg.reactions || []).filter((r) => (r.users || []).includes(cfg.userId)).map((r) => r.name);
  if (mine.some((n) => DONE_RE.test(n))) return { state: "done", emoji: mine.find((n) => DONE_RE.test(n)) };
  if (mine.length) return { state: "ack", emoji: mine[0], unsure: !mine.some((n) => ACK_RE.test(n)) };
  return { state: "open", emoji: "" };
}

async function pickConfig() {
  if (chosen) return chosen;
  const tried = [];
  for (const cfg of configs()) {
    try {
      const a = await api(cfg, "auth.test");
      cfg.userId = a.user_id || cfg.userId;
      // 検索が使えるかも確かめる（Enterprise Grid では使えないワークスペースがある）
      await api(cfg, "search.messages", { query: "a", count: 1 });
      chosen = cfg; return cfg;
    } catch (e) { tried.push(`${cfg.name || cfg.teamId}: ${e.message}`); }
  }
  const err = new Error(tried.length ? tried.join(" / ") : "ログイン情報が見つかりません");
  err.tried = tried; throw err;
}

async function scan() {
  const at = Date.now();
  if (!configs().length) return ipcRenderer.send("slack-result", { at, status: "login", items: [] });
  let cfg;
  try { cfg = await pickConfig(); }
  catch (err) { return ipcRenderer.send("slack-result", { at, status: /invalid_auth|not_authed|token_revoked|見つかりません/.test(err.message) ? "login" : "error", error: err.message.slice(0, 400), items: [] }); }
  try {
    const since = new Date(Date.now() - 7 * 86400e3 + 9 * 3600e3).toISOString().slice(0, 10);
    const out = [];
    // 1) 自分宛てのメンション
    const s = await api(cfg, "search.messages", { query: `<@${cfg.userId}> after:${since}`, count: 40, sort: "timestamp", sort_dir: "desc" });
    const matches = (s.messages && s.messages.matches) || [];
    for (const m of matches.slice(0, 40)) {
      if (m.user === cfg.userId) continue;
      const ch = m.channel || {};
      const threadTs = (m.permalink && (m.permalink.match(/thread_ts=([\d.]+)/) || [])[1]) || m.thread_ts || m.ts;
      let msg = m, laterMine = false;
      try {
        const r = await api(cfg, "conversations.replies", { channel: ch.id, ts: threadTs, limit: 200 });
        const list = r.messages || [];
        msg = list.find((x) => x.ts === m.ts) || m;
        laterMine = list.some((x) => x.user === cfg.userId && parseFloat(x.ts) > parseFloat(m.ts));
        // 他の人が ✅ を付けて片付いていれば閉じる
        if (!laterMine && (msg.reactions || []).some((r) => DONE_RE.test(r.name) && (r.users || []).some((u) => u !== m.user))) laterMine = true;
      } catch (e) { /* スレッドが読めなくても一覧には出す */ }
      const st = stateOf(cfg, msg, laterMine);
      if (st.state === "done") continue;
      out.push({ kind: ch.is_im || ch.is_mpim ? "dm" : "mention", channel: ch.id, channelName: ch.name || "", ts: m.ts, threadTs,
        user: m.user, userName: m.username || (await userName(cfg, m.user)), text: await plain(cfg, m.text), permalink: m.permalink || "",
        state: st.state, emoji: st.emoji, unsureEmoji: !!st.unsure, at: Math.round(parseFloat(m.ts) * 1000) });
    }
    // 2) DM で相手の発言で止まっているもの（最近動いた DM から順に）
    // DM の一覧は Enterprise Grid だと速度制限で弾かれやすい（弾かれた応答はブラウザからは「通信できない」に見える）。
    // 時間を置いて取り直し、だめなら別の API で取る。それでも取れなければメンションだけ出して、注意書きを付ける
    let warn = "";
    let listErr = "";
    const ims = await listDMs(cfg).catch((e) => { listErr = String(e.message || e).slice(0, 160); return []; });
    // DM の一覧が取れない Slack（Enterprise Grid でブラウザから呼べない場合など）は、検索で拾う
    if (listErr) {
      try { out.push(...(await dmsBySearch(cfg, out))); }
      catch (e) { warn = `DM を読めませんでした（一覧: ${listErr} / 検索: ${String(e.message || e).slice(0, 120)}）。メンションだけ出しています`; }
    }
    ims.sort((a, b) => (b.updated || b.created || 0) - (a.updated || a.created || 0));
    for (const im of ims.slice(0, 25)) {
      try {
        const h = await api(cfg, "conversations.history", { channel: im.id, limit: 1 });
        const last = (h.messages || [])[0];
        if (!last || last.user === cfg.userId || last.bot_id || last.subtype) continue;
        if (Date.now() - parseFloat(last.ts) * 1000 > 30 * 86400e3) continue;
        if (out.some((x) => x.channel === im.id && x.ts === last.ts)) continue;
        const st = stateOf(cfg, last, false);
        if (st.state === "done") continue;
        if (st.state === "open" && isClosing(last.text)) continue;
        out.push({ kind: "dm", channel: im.id, channelName: im.is_mpim ? (im.name || "グループDM") : "", ts: last.ts, threadTs: last.thread_ts || "",
          user: last.user, userName: await userName(cfg, last.user || im.user), text: await plain(cfg, last.text), permalink: "",
          state: st.state, emoji: st.emoji, unsureEmoji: !!st.unsure, at: Math.round(parseFloat(last.ts) * 1000) });
        await sleep(120);
      } catch (e) { /* 読めない DM は飛ばす */ }
    }
    ipcRenderer.send("slack-result", { at, status: "ok", team: cfg.name, items: out, warn });
  } catch (err) {
    const msg = String(err && err.message || err);
    if (/invalid_auth|not_authed|token_revoked/.test(msg)) chosen = null; // ログインし直したときに選び直す
    ipcRenderer.send("slack-result", { at, status: /invalid_auth|not_authed|token_revoked/.test(msg) ? "login" : "error", error: msg.slice(0, 400), items: [] });
  }
}

// スレッド（またはスレッドの無い DM の直近）を読む
ipcRenderer.on("slack-thread", async (_e, { channel, threadTs, reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-thread-result", { reqId, ok: false, error: "Slack にログインしていません" });
  try {
    const r = threadTs ? await api(cfg, "conversations.replies", { channel, ts: threadTs, limit: 200 })
      : await api(cfg, "conversations.history", { channel, limit: 30 });
    let list = r.messages || [];
    if (!threadTs) list = list.slice().reverse();
    const messages = [], ids = new Set();
    for (const m of list) {
      if (m.user && m.user !== cfg.userId) ids.add(m.user);
      for (const x of String(m.text || "").matchAll(/<@([UW][A-Z0-9]+)(?:\|[^>]*)?>/g)) if (x[1] !== cfg.userId) ids.add(x[1]);
      const nm = m.user === cfg.userId ? "自分" : (m.username || (m.user && (await userName(cfg, m.user))) || (m.bot_profile && m.bot_profile.name) || "bot");
      if (m.user === cfg.userId) await userName(cfg, m.user);
      messages.push({ user: m.user, name: nm, mine: m.user === cfg.userId, avatar: avatars.get(m.user) || (m.bot_profile && m.bot_profile.icons && (m.bot_profile.icons.image_72 || m.bot_profile.icons.image_48)) || "",
        ts: m.ts, edited: !!m.edited, text: await plain(cfg, m.text), reactions: (m.reactions || []).map((x) => ({ name: x.name, count: x.count, mine: (x.users || []).includes(cfg.userId) })),
        replyCount: m.reply_count || 0,
        files: (m.files || []).map((f) => ({
          name: f.name || f.title || "ファイル", title: f.title || "", url: f.permalink || f.url_private || "", download: f.url_private || "", mimetype: f.mimetype || "",
          filetype: f.filetype || "", pretty: f.pretty_type || "", size: f.size || 0, w: f.original_w || 0, h: f.original_h || 0,
          thumb: f.thumb_720 || f.thumb_480 || f.thumb_360 || f.thumb_pdf || f.thumb_video || (/^image\//.test(f.mimetype || "") ? f.url_private : "") || "",
        })) });
    }
    const people = [];
    for (const id of ids) people.push({ id, name: await userName(cfg, id) });
    // 使われているカスタム絵文字（本文の :name: とリアクション）だけ渡す
    const all = await customEmoji(cfg), emoji = {};
    for (const m of messages) {
      for (const x of String(m.text).matchAll(/:([a-z0-9_+'-]+):/gi)) { const u = emojiOf(all, x[1]); if (u) emoji[x[1]] = u; }
      for (const r of m.reactions) { const u = emojiOf(all, r.name); if (u) emoji[r.name] = u; }
    }
    ipcRenderer.send("slack-thread-result", { reqId, ok: true, messages, people, emoji, selfName: users.get(cfg.userId) || "", teamUrl: cfg.url });
  } catch (err) { ipcRenderer.send("slack-thread-result", { reqId, ok: false, error: String(err.message || err) }); }
});

// ワークスペースのカスタム絵文字（名前 → 画像）。1回だけ読む。別名（alias:xxx）はたどる
let emojiAll = null;
async function customEmoji(cfg) {
  if (emojiAll) return emojiAll;
  try { const r = await api(cfg, "emoji.list", {}); emojiAll = r.emoji || {}; } catch (e) { emojiAll = {}; }
  return emojiAll;
}
function emojiOf(all, name, depth = 0) {
  const v = all[name];
  if (!v || depth > 3) return "";
  return /^alias:/.test(v) ? emojiOf(all, v.slice(6), depth + 1) : v;
}

// メンションの候補: チャンネルのメンバー（最大 300 人。名前は覚えておいて2回目からは速い）
const peopleCache = new Map();
ipcRenderer.on("slack-people", async (_e, { channel, reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-people-result", { reqId, ok: false, error: "Slack にログインしていません" });
  try {
    if (!peopleCache.has(channel)) {
      const ids = [];
      let cursor = "";
      for (let page = 0; page < 3; page++) {
        const r = await api(cfg, "conversations.members", { channel, limit: 100, cursor });
        ids.push(...(r.members || []));
        cursor = r.response_metadata && r.response_metadata.next_cursor;
        if (!cursor) break;
      }
      const people = [];
      const todo = ids.filter((id) => id !== cfg.userId);
      for (let k = 0; k < todo.length; k += 5) {
        const part = await Promise.all(todo.slice(k, k + 5).map(async (id) => ({ id, name: await userName(cfg, id) })));
        people.push(...part.filter((x) => x.name && x.name !== x.id));
      }
      peopleCache.set(channel, people);
    }
    ipcRenderer.send("slack-people-result", { reqId, ok: true, people: peopleCache.get(channel) });
  } catch (err) { ipcRenderer.send("slack-people-result", { reqId, ok: false, error: String(err.message || err) }); }
});

// 送信（返信）。BALL 本体が「この内容で送信」を押されたときにだけ送ってくる
// ファイル付きのときは、BALL 本体が先にファイルを上げて（slack-upload-url → 本体がアップロード）、ここで本文と一緒に投稿する
ipcRenderer.on("slack-send", async (_e, { channel, threadTs, text, fileIds, reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-send-result", { reqId, ok: false, error: "Slack にログインしていません" });
  try {
    if (fileIds && fileIds.length) {
      await api(cfg, "files.completeUploadExternal", { files: JSON.stringify(fileIds), channel_id: channel, thread_ts: threadTs || undefined, initial_comment: text || undefined });
      return ipcRenderer.send("slack-send-result", { reqId, ok: true });
    }
    const r = await api(cfg, "chat.postMessage", { channel, text, thread_ts: threadTs || undefined });
    ipcRenderer.send("slack-send-result", { reqId, ok: true, ts: r.ts });
  } catch (err) { ipcRenderer.send("slack-send-result", { reqId, ok: false, error: String(err.message || err) }); }
});

// ファイルを上げる先を Slack に聞く（上げるのは BALL 本体）
ipcRenderer.on("slack-upload-url", async (_e, { filename, length, reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-upload-url-result", { reqId, ok: false, error: "Slack にログインしていません" });
  try {
    const r = await api(cfg, "files.getUploadURLExternal", { filename, length });
    ipcRenderer.send("slack-upload-url-result", { reqId, ok: true, uploadUrl: r.upload_url, fileId: r.file_id, token: cfg.token });
  } catch (err) { ipcRenderer.send("slack-upload-url-result", { reqId, ok: false, error: String(err.message || err) }); }
});
// スタンプを付ける・外す（片山さんが BALL 本体で押したときだけ届く）
ipcRenderer.on("slack-react", async (_e, { channel, ts, name, remove, reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-react-result", { reqId, ok: false, error: "Slack にログインしていません" });
  try {
    await api(cfg, remove ? "reactions.remove" : "reactions.add", { channel, timestamp: ts, name });
    ipcRenderer.send("slack-react-result", { reqId, ok: true });
  } catch (err) {
    const msg = String(err.message || err);
    if (/already_reacted|no_reaction/.test(msg)) return ipcRenderer.send("slack-react-result", { reqId, ok: true });
    ipcRenderer.send("slack-react-result", { reqId, ok: false, error: msg });
  }
});
// 絵文字を選ぶ小窓用: カスタム絵文字の全部（別名はたどった画像）
ipcRenderer.on("slack-emoji-all", async (_e, { reqId }) => {
  const cfg = config();
  if (!cfg) return ipcRenderer.send("slack-emoji-all-result", { reqId, ok: false });
  const all = await customEmoji(cfg), out = {};
  for (const n of Object.keys(all)) { const u = emojiOf(all, n); if (u) out[n] = u; }
  ipcRenderer.send("slack-emoji-all-result", { reqId, ok: true, emoji: out });
});

ipcRenderer.on("slack-scan-now", scan);
window.addEventListener("DOMContentLoaded", () => {
  setTimeout(scan, 6000);
  setInterval(scan, 2 * 60 * 1000);
});
