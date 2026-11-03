// 真ん中の Claude が Bash で叩く gog の門番。BALL が Claude に渡す PATH の先頭に置く「gog」から呼ばれる。
// どう書かれても送信系が動かないように、送信禁止のフラグを必ず付け、
// Claude 側が付けた --disable-commands / --enable-commands / --access-token（BALL の禁止を外せるもの）は取り除く。
const { spawnSync } = require("child_process");

const REAL = process.env.BALL_REAL_GOG;
const BLOCK = "gmail.send,gmail.drafts.send,gmail.reply,gmail.forward,chat.messages.send,chat.send,chat.spaces.messages.send";
const DROP = /^--(disable-commands|enable-commands|access-token)(=|$)/;

const args = [];
const src = process.argv.slice(2);
for (let k = 0; k < src.length; k++) {
  const a = src[k];
  if (DROP.test(a)) { if (!a.includes("=")) k++; continue; }
  if (a === "--gmail-no-send") continue;
  args.push(a);
}
// 自分自身を呼び続けないように: 本物の gog は絶対パスで、門番の置き場所（BALL_GUARD_DIR）以外でなければ呼ばない
const path = require("path");
const GUARD_DIR = process.env.BALL_GUARD_DIR || "";
if (process.env.BALL_GUARD_DEPTH) { console.error("BALL: gog の門番が二重に呼ばれたので止めました"); process.exit(1); }
if (!REAL || !path.isAbsolute(REAL) || (GUARD_DIR && path.resolve(path.dirname(REAL)) === path.resolve(GUARD_DIR))) {
  console.error("BALL: 本物の gog の場所が分かりません"); process.exit(1);
}
const r = spawnSync(REAL, ["--gmail-no-send", "--disable-commands", BLOCK, ...args], { stdio: "inherit", env: { ...process.env, BALL_GUARD_DEPTH: "1" } });
process.exit(r.status == null ? 1 : r.status);
