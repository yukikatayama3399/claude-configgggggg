---
name: weekly-shared-notes
description: 自動生成議事録（Gemini自動メモ等）に追記された【共有】マーカー付きメモを「週報で全体共有する特別な事項」として自動で拾い上げ、週報メモDocに反映する。週報（Weekly）の下書き作成、議事録からの要望リスト取得、「共有事項を拾って」「議事録の追記メモを集めて」などの依頼で使う。毎週水曜の HAWK週報 Routine にも組み込まれている。
---

# weekly-shared-notes: 議事録追記メモの週次拾い上げ

## 仕組み（運用ルール）

1. 商談・定例の議事録は Gemini が自動生成する（`議事録_MMDD_〇〇（Gemini自動メモ）` /
   `〇〇 - Gemini によるメモ` 等）。
2. 週報で全体共有したい事項（ユーザー・クライアントからの要望など）が出たら、
   片山がその議事録 Doc に **`【共有】` で始まる行を追記**する。
   - 例: `【共有】A社からAdvantage+レポート対応の要望。優先度高。`
   - マーカーが無い追記メモは拾われない（普通のメモとして扱われる）。
3. 週次（水曜の週報下書き作成時）に、この Skill が直近1週間の議事録から
   `【共有】` 行を横断収集し、週報メモ Doc に反映する。

## 収集（読み取り専用）

```bash
bash weekly/collect_shared_notes.sh            # 直近8日・マーカー【共有】
bash weekly/collect_shared_notes.sh --days 14  # 期間を変える
```

出力は週報にそのまま貼れる Markdown（Doc名・更新日・項目・出典URL）。
0件なら「追記はありません」と1行出る。

スクリプトが手元に無い環境では同等をインラインで行う:
`fullText contains '【共有】' and mimeType = 'application/vnd.google-apps.document'
and trashed = false and modifiedTime > '<8日前RFC3339>'` で gog drive search し、
各 Doc を `gog docs cat` して `【共有】` を含む行を抽出する
（title contains は CJK で効かないので fullText を使う。
追記直後は fullText 索引が遅れることがあるため、
`fullText contains 'Gemini'` の直近更新 Doc も union して本文側で grep する）。

## 反映先（本番は Word ではなくこの Doc）

Google Doc **「【片山】週報メモ」**
`documentId: 1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY`

- 反映先タブ: **t.0**（週報タブ本体）のセクション
  **「6. お客様の声・フィードバック（週報共有用）」** の末尾に
  `■ 議事録拾い上げ（MMDD週・自動）` ブロックとして追記する。
- 書き込みは必ず `gws docs documents batchUpdate`（insertText、location に
  `tabId: "t.0"` を指定）で行う。**gog docs write はタブ指定ができないため使わない**
  （このDocは複数タブ構成。タブ運用は既存の「機能要望ストック」Routine と同じ流儀）。

```bash
# 1) 末尾 index を調べる
gws docs documents get --params '{"documentId":"1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY","includeTabsContent":true}'
# → tabs[] から t.0 の body.content 最終要素の endIndex を取る

# 2) endIndex-1 に挿入
gws docs documents batchUpdate \
  --params '{"documentId":"1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY"}' \
  --json '{"requests":[{"insertText":{"location":{"tabId":"t.0","index":<endIndex-1>},"text":"\n\n■ 議事録拾い上げ（MMDD週・自動）\n・…\n"}}]}'
```

## 週報メモ t.0 の毎週水曜ミラー運用（2026-09-02 決定）

週報メモ（片山メモ）の t.0 は、**毎週水曜に本番「HAWK営業 - 定例会報告書」の
当週タブと同じ内容へ全文更新する**（水曜の HAWK週報 Routine 手順 4c に組込済み）。

- 本番 Doc: `documentId: 1I7u2zNZTPl9tAo2SGalo35ElsDWu2MPpP6JgIYr8LCk`
  （タブは週ごとに `YYYYMMDD`＝定例日の日付。**本番 Doc にこちらから書き込まない**
  ——チーム共有 Doc のため。本番への転記は片山が手動で行う）
- 実行はリポジトリの **`weekly/mirror_report_to_memo.py`** で行う
  （本番と同じフォーマット＝見出しレベル・1x1バナー表・データ表を再現して全文差し替え）:
  ```bash
  python3 weekly/mirror_report_to_memo.py --highlights <ハイライトtxt> [--source-tab YYYYMMDD]
  ```
- t.0 の構成（スクリプトが組み立てる）:
  1. `◆ 週次アップデート（当日日付 水曜更新）` ＋ `■ 今週のハイライト`（5〜8行）
  2. `6. お客様の声・フィードバック（週報共有用）`
     （差し替え前の既存ブロックを自動保全。拾い上げ・新規フィードバックは
     スクリプト実行「前」にこの節へ追記しておくと、そのまま引き継がれる）
  3. 本番当週タブの写し（書式付き）
- 書式は「そのまま本番に貼れるプレーンテキスト」:
  - ブロック見出しは `■ 〇〇社からのフィードバック（MMDD 商談・経緯）`
  - 本文は `・` 箇条書き、結論・提案は `・→ ` で始める
  - Markdown 記法（`**` や `#`）は使わない

数値の裏取りに使う関連シート:
- 失注要件のまとめ: スプレッドシート「提案ステータス」
  `1KbOQJCgxaaAzTcQPmOgTjgYl8bCzZrOGyXhKUnK_ESs` の **`xx_0831週` タブ**
  （クライアント名／ステータス／失注理由 列。週次タブ `MMDD週` は当週分のみ）。
  料金・価格の議論では「全体のうちその理由で落とした案件数」をここから集計する。

## 顧客からの要望まとめ Doc（正本・2026-09-02 新設）

機能要望の積み上げ先は独立 Doc に移行した。**常にこちらを参照・更新する**。
旧・週報メモ内「機能要望ストック」タブ（t.1tg9z5jlttjh）は廃止済み（案内文のみ・書き込み禁止）。

Google Doc **「顧客からの要望まとめ（HAWK・週次更新）」**
`documentId: 12h8p2HA3Zpgp-G7j0filhmVfy9XTxBvX9jMdn0sTJeM`（タブなし＝tabId 指定不要）

- 構成: ①運用ルール → ②`■ ニーズ集計サマリー`（**カテゴリ別**×社数の多い順、
  `・要望名（社名、社名…）… N社 → No.X`）→ ③`■ 週次アップデート`
  （**最新の週が一番上**。見出し直後に `==MMDD週==` ブロックを挿入）→
  ④`■ 要望明細`（カテゴリ別・通し番号 No.1〜）
- カテゴリ: 要件整理・入稿／見積もり・提案／運用／レポート・ダッシュボード／
  クリエイティブ／媒体・外部連携／料金・プラン／管理・セキュリティ
- 正の字方式: 重複する要望は該当 No. に社名・日付・出所を1行追記して社数を更新。
  新規はカテゴリ末尾に通し番号で追加。サマリーは必ず数え直して整合させる。
- 収集源は議事録だけでなく **Slack・Gmail も毎週横断**する。
- 更新タイミングは2つ（どちらも既存内容を読んでから・重複追記禁止）:
  月曜 Routine「『顧客からの要望まとめ』週次更新」（全チャネル横断の本スイープ）と、
  水曜 HAWK週報 Routine の手順 4d（週報作成中に見つけた分の反映）。

## ルール

- **追記前に必ず既存内容を読む**。同一項目が既に載っていれば重複追記しない
  （既出の場合は社名の並記など既存項目側の更新に留める）。
- 0件の週は Doc に何も書かない（収集結果の「なし」を週報下書きにだけ書く）。
- 純粋な「機能要望」は月曜の Routine（機能要望ストック タブ `t.1tg9z5jlttjh`）が
  担当。この Skill が扱うのは **全体共有事項としての拾い上げ**（要望を含むがそれに限らない）。
  同じ内容が両方に載るのは許容（用途が違う）。
- 週報下書き（水曜の HAWK週報 Routine）には、拾い上げた項目をそのまま
  「今週の共有事項」として含める。

## 関連

- 収集スクリプト: `weekly/collect_shared_notes.sh`（読み取り専用）
- 水曜 10:00 JST「HAWK週報」Routine（trig_01H9pNo2RxrpTioqPK3QV9yT）に手順 4b として組み込み済み
- 月曜 9:00 JST「週報メモ『機能要望ストック』週次更新」Routine（trig_015FwE4GCRbtYhjUTgDk7Lax）
