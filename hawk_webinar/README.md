# HAWK ウェビナー（2026-09-29）スライド編集スクリプト

Google Slides API を直接叩いて、投影版（紙芝居版）と送付版（本番版）の2デッキを一括編集する。
2026-09-17 の決定事項（改良メモ 6章）を反映した際に使ったもの。

- 改良メモ: https://docs.google.com/document/d/1BCYVbaxg8EbQzXCaL-DEqbDk-59m6J1HDzXkJ6N7-fU/edit
- 投影＝紙芝居版（55枚）: https://docs.google.com/presentation/d/1WdSjAJttmgzPQHgH_OAlxhCKY1RBrCqeE4xBzIHUyM0/edit
- 送付＝本番版（41枚）: https://docs.google.com/presentation/d/1mTA1GT3-nPTos6K-Kk6MP2C8JWCns8Tp-8yeXkQz4ys/edit

## 認証
`setup_gws_remote.sh` が作る `~/.config/gws/credentials.json`（gog のトークン流用）を
`slidekit.py` がそのまま読んでアクセストークンに交換する。新規認証はしない。
`gws --json` はコマンドライン引数長の上限（約128KB）に当たるため、`requests` で直接 POST している。

## ファイル
| ファイル | 役割 |
|---|---|
| `slidekit.py` | API 呼び出し、`set_text` / `shape` / `line` / ノート操作などの部品 |
| `builders.py` | スライド単位の描画定義（お悩み集計・こんな毎日・こう変わる・レイヤー図・ハブ図・内訳表・予備デモ・DEMO 本文）。**数字や文言を差し替えるときはここの定数を変える** |
| `run_kb.py` / `run_kb2.py` | 紙芝居版: 既存スライドの★埋め・図解（phase1）／新規スライド追加（phase2） |
| `run_hb.py` / `run_hb2.py` | 本番版: 同上＋黄色メモ撤去・P14/P15 差し替え |
| `dump.py` / `detail.py` / `stars.py` | `slides raw` の JSON から本文・ノート・objectId・座標・文字スタイルを読む調査用 |
| `render.py` | Drive export の PDF を PyMuPDF でページ画像化（thumbnail API は CDN がプロキシで遮断されるため） |

## 再実行の注意
- `run_*.py` は objectId 直指定が多い。スライドを手で編集したあとは `detail.py` で id を確認してから使う。
- `run_kb2.py` / `run_hb2.py` は `kb_survey` 等の固定 id が既にあれば複製をスキップし、中身だけ作り直す（`strip_body` で本文を消してから再描画）。
- お悩み集計（`SURVEY` / `QUOTES`）は集客シート 9/16 11:00 時点の n=12。当日朝に再集計して更新する。
