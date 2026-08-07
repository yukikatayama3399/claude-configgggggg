#!/usr/bin/env python3
"""
inbox-calendar-watchdog/SKILL.md の「gog死活チェック」節を差し替える。

置き換え内容は patches/inbox-calendar-watchdog-gog-section.md の
```markdown ... ``` フェンス内から読む（正は常にそちら）。

使い方:
    python3 patches/apply_watchdog_patch.py            # 差分を表示するだけ
    python3 patches/apply_watchdog_patch.py --write    # 実際に書き換える

--write 時は SKILL.md.bak-YYYYMMDDHHMMSS を必ず残す。
"""
import datetime
import difflib
import pathlib
import re
import sys

HEADING = "## gog死活チェック"
TARGET = pathlib.Path.home() / ".claude/scheduled-tasks/inbox-calendar-watchdog/SKILL.md"
PATCH = pathlib.Path(__file__).with_name("inbox-calendar-watchdog-gog-section.md")


def fail(msg):
    print(f"!! {msg}", file=sys.stderr)
    sys.exit(1)


def extract_replacement(patch_text):
    """```markdown フェンスの中身を取り出す。"""
    m = re.search(r"^```markdown\n(.*?)^```$", patch_text, re.M | re.S)
    if not m:
        fail("パッチファイルから ```markdown フェンスを取り出せなかった")
    return m.group(1).rstrip("\n")


def find_section(lines):
    """見出し行の位置と、次の '## ' 見出しの位置を返す。"""
    start = None
    for i, line in enumerate(lines):
        if line.startswith(HEADING):
            start = i
            break
    if start is None:
        fail(f"'{HEADING}' で始まる節が見つからない: {TARGET}")

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return start, end


def main():
    write = "--write" in sys.argv[1:]

    if not TARGET.exists():
        fail(f"対象が無い: {TARGET}")
    if not PATCH.exists():
        fail(f"パッチが無い: {PATCH}")

    original = TARGET.read_text(encoding="utf-8")
    replacement = extract_replacement(PATCH.read_text(encoding="utf-8"))

    lines = original.splitlines()
    start, end = find_section(lines)

    # 置換後も、元の節の後ろにあった空行の詰まり方を壊さないようにする。
    new_lines = lines[:start] + replacement.splitlines() + [""] + lines[end:]
    updated = "\n".join(new_lines)
    if original.endswith("\n"):
        updated += "\n"

    if updated == original:
        print("差分なし。すでに適用済み。")
        return

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=str(TARGET),
        tofile=str(TARGET) + " (更新後)",
    )
    sys.stdout.writelines(diff)

    if not write:
        print("\n--- ドライラン。書き換えていない。適用するには --write を付ける。")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = TARGET.with_suffix(TARGET.suffix + f".bak-{stamp}")
    backup.write_text(original, encoding="utf-8")
    TARGET.write_text(updated, encoding="utf-8")
    print(f"\n--- 書き換えた。バックアップ: {backup}")


if __name__ == "__main__":
    main()
