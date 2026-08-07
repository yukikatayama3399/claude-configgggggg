# 週次報告の自動生成を「新規作成」から「あれば更新」に変える

**次に Mac 側（scheduled-tasks の週次報告ドラフト生成）を触るときの作業メモ。**
クラウドセッションからは Mac ローカル / iCloud のタスク定義を編集できないため、
仕様とヘルパースクリプトだけこのリポジトリに置いてある。

## なぜ必要か

週次報告ドラフトの自動生成が毎回 `週次報告_YYYY-MM-DD_片山` を**新規作成**する作りだと、
週の途中で人手が書き足した申し送り（商談で判明した論点、来週の全体共有ネタなど）が
生成時に取り残される。実際に 2026-08-14 分は 8/7 時点で先に器を作り、
サイバー・バズ様の利用用途（小型案件を低リソースで回したい）を先行メモとして書き込んである。
このまま新規作成されると、その内容が入っていない別の Doc ができてしまう。

## 期待する挙動

1. 対象日（その週の**金曜日** `YYYY-MM-DD`）で `週次報告_YYYY-MM-DD_片山` を Drive から探す
2. **あれば**その Doc を更新する（新規作成しない）
3. **無ければ**従来どおり新規作成する
4. 更新時、**「■ 0. 先行メモ」ブロックは絶対に消さない**。内容は
   ■1 サマリー / ■2-1 の該当社の項 / ■5 所感 に反映したうえで、ブロック自体は残置する

保存先フォルダ: `11_週次mtg用報告メモ / Yuki`
（folder id `1F70c4D3EuWR14kefYyKCiEw4Wy9Jzvvk`。共有ドライブ配下）

## 使うもの

`weekly_report_doc.sh`（このリポジトリ同梱）。gog CLI だけで動く。

| モード | 挙動 |
|---|---|
| （既定） | docId を出力。無ければ作ってから出力 |
| `--no-create` | docId を出力。無ければ exit 3 |
| `--carryover` | 既存 Doc の「■ 0. 先行メモ」ブロックだけ出力（無ければ空） |
| `--reset-body` | ヘッダと ■0 を残して「■ 1.」以降を削除し、本文の挿入インデックスを出力 |

組み込みイメージ:

```bash
D=2026-08-14                                     # その週の金曜日
ID=$(./weekly_report_doc.sh "$D")                # find-or-create
CARRY=$(./weekly_report_doc.sh "$D" --carryover) # 先行メモをプロンプトに渡す

# ... $CARRY を踏まえてドラフト本文（■1 以降）を draft.txt に生成 ...

IDX=$(./weekly_report_doc.sh "$D" --reset-body)  # ■1 以降だけ差し替え
gog --account yuki.katayama@fout.jp docs insert "$ID" -f draft.txt --index "$IDX"
```

## 落とし穴（実測済み）

- **`docs clear` を使わない。** ヘッダも ■0 も消える。`--reset-body` は
  「■ 1.」段落（直前の区切り線含む）から本文末尾までを `docs delete` で消すだけなので、
  ヘッダと ■0 はそのまま残る。
- **`docs cat` はハイパーリンクを落とす。** 既存 Doc を cat して作り直す方式にすると、
  参照 Doc のリンクが平文タイトルに戻る。既存週報は参照をリンク化する慣習なので、
  「読んで作り直す」ではなく「■1 以降だけ消して挿し込む」で通すこと。
  `--carryover` の出力もリンクは落ちているので、**プロンプトに渡す用途に限る**
  （そのまま書き戻さない）。
- **リンクを新規に張るときは `docs find-replace --format markdown`。**
  `[表示テキスト](URL)` が本物のハイパーリンクになる。
  ただしリンクテキスト自体に `[` を含めるとマークダウンとして壊れるので、
  `[オンライン社外] 〜` のような Doc 名はその部分を外して張る。
- **`docs insert` は挿入位置の段落スタイルを継承する。** 見出し段落の先頭に挿すと
  丸ごと見出しになる。通常テキストの位置に挿してから
  `docs format --match "<見出し行>" --heading-level 3` で直すのが安全。
  なお `--heading-level` は `HEADING_3` ではなく `3` を渡す。
- **完全一致検索は `--raw-query`。** `drive search "name = '...' and trashed = false" --raw-query`。
  素の全文検索だと同名以外も拾う。

## 検証手順

本番の Doc を壊さずに試せる。

```bash
# 適当な未来日でコピーを作って試す
gog --account yuki.katayama@fout.jp drive copy <既存docId> "週次報告_2026-08-21_片山" \
  --parent 1F70c4D3EuWR14kefYyKCiEw4Wy9Jzvvk

./weekly_report_doc.sh 2026-08-21 --no-create     # id が出る
./weekly_report_doc.sh 2026-08-21 --carryover     # ■0 が出る
IDX=$(./weekly_report_doc.sh 2026-08-21 --reset-body)
gog --account yuki.katayama@fout.jp docs cat <copyId> | tail   # ヘッダ+■0 だけ残る

gog --account yuki.katayama@fout.jp drive delete <copyId> -y   # 後片付け
```

2026-08-07 時点でこの手順を一通り実行し、■0 のハイパーリンク2本が
`--reset-body` 後も保持されることを確認済み。
