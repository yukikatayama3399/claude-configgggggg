#!/bin/bash
# ============================================================
# automode-settings.json の autoMode ブロックを
# ~/.claude/settings.json にマージする。
#
# なぜ ~/.claude/settings.json なのか:
#   auto モードの分類器は autoMode をユーザー設定(~/.claude/settings.json)と
#   managed settings からしか読まない。プロジェクトの .claude/settings.json /
#   .claude/settings.local.json は「リポジトリ側が勝手に自分を信頼させる」のを
#   防ぐため意図的に無視される (Claude Code v2.1.207 以降)。
#   なのでリポジトリに置いた定義を、このスクリプトでユーザー設定へ写す。
#
# 使い方:
#   bash apply_automode_settings.sh          # マージ
#   bash apply_automode_settings.sh --check  # 差分だけ表示して書き込まない
#
# 会社 Mac など永続環境では一度実行すれば足りる。
# クラウド(Claude Code on the web)は毎回コンテナが作り直されるので
# SessionStart フックから自動実行している。
# ============================================================
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/automode-settings.json"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
MODE="${1:-apply}"

if [ ! -f "$SRC" ]; then
  echo "[automode] 定義ファイルが無い: $SRC" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[automode] python3 が無いのでスキップ" >&2
  exit 1
fi

SRC="$SRC" DEST="$DEST" MODE="$MODE" python3 <<'PY'
import json, os, pathlib, sys

src = pathlib.Path(os.environ["SRC"])
dest = pathlib.Path(os.environ["DEST"])
check_only = os.environ["MODE"] == "--check"

fragment = json.loads(src.read_text(encoding="utf-8"))

current = {}
if dest.exists() and dest.stat().st_size > 0:
    try:
        current = json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[automode] {dest} が壊れている ({e}) ので中断", file=sys.stderr)
        sys.exit(1)

if current.get("autoMode") == fragment["autoMode"]:
    print("[automode] 既に最新: 変更なし")
    sys.exit(0)

if check_only:
    print("[automode] 差分あり (--check なので書き込まない)")
    sys.exit(0)

# autoMode 以外のユーザー設定は一切触らない
merged = dict(current)
merged["autoMode"] = fragment["autoMode"]

dest.parent.mkdir(parents=True, exist_ok=True)
tmp = dest.with_suffix(".json.tmp")
tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp.replace(dest)
n = len(fragment["autoMode"].get("environment", []))
print(f"[automode] {dest} に autoMode.environment ({n} 項目) を書き込み")
PY
