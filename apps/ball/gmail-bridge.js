// Gmail の読み書き係（アプリ本体側）。Mac に入っている gog を呼ぶだけ。
// できること: ボール候補の一覧、スレッドの中身、添付ファイルを開く、返信の下書きを保存・更新。
// 送信系のコマンドは呼ばない（念のため常に --gmail-no-send を付ける）。
const { execFile } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const ACCOUNT = process.env.BALL_GOG_ACCOUNT || "yuki.katayama@fout.jp";
const CANDIDATES = [process.env.BALL_GOG, "gog", "/opt/homebrew/bin/gog", "/usr/local/bin/gog", path.join(os.homedir(), "bin", "gog")].filter(Boolean);
let GOG = null;

function run(args, { input, timeout = 60000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = execFile(GOG, ["--account", ACCOUNT, "--gmail-no-send", "--no-input", ...args],
      { timeout, maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
        if (err) return reject(new Error((stderr || err.message).trim().split("\n").slice(-3).join(" ")));
        resolve(stdout);
      });
    if (input != null) { child.stdin.write(input); child.stdin.end(); }
  });
}
const runJson = async (args, opts) => JSON.parse(await run(["-j", ...args], opts));

async function findGog() {
  for (const c of CANDIDATES) {
    try {
      await new Promise((res, rej) => execFile(c, ["--version"], { timeout: 8000 }, (e) => (e ? rej(e) : res())));
      GOG = c; return c;
    } catch (e) { /* 次の候補 */ }
  }
  return null;
}

// ボール候補: 最後のメッセージが自分以外の人から来ている、受信トレイのスレッド
const QUERY = [
  "in:inbox", "newer_than:14d", "-from:me",
  "-category:promotions", "-category:social", "-category:updates", "-category:forums",
  "-label:問い合わせ完了", "-label:カレンダー通知", "-label:メルマガ・通知", "-label:配信不能通知",
].join(" ");
const AUTO_RE = /お問い合わせありがとうございま|自動返信|受け付けました|受付いたしました|noreply|no-reply|do-not-reply/i;
// カレンダーの招待・返答通知はカレンダー側で扱うので除外
const CAL_RE = /^(招待|招待 - 更新|承諾|辞退|参加予定（未定）|予定のキャンセル|Invitation|Updated invitation|Accepted|Declined|Tentative)[:：]/;
const SELF_RE = new RegExp(ACCOUNT.replace(/[.@]/g, (c) => "\\" + c), "i");

async function status() {
  if (!GOG && !(await findGog())) return { ok: false, reason: "nogog" };
  try { await runJson(["gmail", "search", "in:inbox", "--max", "1"], { timeout: 20000 }); return { ok: true }; }
  catch (e) { return { ok: false, reason: "auth", message: e.message }; }
}

async function inbox() {
  const d = await runJson(["gmail", "search", QUERY, "--max", "40"]);
  return (d.threads || [])
    .filter((t) => !SELF_RE.test(t.from || "") && !AUTO_RE.test((t.from || "") + " " + (t.subject || "")) && !CAL_RE.test(t.subject || ""))
    .map((t) => ({ id: t.id, date: t.date, from: t.from, subject: t.subject, unread: (t.labels || []).includes("UNREAD"), count: t.messageCount }));
}

// Gmail API の生データ（payload）から本文・ヘッダ・添付を取り出す
const b64 = (s) => Buffer.from((s || "").replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8");
function walk(part, acc) {
  if (!part) return acc;
  const mime = part.mimeType || "";
  if (part.filename && part.body && part.body.attachmentId) {
    acc.attachments.push({ filename: part.filename, mimeType: mime, size: part.body.size || 0, attachmentId: part.body.attachmentId });
  } else if (mime === "text/plain" && part.body && part.body.data && !acc.text) acc.text = b64(part.body.data);
  else if (mime === "text/html" && part.body && part.body.data && !acc.html) acc.html = b64(part.body.data);
  (part.parts || []).forEach((p) => walk(p, acc));
  return acc;
}
function htmlToText(h) {
  return h.replace(/<style[\s\S]*?<\/style>/gi, "").replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|tr|li|h\d)>/gi, "\n").replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&")
    .replace(/\n{3,}/g, "\n\n").trim();
}
const human = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : n > 1024 ? Math.round(n / 1024) + " KB" : n + " B");

async function thread(id) {
  const d = await runJson(["gmail", "thread", "get", id, "--full"]);
  const msgs = (d.thread && d.thread.messages) || [];
  return {
    id,
    messages: msgs.map((m) => {
      const h = {};
      ((m.payload && m.payload.headers) || []).forEach((x) => { h[x.name.toLowerCase()] = x.value; });
      const acc = walk(m.payload, { text: "", html: "", attachments: [] });
      const body = acc.text || (acc.html ? htmlToText(acc.html) : "") || m.snippet || "";
      return {
        id: m.id, date: h.date || "", from: h.from || "", to: h.to || "", cc: h.cc || "", subject: h.subject || "",
        body, unread: (m.labelIds || []).includes("UNREAD"),
        attachments: acc.attachments.map((a) => ({ ...a, size: human(a.size), messageId: m.id })),
      };
    }),
  };
}

async function openAttachment({ messageId, attachmentId, filename }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ball-att-"));
  const out = path.join(dir, (filename || "attachment").replace(/[\\/:]/g, "_"));
  await run(["gmail", "attachment", messageId, attachmentId, "--out", out]);
  return out;
}

// 返信の下書きを保存。draftId があれば更新、無ければ作成。送信はしない。
async function saveDraft({ draftId, replyToMessageId, to, cc, subject, body }) {
  const args = ["--to", to, "--subject", subject, "--body-file", "-"];
  if (cc) args.push("--cc", cc);
  if (draftId) {
    const r = await runJson(["gmail", "drafts", "update", draftId, ...args], { input: body });
    return { draftId: (r.draft && r.draft.id) || r.id || draftId };
  }
  if (replyToMessageId) args.push("--reply-to-message-id", replyToMessageId);
  const r = await runJson(["gmail", "drafts", "create", ...args], { input: body });
  return { draftId: (r.draft && r.draft.id) || r.draftId || r.draft_id || r.id || null };
}

module.exports = { status, inbox, thread, openAttachment, saveDraft, ACCOUNT };
