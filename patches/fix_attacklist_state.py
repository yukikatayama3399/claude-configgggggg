#!/usr/bin/env python3
"""
hawk-attacklist-morning-sync/state.json の note に固定されている
「gogトークン失効継続」という誤った記録を訂正する。

この note が残っている限り、ルーティンは自分のメモを信じて
「失効継続のためスキップ」を続けてしまう。実際にはトークンは
2026-08-07 の検証で終始正常だった（22 スコープ健在、両アカウントとも
refresh token exchange 成功）。

note の他の記述（列マッピング・タブ名変更）は運用上必要なので残す。
last_written が 7/8 のままである事実も残す（差分取り込みは実際に必要）。

使い方:
    python3 patches/fix_attacklist_state.py            # 差分を表示するだけ
    python3 patches/fix_attacklist_state.py --write    # 実際に書き換える

第1引数に state.json のパスを渡すと、そちらを対象にする（動作確認用）。
"""
import datetime
import json
import pathlib
import shutil
import sys

STATE = (
    pathlib.Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/Claude"
    / "scheduled-tasks/hawk-attacklist-morning-sync/state.json"
)

OLD = (
    "2026-07-21〜2026-08-05: gogトークン失効継続（16日間）でシートアクセス不可。"
    "last_writtenは7/8時点のまま。復旧次第、差分を一括取り込み予定。"
)

NEW = (
    "【2026-08-07 訂正】「2026-07-21からgogトークン失効」という従来の記録は誤りだった。"
    "トークンは終始正常（22スコープ健在・両アカウントともrefresh成功）。"
    "真因は gog-health.sh が失敗の種類を問わず exit 1 を返し、"
    "inbox-calendar-watchdog がそれを一律「失効」と解釈していたこと。"
    "両方とも2026-08-07に修正済み。"
    "認証を理由にシート更新をスキップしないこと。"
    "ただし last_written は7/8時点のままなので、次回実行で7/9以降の差分を一括取り込みすること。"
)


def fail(msg):
    print(f"!! {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    args = sys.argv[1:]
    write = "--write" in args

    global STATE
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        STATE = pathlib.Path(positional[0])

    if not STATE.exists():
        fail(f"state.json が無い: {STATE}")

    raw = STATE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"JSON として読めない: {e}")

    note = data.get("note")
    if note is None:
        fail("note フィールドが無い")

    if NEW[:20] in note:
        print("すでに訂正済み。何もしない。")
        return

    if OLD not in note:
        print("想定していた誤記述が見つからなかった。手で確認してほしい。")
        print("--- 現在の note ---")
        print(note)
        sys.exit(1)

    data["note"] = note.replace(OLD, NEW)

    print("--- 変更前 ---")
    print(note)
    print("\n--- 変更後 ---")
    print(data["note"])

    if not write:
        print("\n--- ドライラン。書き換えていない。適用するには --write を付ける。")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = STATE.with_suffix(f".json.bak-{stamp}")
    shutil.copy2(STATE, backup)

    # rows などの他フィールドは触らない。ensure_ascii=False で日本語を保つ。
    STATE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 書き戻したものが JSON として読めるか自己検証する。
    json.loads(STATE.read_text(encoding="utf-8"))
    print(f"\n--- 書き換えた。バックアップ: {backup}")


if __name__ == "__main__":
    main()
