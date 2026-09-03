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

## ルール

- **追記前に必ず既存内容を読む**。同一項目が既に載っていれば重複追記しない
  （既出の場合は社名の並記など既存項目側の更新に留める）。
- 0件の週は Doc に何も書かない（収集結果の「なし」を週報下書きにだけ書く）。
- 純粋な「機能要望」は正本 Doc「顧客からの要望まとめ（HAWK・週次更新）」
  （documentId: `12h8p2HA3Zpgp-G7j0filhmVfy9XTxBvX9jMdn0sTJeM`）と
  水曜 9:00 JST の週次更新 Routine が担当（詳細は `hawk-customer-requests` スキル）。
  旧「機能要望ストック」タブ（`t.1tg9z5jlttjh`）は**廃止済みで書き込み禁止**。
  この Skill が扱うのは **全体共有事項としての拾い上げ**（要望を含むがそれに限らない）。
  同じ内容が両方に載るのは許容（用途が違う）。
- 週報下書き（水曜の HAWK週報 Routine）には、拾い上げた項目をそのまま
  「今週の共有事項」として含める。

## 関連

- 収集スクリプト: `weekly/collect_shared_notes.sh`（読み取り専用）
- 水曜 10:00 JST「HAWK週報」Routine（trig_01H9pNo2RxrpTioqPK3QV9yT）に手順 4b として組み込み済み
- 水曜 9:00 JST「顧客からの要望まとめ」週次更新 Routine（trig_015FwE4GCRbtYhjUTgDk7Lax）
  ／`hawk-customer-requests` スキル（機能要望の正本 Doc 更新と週報転記）
