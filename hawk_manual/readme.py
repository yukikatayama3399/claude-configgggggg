"""マスターシートの README タブを書き直す。

先頭に「いま使う URL」（社内管理用の最新下書き・お客様送付用の本番固定URL）を置き、
運用ルールと、Routine が毎回送るプロンプト（SKILL.md のコードブロックをそのまま）を続ける。
build_slides.py が生成のたびに呼ぶ。手で回すときは `python3 readme.py`。
"""
import json
import pathlib
import re

from gws import call, read_tab

HERE = pathlib.Path(__file__).parent
SKILL = HERE.parent / ".claude" / "skills" / "hawk-manual-update" / "SKILL.md"


def _url(pid: str) -> str:
    return f"https://docs.google.com/presentation/d/{pid}/edit" if pid else "（未作成）"


def routine_prompt() -> list[str]:
    text = SKILL.read_text()
    m = re.search(r"## Routine（自動ループ）のプロンプト.*?```\n(.*?)```", text, re.S)
    return m.group(1).strip().splitlines() if m else ["（SKILL.md にプロンプトが見つからない）"]


def lines(cfg: dict) -> list[str]:
    drafts = [r for r in read_tab(cfg["master_sheet_id"], "版管理") if r.get("種類") == "draft"]
    latest = drafts[-1] if drafts else {}
    prods = [r for r in read_tab(cfg["master_sheet_id"], "版管理") if r.get("種類") == "prod"]
    prod_at = prods[-1].get("生成日時", "") if prods else ""
    return [
        "HAWK 機能取扱説明書マスター — 運用ルール",
        "",
        "■ いま使う URL（スライドを作り直すたびに自動で更新）",
        f"  社内管理用の最新下書き: {latest.get('版', '')}（{latest.get('生成日時', '')}）",
        f"    {latest.get('スライドURL', '') or _url(cfg.get('draft_presentation_id', ''))}",
        "    ※ 社内確認用。お客様には渡さない。過去の版は「版管理」タブ。",
        "  お客様送付用（本番・固定URL）: このURLは今後も変わらない。中身だけ上書きされる",
        f"    {_url(cfg.get('prod_presentation_id', '')).replace('/edit', '/view')}",
        f"    ※ 最終更新: {prod_at or '—'}。片山の指示があったときだけ作り直す（自動では更新しない）。",
        "",
        "■ このシートが「正」",
        "  スライドはこのシートから自動生成する。スライドを直接直さない。",
        "  下書き・本番とも「承認＝承認済」の行だけで作る（本番はさらに「提供状態＝提供中」だけ）。",
        "",
        "■ 承認フロー",
        "  1. 自動ループ（月・木 8:52）が Slack（#hawk-社内利用 / #hawk-product ＋全体検索）・Gmail・Drive の新着から",
        "     変更を拾い、各タブに「承認＝下書き」（候補）で行を足す。更新履歴タブにも1行残す。",
        "  2. #hawk-sales-private に片山宛ての承認依頼を投稿する。片山は候補ごとに ✅（入れる）/ ❌（入れない）を付ける。",
        "  3. 次の巡回で ✅ の候補を承認済にし、社内管理用の下書きを新しい版で作り直す（❌ は差戻し）。",
        "  4. 本番（お客様の固定URL）は片山が「本番に反映して」と指示したときだけ作り直す。",
        "",
        "■ ID のルール",
        "  機能ID: F-カテゴリ略号-連番（例 F-DD-003）／画面ID: S-連番／逆引き: UC-連番",
        "  一度振った ID は変えない・使い回さない（削除するときは提供状態を提供終了にする）。",
        "  承認済の行は書き換えない。仕様変更は同じIDの新しい行を足し、承認されたら古い行が「置換済」になる。",
        "",
        "■ 版管理",
        "  下書きは版ごとに別ファイル。本番を作り直すたびに PDF を書き出して日付付きで保存し、版管理タブに1行残す。",
        "",
        "■ 確認メモ：自動ループ（巡回）の設定",
        "  拾う範囲: Slack #hawk-社内利用・#hawk-product の全投稿 ＋ Slack 全体の「HAWK」「DealDesk」検索",
        "    ＋ Gmail の「HAWK」「DealDesk」メール ＋ Drive の HAWK 仕様書・リリースノート（すべて読み取りのみ）",
        "  承認依頼の投稿先: Slack #hawk-sales-private（片山宛てのメンション）",
        "  手順の本体: GitHub リポジトリ claude-configgggggg の .claude/skills/hawk-manual-update/SKILL.md",
        f"  ループの実体: Claude の Routine「HAWKマニュアル巡回」（月・木 8:52 JST）{cfg.get('routine_id', '')}",
        "  毎回 Routine から送るプロンプト（そのまま）:",
    ] + ["    " + ln for ln in routine_prompt()]


def write(cfg: dict):
    sid = cfg["master_sheet_id"]
    body = lines(cfg)
    call("sheets.spreadsheets.values.clear", {"spreadsheetId": sid, "range": "README!A1:A300"})
    call("sheets.spreadsheets.values.update", {"spreadsheetId": sid, "range": "README!A1", "valueInputOption": "RAW"},
         {"values": [[ln] for ln in body]})


if __name__ == "__main__":
    write(json.loads((HERE / "config.json").read_text()))
    print("README を更新しました")
