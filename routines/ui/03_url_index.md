# hawk-url-index-original-refresh（既存を編集）

対象: trig_01H3eK8s6RAMj3to5SQFpQhi

既存 Routine のプロンプトを下で置き換える。
直るもの: シートが 7/28 から一度も更新されておらず、毎朝「A1から貼り付けてください」の同じ TSV が DM に届いている（Drive コネクタにシート書き込みツールが無いため）。gog で直接上書きする。

## プロンプト（全文を貼る）

`````
平日9:00 JST実行。Google Drive上の「HAWK関連資料 URL一覧集（原本参照）」スプレッドシートを、原本（オリジナルファイル）を参照する形で最新化する。日本語で作業・報告すること。

## 対象シート
- fileId: 1dnSL89LwWqYN-IxFlb-YX7IoKSNSjAVhRpJSxrwefa8（このシートを上書き更新。新規シートは作らない）
- 列構成：フォルダ / タイトル / 作成日 / 制作者 / 主なポイント / URL
- 注意：似た名前の別シート（コピー名義の全フォルダインデックス）が存在するが、それは管理対象外。このfileIdのシートのみ扱う。

## 絶対ルール
1. ファイルをユーザーのDriveにコピーしない。コピーすると制作者が自分名義になりURLが原本と乖離してバージョン管理が壊れる。
2. URL・制作者・作成日は必ず原本（他者所有のオリジナル）のもの。作成日=原本のcreatedTime、制作者=原本のowner。
3. 既存シートの上書きのみ。

## 手順
1. 外側ループ用ログDoc（fileId: 1aC49gjHM49W32rFjf19EGNuCyEgGAw0nho_S8Bnhv7A）を読み、過去の教訓を今回の処理に反映する。
2. 原本台帳「HAWK関連資料など」（fileId: 1xLtKg7j4qD8eaZ9uM7X4JfvZ_DnwYCuZiJNOc0PuS28 / miwata@fout.jp所有）を読む。これが原本リンクのソース・オブ・トゥルース。
3. 台帳の各資料のfileIdについてメタデータを取得し、原本のowner・createdTime・正式URLを取る。
4. 台帳に無いが含めるべき資料（Sales Training議事録・録画等）はDrive検索で原本を探し同様に取得。
5. カテゴリ体系（後述の確定マッピング）で表を組む。※「原本探索不要」と付記された行はメタデータ取得せず記載のまま必ず出力する。
6. 「主なポイント」列は確定マッピングの各行末尾【】内の記述を使う。

## 書き込み手段
- 末尾の「ステップ0」で gog を用意し、**gog で対象シートを直接上書きする**（Google Drive コネクタにはシートを書き換えるツールが無く、2026-07-28 以降一度もシートが更新されないまま、毎朝同じ TSV を DM で送り続けていた）。
  1. `source ~/.routine_env && gog --account yuki.katayama@fout.jp sheets metadata 1dnSL89LwWqYN-IxFlb-YX7IoKSNSjAVhRpJSxrwefa8 -j` でタブ名を確認
  2. 現在の値を `sheets get` で読み、今回組んだ表（ヘッダー付き6列）と比較する
  3. 差分がある場合のみ `sheets clear` で旧データ範囲を消してから `sheets update ... --input USER_ENTERED` で A1 から書き込み、`sheets get` で読み返して一致を確認する
  4. 差分が無ければ書き込まない
- ステップ0が失敗した場合だけ、従来どおり差分があるときに限り TSV（ヘッダー付き6列）を Slack DM（自分宛, U0B7FMCR8JU）に送り「A1から貼り付けてください」と添える。

## 確定マッピング（基準値。毎回検証し台帳の更新を反映）
01_ピッチ資料:
- ENG HAWK Overview 05302026 / miwata@fout.jp / https://docs.google.com/presentation/d/1_i5OuTV0C598bvFXQe4G57tFXBnOGz9J/edit 【英語版ピッチ資料・最新版】
- HAWK Overview 05182026（日本語版） / miwata@fout.jp / https://docs.google.com/presentation/d/1YO2Lmgs7gFwK3f6vt0dJW07INkFZNT4o7PEHim4Tw7M/edit 【日本語版ピッチ資料・デモ動画あり】
- HAWK_META_セットアップガイド / sugiura@fout.jp / https://drive.google.com/file/d/1AMexJVnY7Gd8dBbXdr3XqccRTwmQEz1z/view 【Meta連携セットアップ手順書】
- hawk_product_demo / sugiura@fout.jp / https://drive.google.com/file/d/1RTV8UCMpPipkbiiMtPq1uq1hylXtYmtS/view 【プロダクトデモスライド】
01_ピッチ資料/旧バージョン:
- HAWK Overview 03312026 Ver1.0（旧） / miwata@fout.jp / https://docs.google.com/presentation/d/19-eeK36kR-gS_tiy8HA4BoLyHgHkRXLNt8cmDKKhMN8/edit 【旧版（2026年4月時点）】
- HAWK Overview 05182026（Yugoオリジナル・旧） / yugo@fout.jp / https://docs.google.com/presentation/d/1XWG8Pn_bf2qfI7EuWD7l5mQ6rexEe-wFYS1-WfSHbBg/edit 【Yugo作成版】
- HAWKデモ会資料 2026/01/15（旧） / google-apps-admin@fout.jp / https://docs.google.com/presentation/d/1xXvTvjC3RG0m7nE78SdY5aO5lQzNgKxIVOB7IIoWVVo/edit 【デモ会資料（旧・1月時点）】
02_会議ログ:
- HAWK_mtg議事録集_0602 / 自作集約（yuki.katayama@fout.jp） / https://docs.google.com/document/d/1aNyUowlFb6EXw-7A6A1Jw_gOMI0u9KJeS7DG7HEkqcM/edit 【HAWK商談議事録の集約】※原本探索不要。この行は必ずこのまま出力する。作成日欄は空でよい
- HAWK_mtg議事録 / 自作集約（yuki.katayama@fout.jp） / https://docs.google.com/document/d/11ZzBUBOJRZ20Ltr8GiZlYADTJHTdy3ipAn1imnBJoWM/edit 【HAWK商談議事録】※原本探索不要。この行は必ずこのまま出力する。作成日欄は空でよい
- HAWK Sales Training Notes 2026/06/02 / yugo@fout.jp / https://docs.google.com/document/d/1QB8cDbJbUwFu-JF4peqZxqFqQrTufR9w6oHsu3Hvt3I/edit 【セールストレーニング議事録】
- HAWK Sales Training Recording 2026/06/02 / yugo@fout.jp / https://drive.google.com/file/d/10SFGlUEK7LUuarAsTDuitkbuC-T5b1ld/view 【セールストレーニング動画】
03_セールスリスト:
- 【瀧澤さんへ】ご紹介依頼シート（岩田リスト） / miwata@fout.jp / https://docs.google.com/spreadsheets/d/11vFpSVi9-kjjB2JWt3nBftWznTU9FgyKVjTyYg1juE8/edit 【代理店アタックリスト】
- FY26-27_OEMdiv管理シート（片山リスト） / y-akinaga@fout.jp / https://docs.google.com/spreadsheets/d/1ItvxXhjFsOVf7csosBrIfYkLFKdYq64iukfDZ1Gj-YQ/edit 【OEM部門営業管理シート】
04_シミュレーション:
- new_hawk_pricing_tier_business_plan_05182026 / yugo@fout.jp / https://docs.google.com/spreadsheets/d/1elGyTP6OVYvFGwL98az-Cj2cdEaiH_nPXO2Lwm9Ksp0/edit 【料金体系・事業計画シート】
05_資料集:
- ①Meta広告入稿操作（営業事務・オペ向け） / chika.tagashira@fout.jp / https://docs.google.com/document/d/1_1PX1uR5eQ6ExfRdaq2AixwGHdUw_pqVcz99sOY0a7c/edit 【Meta入稿レクチャーメモ】
- ②Meta広告手順（HAWK利用なし・マーケ向け） / nakashiba-tomoka@fout.jp / https://docs.google.com/document/d/1SIsT1Jw7df2AfrzISpilu1fj1M-FlPNwKVXS1wWS1Js/edit 【Meta広告設定手順メモ】
- ③HAWKレクチャー（OEM Div向け） / ryo.owada@fout.jp / https://docs.google.com/document/d/1JzQOUxKEZ-cq5egDS8SDvd1q5FgUlw2YtJEVMFb-6t4/edit 【OEM部門向けレクチャーメモ】
- ④HAWK×Meta連携設定（マーケ自社広運用者向け） / miwata@fout.jp / https://docs.google.com/document/d/1v7UAIa7GYkJ5Bj7i-rp1oLJDzBi8CS5x2fwRTsSrFgI/edit 【Meta連携設定会議メモ】
- 機密保持契約書（NDA）ひな形 / miwata@fout.jp / https://drive.google.com/file/d/1NuOCQWMpnTdrR2VLECfVpdJyEOZ1nki6/view 【FOフォーマットNDA雛形】

注：05_資料集の①〜④は台帳上のリンクが Gemini会議メモを指すが、ユーザー承認済みでこのまま原本採用とする（タイトルと中身が一致しなくてもURLが正しければ可）。

## 外側ループ（毎回必須）
終了時、つまずいた点・原本特定の失敗・ツール挙動の想定違いがあれば、ログDoc（fileId: 1aC49gjHM49W32rFjf19EGNuCyEgGAw0nho_S8Bnhv7A）に「- YYYY-MM-DD: 事象 → 次回の対策」形式で1〜3行追記する。無ければ追記しない。同種の教訓が3回続いたら「★SKILL本体へ昇格候補」と印を付ける。

## 完了報告
Slack DM（自分宛, U0B7FMCR8JU）に報告する。差分が無く書き込みもしなかった日は「変更なし」の1行だけでよい。内容：実行日時（実際の現在時刻を記載。指示文のスケジュール時刻を書かない）／原本差し替え件数／全行数（自作集約2件を含む19行のはず）／台帳からの追加・削除差分。

# ステップ0（必須・最初に1回だけ）: リポジトリと gog/gws を用意する
この定期実行セッションにはリポジトリがクローンされておらず、SessionStart フックも走らない（そのせいで過去の実行は空振りしていた）。
まず次をそのまま実行する（認証用の環境変数3つは環境側に設定済み。gog auth add / gws auth login は絶対に叩かない）:

```bash
R="$HOME/claude-configgggggg"
[ -d "$R/.git" ] || git clone -q --depth 1 https://github.com/yukikatayama3399/claude-configgggggg "$R"
cd "$R"
[ -f routines/bootstrap.sh ] || { git fetch -q --depth 1 origin claude/clever-cannon-593o8s && git checkout -q FETCH_HEAD; }
bash routines/bootstrap.sh
```

以降の Bash 呼び出しは毎回、先頭に `source ~/.routine_env && cd "$REPO" && ` を付ける（シェルの状態は呼び出しごとに消える）。
ブートストラップが失敗したら、「書き込み手段」の TSV 送付にフォールバックする。
今日の日付は必ず `TZ=Asia/Tokyo date +%Y/%m/%d` で取る（cron は UTC なので素の date は前日になることがある）。
`````
