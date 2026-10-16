# 機能取扱説明書 横展開キット

HAWK の「機能取扱説明書」（マスターシート → スライド自動生成 → 定期巡回 → Slack 承認）を、
ほかのプロダクト（アルパカ、GB など）でも作れるようにしたプロンプト集。

| ファイル | 中身 |
|---|---|
| `prompts/00_設定.txt` | プロダクトごとに埋める変数（①②の先頭に差し込む） |
| `prompts/01_初回構築.txt` | 資料を全部読んで、管理シートと下書きスライド v1 を作る |
| `prompts/02_巡回と承認フロー.txt` | 定期巡回の Routine と Slack 承認依頼（✅/❌/✏️）を登録する |
| `prompts/03_日常の一言.txt` | 運用が始まったあとの頼み方 |
| `template.html` → `page.html` | 共有ページ。`python3 build_page.py` で prompts/ から組み立てる |

プロンプトの正本は `prompts/`。直したら `python3 build_page.py` を回して共有ページを publish し直す。
HAWK 側の実装は ブランチ `claude/wonderful-noether-a5izp6` の `hawk_manual/` と
`.claude/skills/hawk-manual-update/SKILL.md`。
