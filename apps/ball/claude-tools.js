// 真ん中の Claude に渡す道具（MCP サーバー・標準入出力）。
// claude（Claude Code）がこのファイルを子プロセスとして起動する。道具の中身は BALL 本体（main.js）にあり、
// ここは BALL 本体へ 127.0.0.1 の HTTP で取り次ぐだけ。
//
// 絶対ルール: 送信の道具は1つも無い。返信は「下書き欄に入れる」まで。送るのは片山さん本人。
// 権限（BALL_PERM）で出す道具を絞る:
//   read  … 読むだけ（Gmail・カレンダー・Drive・Docs・Sheets を読む）
//   sheet … いつもどおり（＋ 下書き欄・メモ・スプレッドシートに書く）
const http = require("http");

const URL_ = process.env.BALL_TOOLS_URL;
const TOKEN = process.env.BALL_TOOLS_TOKEN;
const PERM = process.env.BALL_PERM || "draft";

const str = (description) => ({ type: "string", description });
const TOOLS = [
  { name: "gmail_search", level: "read", description: "片山さんの Gmail を Gmail の検索式で探す（読み取りのみ）。スレッドの id・日時・差出人・件名を返す。", inputSchema: { type: "object", properties: { query: str("Gmail の検索式。例: from:tanaka@example.com newer_than:30d"), max: { type: "integer", description: "最大件数（既定 10、最大 25）" } }, required: ["query"] } },
  { name: "gmail_read_thread", level: "read", description: "Gmail のスレッドを1つ読む（読み取りのみ）。本文・宛先・添付ファイル名を返す。", inputSchema: { type: "object", properties: { thread_id: str("gmail_search で得たスレッドの id") }, required: ["thread_id"] } },
  { name: "calendar_events", level: "read", description: "片山さんの Google カレンダーの予定を、今日から指定日数ぶん読む（読み取りのみ）。", inputSchema: { type: "object", properties: { days: { type: "integer", description: "何日先まで（既定 7、最大 31）" } } } },
  { name: "drive_search", level: "read", description: "Google Drive を全文検索する（読み取りのみ）。", inputSchema: { type: "object", properties: { query: str("検索する言葉"), max: { type: "integer", description: "最大件数（既定 10）" } }, required: ["query"] } },
  { name: "docs_read", level: "read", description: "Google ドキュメントの本文を読む（読み取りのみ）。", inputSchema: { type: "object", properties: { doc: str("ドキュメントの URL または id") }, required: ["doc"] } },
  { name: "sheets_read", level: "read", description: "スプレッドシートの範囲を読む（読み取りのみ）。", inputSchema: { type: "object", properties: { sheet: str("スプレッドシートの URL または id"), range: str("範囲。例: シート1!A1:F40") }, required: ["sheet", "range"] } },
  { name: "ball_set_draft", level: "draft", description: "このボールの返信の下書き欄に文面を入れる。送信はしない（送るのは片山さんが自分のボタンで行う）。今ある下書きは置き換わる。メールなら宛先・CC も変えられる（省略すると、最後に相手から来たメールへの返信の宛先のまま）。Slack では「@名前」と書けばメンションになる。", inputSchema: { type: "object", properties: { text: str("下書きの本文（宛名から署名まで、そのまま送れる形）"), to: str("メールの宛先（カンマ区切り）。変えるときだけ"), cc: str("メールの CC（カンマ区切り）。変えるときだけ") }, required: ["text"] } },
  { name: "ball_set_memo", level: "draft", description: "このボールのメモ欄に書く。議事録の整理、作業の段取り、調べた結果の控えなどに使う。", inputSchema: { type: "object", properties: { text: str("書く内容"), mode: { type: "string", enum: ["append", "replace"], description: "append（末尾に足す・既定）か replace（置き換える）" } }, required: ["text"] } },
  { name: "sheets_write", level: "sheet", description: "スプレッドシートのセルに値を書く。書く前に、どのシートのどの範囲に何を書くかを本文で片山さんに示すこと。", inputSchema: { type: "object", properties: { sheet: str("スプレッドシートの URL または id"), range: str("範囲。例: シート1!W12:X12"), values: { type: "array", items: { type: "array", items: { type: "string" } }, description: "書く値（行の配列。各行はセルの配列）。例: [[\"済\", \"11/4\"]]" } }, required: ["sheet", "range", "values"] } },
];
const RANK = { read: 0, draft: 1, sheet: 2 };
const visible = () => TOOLS.filter((t) => RANK[t.level] <= (RANK[PERM] ?? 1));

function call(name, args) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ name, args });
    const u = new URL(URL_);
    const req = http.request({ host: u.hostname, port: u.port, path: u.pathname, method: "POST", headers: { "content-type": "application/json", "x-ball-token": TOKEN, "content-length": Buffer.byteLength(body) }, timeout: 180000 }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8"))); } catch (e) { resolve({ ok: false, error: "BALL 本体の応答が読めませんでした" }); } });
    });
    req.on("error", (e) => resolve({ ok: false, error: "BALL 本体につながりません: " + e.message }));
    req.on("timeout", () => { req.destroy(); resolve({ ok: false, error: "時間切れ" }); });
    req.end(body);
  });
}

const send = (msg) => process.stdout.write(JSON.stringify(msg) + "\n");
let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => {
  buf += d;
  let n;
  while ((n = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, n).trim(); buf = buf.slice(n + 1);
    if (line) handle(line);
  }
});
process.stdin.on("end", () => process.exit(0));

async function handle(line) {
  let msg;
  try { msg = JSON.parse(line); } catch (e) { return; }
  const { id, method, params } = msg;
  if (id === undefined) return; // 通知（notifications/initialized など）には返事をしない
  if (method === "initialize") {
    return send({ jsonrpc: "2.0", id, result: { protocolVersion: (params && params.protocolVersion) || "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "ball", version: "1.0.0" } } });
  }
  if (method === "ping") return send({ jsonrpc: "2.0", id, result: {} });
  if (method === "tools/list") return send({ jsonrpc: "2.0", id, result: { tools: visible().map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) } });
  if (method === "tools/call") {
    const name = params && params.name;
    if (!visible().some((t) => t.name === name)) return send({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: `${name} は今の権限では使えません` }], isError: true } });
    const r = await call(name, (params && params.arguments) || {});
    return send({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: r.ok ? String(r.text ?? "OK") : String(r.error || "失敗しました") }], isError: !r.ok } });
  }
  send({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found: " + method } });
}
