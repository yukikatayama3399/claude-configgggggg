// HAWK トライアル（配信設計のみ）の簡易サーバー。依存パッケージなし（Node.js 20 以降）。
//
// 入口の流れ:
//   1) 来場者が URL を開く → 「デモアカウントを申し込む」（会社名・氏名・メール）
//   2) 申込は data/store.json に保存し、決まった Slack チャンネル（Incoming Webhook）に通知（設定したときだけ）
//   3) 担当者が管理画面（/admin）で「招待リンクを発行」→ 招待メールは Gmail の下書きまで（送信は担当者が自分で押す）
//   4) 来場者は招待リンクからサインアップ（パスワード設定＋簡易利用規約・メールアドレス取得への同意）
//   5) ログイン後だけ /app（トライアル画面）と AI 読み取り（/api/extract）が使える
//
// 送信の決まり（リポジトリ直下 CLAUDE.md「送信の絶対ルール」）:
//   このサーバーは来場者にメールを自動送信しない。Slack は決まったチャンネルへの通知だけ。
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFile } = require("child_process");
const ai = require("./ai");
const pages = require("./pages");

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || "127.0.0.1";
const PUBLIC_URL = (process.env.HAWK_TRIAL_PUBLIC_URL || `http://localhost:${PORT}`).replace(/\/$/, "");
const DATA_DIR = process.env.HAWK_TRIAL_DATA || path.join(__dirname, "data");
const STORE = path.join(DATA_DIR, "store.json");
const SLACK_WEBHOOK = process.env.HAWK_TRIAL_SLACK_WEBHOOK || "";
const GOG_ACCOUNT = process.env.HAWK_TRIAL_GOG_ACCOUNT || "";
const TRIAL_DAYS = Number(process.env.HAWK_TRIAL_DAYS || 14);
const OFFER_DEADLINE = process.env.HAWK_TRIAL_OFFER_DEADLINE || ""; // 例 2026-12-04。空なら「トライアル終了日」
const COUPON = process.env.HAWK_TRIAL_COUPON || "HAWK-1MONTH-FREE";
const EXTRACT_PER_DAY = Number(process.env.HAWK_TRIAL_EXTRACT_PER_DAY || 30);
const TERMS_VERSION = pages.TERMS_VERSION;
const SECURE = PUBLIC_URL.startsWith("https://");

// ---------- 保存（1ファイルの JSON。トライアル規模ならこれで足りる） ----------
fs.mkdirSync(DATA_DIR, { recursive: true });
let db = { requests: [], users: [], sessions: {}, usage: {} };
try { db = { ...db, ...JSON.parse(fs.readFileSync(STORE, "utf8")) }; } catch (e) { /* 初回 */ }
const save = () => { const tmp = STORE + ".tmp"; fs.writeFileSync(tmp, JSON.stringify(db, null, 1)); fs.renameSync(tmp, STORE); };
const ADMIN_KEY = process.env.HAWK_TRIAL_ADMIN_KEY || (() => {
  const f = path.join(DATA_DIR, "admin_key");
  try { return fs.readFileSync(f, "utf8").trim(); } catch (e) { const k = crypto.randomBytes(18).toString("base64url"); fs.writeFileSync(f, k, { mode: 0o600 }); return k; }
})();

const id = (n = 12) => crypto.randomBytes(n).toString("base64url");
const now = () => new Date().toISOString();
const hash = (pw, salt) => crypto.scryptSync(pw, salt, 32).toString("hex");
const EMAIL_RE = /^[^\s@<>()"',;]+@[^\s@<>()"',;]+\.[^\s@<>()"',;]+$/;
const clean = (s, max = 200) => String(s || "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, max);
const addDays = (iso, d) => new Date(new Date(iso).getTime() + d * 86400000).toISOString();

// ---------- HTTP の小道具 ----------
function send(res, code, body, type = "text/html; charset=utf-8", headers = {}) {
  res.writeHead(code, { "Content-Type": type, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin", ...headers });
  res.end(body);
}
const json = (res, code, obj, headers) => send(res, code, JSON.stringify(obj), "application/json; charset=utf-8", headers);
const redirect = (res, to, headers = {}) => { res.writeHead(302, { Location: to, ...headers }); res.end(); };
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on("data", (c) => { size += c.length; if (size > 200000) { reject(new Error("too large")); req.destroy(); } else chunks.push(c); });
    req.on("end", () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")); } catch (e) { reject(e); } });
    req.on("error", reject);
  });
}
function cookies(req) {
  const out = {};
  for (const p of String(req.headers.cookie || "").split(";")) { const i = p.indexOf("="); if (i > 0) out[p.slice(0, i).trim()] = decodeURIComponent(p.slice(i + 1).trim()); }
  return out;
}
const cookie = (name, val, maxAge) => `${name}=${encodeURIComponent(val)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${SECURE ? "; Secure" : ""}`;
function currentUser(req) {
  const s = db.sessions[cookies(req).hs];
  if (!s || s.exp < Date.now()) return null;
  return db.users.find((u) => u.id === s.userId) || null;
}
const isAdmin = (req) => cookies(req).ha === ADMIN_KEY;
// JSON の POST は同じオリジンからだけ受け付ける（他サイトからの送りつけ防止）
function sameOrigin(req) {
  const o = req.headers.origin;
  if (!o) return true;
  try { const u = new URL(o); return u.host === req.headers.host || o === PUBLIC_URL; } catch (e) { return false; }
}
function trialInfo(u) {
  const ends = u.trialEndsAt;
  const deadline = OFFER_DEADLINE ? new Date(OFFER_DEADLINE + "T23:59:59+09:00").toISOString() : ends;
  return { endsAt: ends, offerDeadline: deadline, coupon: COUPON, daysLeft: Math.max(0, Math.ceil((new Date(ends) - Date.now()) / 86400000)) };
}

// ---------- 通知（決まった Slack チャンネルだけ） ----------
async function notifySlack(text) {
  if (!SLACK_WEBHOOK) return { ok: false, skipped: true };
  try {
    const r = await fetch(SLACK_WEBHOOK, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    return { ok: r.ok };
  } catch (e) { console.error("[slack]", e.message); return { ok: false, error: e.message }; }
}

function inviteMail(r) {
  const link = `${PUBLIC_URL}/signup?invite=${r.inviteToken}`;
  const subject = "【HAWK】トライアルアカウントのご案内";
  const body = `${r.company} ${r.name} 様

このたびは HAWK のトライアルにお申し込みいただき、ありがとうございます。
下記のリンクからアカウントを作成いただくと、すぐにお試しいただけます。

▼ アカウント作成（${r.email} 専用のリンクです）
${link}

トライアルでは、依頼メモの貼り付けから「オーディエンス設計 → 見積り → 配信設計」までをご利用いただけます。
（Meta／TikTok への配信連携は、正式なお申し込み後にご利用いただけます）

ご不明な点がございましたら、このメールにご返信ください。

株式会社フリークアウト HAWK チーム`;
  return { to: r.email, subject, body, link };
}

// 招待メールを Gmail の下書きにする（送らない。--gmail-no-send で送信系は止める）
function gmailDraft(mail) {
  return new Promise((resolve) => {
    if (!GOG_ACCOUNT) return resolve({ ok: false, error: "HAWK_TRIAL_GOG_ACCOUNT が未設定です（下書き機能は使えません）" });
    const args = ["--account", GOG_ACCOUNT, "--gmail-no-send", "--no-input", "-j", "gmail", "drafts", "create", "--to", mail.to, "--subject", mail.subject, "--body", mail.body];
    execFile(process.env.HAWK_TRIAL_GOG || "gog", args, { timeout: 60000 }, (e, out, err) => {
      if (e) return resolve({ ok: false, error: String(err || e.message).slice(0, 300) });
      resolve({ ok: true });
    });
  });
}

// ---------- ルーティング ----------
const APP_HTML = path.join(__dirname, "index.html");
// ロゴ・アイコン（公式ロゴ hawk_logo_col02.png / col01.png から作成）
const STATIC = { "/logo.png": "logo.png", "/favicon.png": "favicon.png", "/apple-touch-icon.png": "apple-touch-icon.png", "/app/logo.png": "logo.png" };

async function handle(req, res) {
  const url = new URL(req.url, "http://x");
  const p = url.pathname;
  const user = currentUser(req);

  if (req.method === "GET") {
    if (STATIC[p]) return send(res, 200, fs.readFileSync(path.join(__dirname, STATIC[p])), "image/png", { "Cache-Control": "public, max-age=86400" });
    if (p === "/") return user ? redirect(res, "/app") : send(res, 200, pages.landing());
    if (p === "/login") return user ? redirect(res, "/app") : send(res, 200, pages.login());
    if (p === "/terms") return send(res, 200, pages.terms());
    if (p === "/logout") {
      delete db.sessions[cookies(req).hs]; save();
      return redirect(res, "/login", { "Set-Cookie": cookie("hs", "", 0) });
    }
    if (p === "/signup") {
      const r = db.requests.find((x) => x.inviteToken && x.inviteToken === url.searchParams.get("invite"));
      if (!r) return send(res, 404, pages.message("招待リンクが見つかりません", "リンクが正しいか、もう一度メールをご確認ください。すでにアカウントを作成済みの場合は <a href=\"/login\">ログイン</a> してください。"));
      if (db.users.some((u) => u.email === r.email)) return redirect(res, "/login");
      return send(res, 200, pages.signup({ email: r.email, name: r.name, company: r.company, token: r.inviteToken }));
    }
    if (p === "/app") {
      if (!user) return redirect(res, "/login");
      return send(res, 200, fs.readFileSync(APP_HTML));
    }
    if (p === "/api/me") {
      if (!user) return json(res, 401, { ok: false });
      const st = await ai.status();
      return json(res, 200, { ok: true, user: { id: user.id, email: user.email, name: user.name, company: user.company }, trial: trialInfo(user), ai: st });
    }
    if (p === "/admin") {
      const key = url.searchParams.get("key");
      if (key && key === ADMIN_KEY) return redirect(res, "/admin", { "Set-Cookie": cookie("ha", ADMIN_KEY, 60 * 60 * 12) });
      if (!isAdmin(req)) return send(res, 403, pages.message("管理画面", "管理用の URL（?key=…）から開いてください。キーはサーバー起動時にターミナルに表示されます。"));
      return send(res, 200, pages.admin({ gog: !!GOG_ACCOUNT, slack: !!SLACK_WEBHOOK }));
    }
    if (p === "/api/admin/list") {
      if (!isAdmin(req)) return json(res, 403, { ok: false });
      return json(res, 200, { ok: true, requests: db.requests, users: db.users.map(({ passHash, salt, ...u }) => ({ ...u, usage: db.usage[u.id] || {} })) });
    }
    return send(res, 404, pages.message("ページが見つかりません", "<a href=\"/\">トップへ戻る</a>"));
  }

  if (req.method !== "POST") return send(res, 405, "method not allowed", "text/plain");
  if (!sameOrigin(req)) return json(res, 403, { ok: false, error: "origin" });
  let body;
  try { body = await readBody(req); } catch (e) { return json(res, 400, { ok: false, error: "入力を読み取れませんでした" }); }

  // 1) デモアカウントの申込
  if (p === "/api/request") {
    const r = { company: clean(body.company, 100), name: clean(body.name, 60), email: clean(body.email, 120).toLowerCase(), note: clean(body.note, 500), source: clean(body.source, 60) };
    if (!r.company || !r.name || !EMAIL_RE.test(r.email)) return json(res, 400, { ok: false, error: "会社名・お名前・メールアドレスを正しく入力してください" });
    if (!body.agree) return json(res, 400, { ok: false, error: "個人情報の取り扱いへの同意が必要です" });
    if (db.users.some((u) => u.email === r.email)) return json(res, 200, { ok: true, already: true });
    const dup = db.requests.find((x) => x.email === r.email);
    if (dup) return json(res, 200, { ok: true });
    const rec = { id: id(8), ...r, createdAt: now(), status: "pending", inviteToken: "", invitedAt: "", privacyAgreedAt: now() };
    db.requests.unshift(rec); save();
    notifySlack(`:hawk: *HAWK トライアル申込*\n${rec.company} / ${rec.name}\n${rec.email}${rec.source ? `\n経路: ${rec.source}` : ""}${rec.note ? `\nメモ: ${rec.note}` : ""}\n→ 管理画面で招待: ${PUBLIC_URL}/admin`);
    return json(res, 200, { ok: true });
  }

  // 2) サインアップ（招待リンク経由のみ）
  if (p === "/api/signup") {
    const r = db.requests.find((x) => x.inviteToken && x.inviteToken === body.token);
    if (!r) return json(res, 400, { ok: false, error: "招待リンクが無効です" });
    if (db.users.some((u) => u.email === r.email)) return json(res, 400, { ok: false, error: "このメールアドレスは登録済みです。ログインしてください" });
    const pw = String(body.password || "");
    if (pw.length < 8) return json(res, 400, { ok: false, error: "パスワードは8文字以上にしてください" });
    if (!body.agreeTerms || !body.agreeEmail) return json(res, 400, { ok: false, error: "利用規約とメールアドレスの取り扱いへの同意が必要です" });
    const salt = id(12);
    const u = { id: id(8), email: r.email, name: clean(body.name, 60) || r.name, company: clean(body.company, 100) || r.company,
      salt, passHash: hash(pw, salt), createdAt: now(), trialEndsAt: addDays(now(), TRIAL_DAYS),
      consent: { termsVersion: TERMS_VERSION, termsAt: now(), emailUseAt: now(), marketing: !!body.marketing } };
    db.users.push(u);
    r.status = "signed_up"; r.signedUpAt = now();
    const tok = id(24);
    db.sessions[tok] = { userId: u.id, exp: Date.now() + 30 * 86400000 };
    save();
    notifySlack(`:white_check_mark: *HAWK トライアル登録完了* ${u.company} / ${u.name}（${u.email}）`);
    return json(res, 200, { ok: true }, { "Set-Cookie": cookie("hs", tok, 30 * 86400) });
  }

  // 3) ログイン
  if (p === "/api/login") {
    const email = clean(body.email, 120).toLowerCase();
    const u = db.users.find((x) => x.email === email);
    if (!u || hash(String(body.password || ""), u.salt) !== u.passHash) return json(res, 400, { ok: false, error: "メールアドレスかパスワードが違います" });
    const tok = id(24);
    db.sessions[tok] = { userId: u.id, exp: Date.now() + 30 * 86400000 };
    for (const [k, s] of Object.entries(db.sessions)) if (s.exp < Date.now()) delete db.sessions[k];
    save();
    return json(res, 200, { ok: true }, { "Set-Cookie": cookie("hs", tok, 30 * 86400) });
  }

  // 4) AI 読み取り（ログイン必須・1日の回数上限あり）
  if (p === "/api/extract") {
    if (!user) return json(res, 401, { ok: false, error: "ログインが切れました。もう一度ログインしてください" });
    if (new Date(user.trialEndsAt) < new Date()) return json(res, 403, { ok: false, error: "トライアル期間が終了しました" });
    const day = new Date().toISOString().slice(0, 10);
    const us = (db.usage[user.id] ||= { day, today: 0, total: 0 });
    if (us.day !== day) { us.day = day; us.today = 0; }
    if (us.today >= EXTRACT_PER_DAY) return json(res, 429, { ok: false, error: `本日の AI 読み取り回数の上限（${EXTRACT_PER_DAY}回）に達しました` });
    const notes = (Array.isArray(body.notes) ? body.notes : []).slice(-20).map((n) => ({ at: clean(n.at, 40), text: String(n.text || "").slice(0, 10000) }));
    const r = await ai.extract({ notes, current: body.current && typeof body.current === "object" ? body.current : null, today: body.today });
    if (r.ok) { us.today++; us.total++; save(); }
    return json(res, r.ok ? 200 : 502, r);
  }

  // 管理: 招待リンク発行／Gmail 下書き／取り消し
  if (p.startsWith("/api/admin/")) {
    if (!isAdmin(req)) return json(res, 403, { ok: false });
    const r = db.requests.find((x) => x.id === body.id);
    if (!r) return json(res, 404, { ok: false, error: "申込が見つかりません" });
    if (p === "/api/admin/invite") {
      if (!r.inviteToken) { r.inviteToken = id(18); r.invitedAt = now(); r.status = r.status === "pending" ? "invited" : r.status; save(); }
      return json(res, 200, { ok: true, mail: inviteMail(r) });
    }
    if (p === "/api/admin/draft") {
      if (!r.inviteToken) return json(res, 400, { ok: false, error: "先に招待リンクを発行してください" });
      const d = await gmailDraft(inviteMail(r));
      if (d.ok) { r.draftAt = now(); save(); }
      return json(res, d.ok ? 200 : 500, d);
    }
    if (p === "/api/admin/revoke") { r.inviteToken = ""; r.status = "revoked"; save(); return json(res, 200, { ok: true }); }
  }
  return json(res, 404, { ok: false, error: "not found" });
}

http.createServer((req, res) => {
  handle(req, res).catch((e) => { console.error(e); try { json(res, 500, { ok: false, error: "サーバーエラー" }); } catch (_) { /* 応答済み */ } });
}).listen(PORT, HOST, async () => {
  const st = await ai.status();
  console.log(`HAWK トライアル: ${PUBLIC_URL}/`);
  console.log(`管理画面:        ${PUBLIC_URL}/admin?key=${ADMIN_KEY}`);
  console.log(`AI 読み取り:     ${st.ok ? `claude ${st.version}（${st.model}）` : st.error}`);
  console.log(`Slack 通知:      ${SLACK_WEBHOOK ? "あり" : "なし（HAWK_TRIAL_SLACK_WEBHOOK 未設定。申込は管理画面で確認）"}`);
  console.log(`Gmail 下書き:    ${GOG_ACCOUNT ? GOG_ACCOUNT : "なし（HAWK_TRIAL_GOG_ACCOUNT 未設定。管理画面で文面コピー）"}`);
});
