# 週報メモ下書きツール

毎週水曜の「HAWK週次アタックリスト＋週報下書き」Routine で使う。
本番「HAWK営業 - 定例会報告書」の最新タブを【片山】週報メモに写し、今週分だけ黒字で足す。

```bash
SC=<作業ディレクトリ>
# 1. 本番 Doc を JSON で取得し、最新タブを markdown に
gws docs documents get --params '{"documentId":"1I7u2zNZTPl9tAo2SGalo35ElsDWu2MPpP6JgIYr8LCk","includeTabsContent":true}' > $SC/prod_doc.json
python3 weekly/memo_tools/doc2md.py $SC/prod_doc.json <本番タブID> $SC/prod.md
# 2. prod.md を編集して今週版 memo.md を作る（片山分だけ）
# 3. 週報メモにタブを作って書き込む（429 で表が欠けても次の手順で直る）
gog --account yuki.katayama@fout.jp docs add-tab 1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY --title "MM/DD" --index 0
gog --account yuki.katayama@fout.jp docs write 1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY --tab "MM/DD" --file $SC/memo.md --markdown --replace
# 4. 表の修復（再実行可）
TAB=<メモのタブID> MD=$SC/memo.md PROD_JSON=$SC/prod_doc.json PROD_TAB=<本番タブID> python3 weekly/memo_tools/fixtables.py
# 5. 前週から変わっていない行をグレーに（まず dry-run、良ければ --apply）
TAB=<メモのタブID> python3 weekly/memo_tools/graypast.py $SC/prod.md $SC/memo.md [--apply]
```

- gog の markdown 書き込みは本文の後に表を1つずつ作るため、Docs の書き込み上限（429）に当たりやすい。
  文字のまま残った章見出し（`| 0. 共有事項 |` と `|---|`）や、消えた複数行の表を fixtables.py が作り直す。
- 色分け：黒字＝今週足した・書き換えた行（片山が本番へコピペする部分）、薄いグレー（RGB 0.65）＝前週から変わっていない行。
  章見出し（1x1表・白文字）と商談ステータス表は触らない。
- 本番 Doc には書き込まない。
