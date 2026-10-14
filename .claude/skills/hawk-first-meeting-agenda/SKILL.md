---
name: hawk-first-meeting-agenda
description: HAWK の初回打ち合わせ（初めて会う商談）で画面共有する「アジェンダシート」スライドを、テンプレから会社ごとに作る。先方の会社紹介・主な取り組み（写真つき）・事前アンケート・ディスカッションしたいこと・お伺いしたいこと・デモ内容・次のステップの9枚構成。「初回の打ち合わせ資料作って」「〇〇社のアジェンダシート」「初回案内のスライド」「カレンダーのこの予定の資料作って」などで使う。概要資料（HAWK Overview）は別物で、これはその前後に出す進行用のシート。
---

# hawk-first-meeting-agenda: 初回打ち合わせアジェンダシート

2026-10-14 のピーエーシー様（PAC）初回打ち合わせで作ったデッキをテンプレ化したもの。
完成形の見本: 【ピーエーシー様】HAWKお打ち合わせ アジェンダ_20261014
`https://docs.google.com/presentation/d/14zgB5FeEYUs1fVXx88EVbajGSkK62B0bfhWijB7lzec/edit`

テンプレ: **【テンプレ】HAWK初回打ち合わせ アジェンダ**
`presentationId: 1_v3W-u6awkmHMpL8DWU9RFFtDmsjvQcavkXw6oUK_6k`
（`agenda/fill_agenda.py` の `TEMPLATE_ID`。テンプレを作り直したらここも直す）

## 進め方（この順番を守る。片山さんの好みの流れ）

1. **素材集め（読み取りのみ）**
   - カレンダー予定を特定する。`.../eventedit/<eid>` の eid は base64 で
     `<eventId> <calendarEmail>` になっている（`echo <eid> | base64 -d`）。
     `gog --account yuki.katayama@fout.jp -j calendar event primary <eventId>`
   - 予定の説明欄と添付（会社概要_〇〇 Doc、ウェビナー申込アンケート等）を読む。
     会社概要 Doc は hawk-inbound-lead / hawk-shodan-prep が作っているものがある。
   - 過去の同種デッキの構成も参考になる（viviON様ご案内資料、gaaboo様オンボーディング資料）。
2. **中身だけ先にチャットで出す**（いきなりスライドにしない）。
   ページタイトル＋構成テキストを9枚分。片山さんがアジェンダの流れ
   （例: 現状 → お困りごと → フリークアウトへの期待 → HAWKでどう解決 → デモ → Q&A）と
   時間配分を言うので、それに合わせる。OK が出てからスライド化。
3. **config JSON を書いて流し込む**（スクラッチパッドに置く）。
   `agenda/examples/pac_20261014.json` をコピーして値を差し替える。
   ```bash
   python3 agenda/fill_agenda.py <config.json> --out-dir <scratchpad>/agenda_out
   ```
   テンプレをコピー → `{{KEY}}` を置換 → 画像を差し込み → PDF 書き出し＋PNG 描画、まで自動。
4. **PNG を必ず目で見る**（`page-N.png`）。はみ出し・改行崩れ・写真のトリミングを確認し、
   直したら再度 PDF で確認。リンクを渡す。

## テンプレの構成とプレースホルダ

| P | ページ | キー |
|---|---|---|
| 1 | 表紙 | `COMPANY`（「御中」は固定）, `DATE_LONG`, `FO_MEMBERS`, 画像 `LOGO`（白カード内） |
| 2 | 本日のアジェンダ | `DATE_SHORT`, `T1`〜`T4`（開始時刻）, `OPENING`（例「9/29 ウェビナーご参加の御礼」）。各行の所要時間（5/15/20〜25/20分）と行タイトルは固定文言 |
| 3 | 御社について | `KPI1`〜`KPI3` と各 `_SUB`, `BIZ_HEAD`, `BIZ_LINE1`, `BIZ_LINE2`, `PHILOSOPHY`, `PHILOSOPHY_NOTE` |
| 4 | 御社の主な取り組み | タイル6枚 × `Wn_TAG`, `Wn_NAME`, `Wn_DESC`, 画像 `Wn_PHOTO`（n=1..6。上段3・下段3。タグ色は上段緑・下段オレンジ） |
| 5 | 事前アンケート | `SURVEY_SOURCE`, `S_TAISEI`, `S_MEDIA`, `S_WANT`, `ISSUE1`/`_SUB`, `ISSUE2`/`_SUB` |
| 6 | ディスカッションしたいこと | 固定（現状→お困りごと→ご期待→解決） |
| 7 | 具体的にお伺いしたいこと | `Q1`〜`Q5`, `Q2_SUB`, `Q3_SUB`, `Q5_SUB`（Q1 はオレンジ強調。最初は「一番お困りのこと」をふわっと聞く） |
| 8 | デモでお見せすること | `MAP1`/`_SUB`, `MAP2`/`_SUB`（アンケートの課題 ↔ HAWK 機能の対応） |
| 9 | 次のステップ／質疑応答 | `END_TIME` |

`LOGO` は P1〜P9 すべての右上（HAWK ロゴの左）と表紙に入る。
画像を指定しなかった枠は灰色の「写真」枠で残る。
文字キーが残っていると実行時に `WARN: 未設定の文字` が出る。

## 画像の入れ方（ここが一番ハマる）

この環境のネットワークからは多くのサイトに**直接つながらない**
（pacweb.co.jp、市役所サイト、Wikipedia 等は 403/DNS 失敗。WebFetch も同じ）。
そこで **Google 側から取りに行かせる**。Slides の createImage は Google のサーバーが URL を取得するので、
公開 URL さえあれば差し込める。

- **先方ロゴ** → 片山さんに**公式の SVG/PNG をもらう**（`{"file": "..."}`）。
  サイトのスクショから切り抜いたロゴはズレてダサいと言われた。SVG は自動で PNG 化する。
  ローカル画像は一時的に Drive に上げて「リンクを知っている全員」で共有 → 差し込み →
  共有解除＆ゴミ箱、までスクリプトがやる。
- **施設・イベント・自社メディアの写真** → `{"mshot": "<ページURL>", "crop": [左, 右, 上, 下]}`。
  WordPress mshots（`s.wordpress.com/mshots/v1/<URL>`）がページのスクショを返す。
  初回は「Generating Preview」画像が返るので、スクリプトは一度差して30秒待ってから差し直す。
  crop は 1024×768 のスクショに対する割合。枠は 84×63pt（4:3）なので、
  `(1-左-右)*1024 : (1-上-下)*768 ≒ 4:3` になるように切る（ずれると縦横が歪む）。
  候補ページが分からないときは、作業用スライドに候補を何枚か並べて差し込み、
  PDF 書き出しで見比べてから選ぶ。
  翻訳ポップアップが出るサイト（静岡市役所など）や Wikipedia の小さい写真は使いにくい。
- **媒体アイコン** → `{"icons": ["google.com", "yahoo.co.jp", "meta.com", "line.me"]}`。
  Google のファビコンサービスから取る。「具体的な事例がない領域（Web 広告運用など）」の
  タイルに使うと見栄えがよい。

### 使えない／ハマった手段（試さなくてよい）

- Slides のサムネイル API の contentUrl（googleusercontent）は、この環境からダウンロードできない
  → 見た目の確認は **Drive の PDF エクスポート＋pdftoppm** で行う。
- Sheets の `IMPORTXML` / `IMAGE` は API 経由だと「デスクトップのブラウザで外部 URL へのアクセスを
  許可して」となって動かない。
- `image.thum.io` は Google から取得すると forbidden。
- 画像のトリミング後に `updatePageElementTransform` でサイズを変えると極小になって消える。
  サイズを変えたいときは**消して作り直す**。
- `gws slides ... batchUpdate --json "$(cat 大きいJSON)"` は Argument list too long。
  大きいリクエストは `agenda/gapi.py`（REST 直叩き）を使う。

## 中身のルール

- 先方について書く事実は、会社概要 Doc・公式サイト・検索で裏が取れたものだけ。
  取れないもの（例: 「ガンダムが東静岡へやってきた」が先方の実績か）は、
  スライドに断定で書かず、片山さんに確認を促すか、事実だけ言える書き方に変える。
- 先方に見せる資料なので、社内メモ（「要確認」「先方共有不可」等）は載せない。
- 料金・リリース時期など台本に無い約束は書かない。
