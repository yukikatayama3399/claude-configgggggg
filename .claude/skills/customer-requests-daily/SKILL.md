---
name: customer-requests-daily
description: 顧客からの要望（「こんなことできますか？」「〜が欲しい」など、現在HAWKに無い／できないと回答した機能・仕様・料金・媒体）を、Gemini自動メモ・Meet文字起こし・整理版議事録・顧客メールから毎日拾い上げ、正本Doc「顧客からの要望まとめ（HAWK・毎日更新）」に反映する。「顧客要望をアップデートして」「〇〇社の議事録から要望を拾って」「要望まとめDocを更新」「開発要望をリストアップ」などの依頼と、毎日21:00 JSTの Routine「「顧客からの要望まとめ」日次更新」で使う。書き込みは gws docs batchUpdate（gog docs write は使わない）。
---

# customer-requests-daily: 顧客要望の日次拾い上げ

## 目的

正本 Google Doc **「顧客からの要望まとめ（HAWK・毎日更新）」**
`documentId: 12h8p2HA3Zpgp-G7j0filhmVfy9XTxBvX9jMdn0sTJeM`
を、顧客接点から毎日更新する。旧「週次更新」は 2026-09-10 に日次へ切り替えた。

拾う対象は **「現在HAWKに機能として無い／できないと回答したもの」** に限る（大小問わず）。
仕様確認だけの質問や既に対応済みの機能は拾わない。当社の回答（開発中／不可／代替案）も一緒に記録する。

## 収集源（すべて読み取り専用・4種類）

| # | 収集源 | 読み方 |
|---|---|---|
| a | Gemini 自動メモ Doc（名前に「Gemini によるメモ」） | **「メモ」タブと「文字起こし」タブの両方**を読む。`gws docs documents get --params '{"documentId":"<id>","includeTabsContent":true}'`。`gog docs cat` は先頭タブしか返さないので使わない |
| b | Meet の文字起こし | a のDocの「文字起こし」タブ（別Docにはならない）。要望は概要タブに載らないことが多いので必ず全文読む |
| c | 整理版議事録 Doc（名前が「議事録_MMDD_」で始まる） | `10_顧客/<社名>/1_議事録` 配下。`gog docs cat` 可 |
| d | 顧客（社外ドメイン）からの受信メール | `gog gmail search "<社名 or 担当者名> newer_than:1d"` → `gog gmail thread get <threadId>`。**メールにしか無い要望がある**（例: 9/9 ドリームネクサス「レポートコメントにチャットで質問できる機能はあるか」） |

### Drive 検索クエリ

`title contains` は CJK で効かないので **fullText** を使う。日次 Routine では前日 21:00 JST 以降の更新分に絞る。

```bash
SINCE=$(date -u -d "yesterday 12:00" +%Y-%m-%dT%H:%M:%SZ)   # 前日21:00 JST
gws drive files list --params "{\"q\":\"(fullText contains 'Gemini によるメモ' or fullText contains '議事録_') and mimeType = 'application/vnd.google-apps.document' and trashed = false and modifiedTime > '$SINCE'\",\"pageSize\":50,\"orderBy\":\"modifiedTime desc\",\"fields\":\"files(id,name,modifiedTime,parents)\",\"supportsAllDrives\":true,\"includeItemsFromAllDrives\":true,\"corpora\":\"allDrives\"}"
```

社名指定で遡る場合は `fullText contains '<社名>'` を追加し、
`10_顧客/<社名>/1_議事録` フォルダを `'<folderId>' in parents` で直接列挙するのが確実。

### タブ抽出（Python 例）

```python
import json,subprocess
d=json.loads(subprocess.run(['gws','docs','documents','get','--params',
    json.dumps({"documentId":DOC,"includeTabsContent":True})],capture_output=True,text=True).stdout)
for t in d['tabs']:
    title=t['tabProperties']['title']          # 'メモ' / '文字起こし'
    body=t['documentTab']['body']['content']
    text=''.join(r.get('textRun',{}).get('content','')
                 for e in body if 'paragraph' in e
                 for r in e['paragraph'].get('elements',[]))
```

## 反映先 Doc の運用ルール（Doc 冒頭の記載と同じ・厳守）

- **書く前に必ず既存本文を全文読む**（重複追記を防ぐ）。
- 既存 No. に該当すれば **社名を並記して社数を更新**（正の字方式）。該当が無ければ **末尾 No. の次番号で新設**。新設はサマリー行＋明細ブロックの両方に書く。
- 新規追加・社数更新の行は行頭に **【MM/DD】**。
- **「■ 日次アップデート（最新の日が上）」** の直下に当日ブロック `==MMDD（曜）==` を挿入し、社名・出典（議事録／文字起こし／メール）・反映先 No. を書く。
- サマリーはカテゴリ内で社数の多い順を保つ（要件整理・入稿／見積もり・提案／運用／レポート／クリエイティブ／媒体・外部連携／料金・プラン／管理・セキュリティ）。
- **0件の日**は `==MMDD（曜）== ・新規要望なし（確認: 議事録N本／文字起こしN本／メールN件）` の1行だけ追記する。
- 社数が **2社以上**になった項目は、【片山】週報メモ（`1BtxjIh0NptD52-M8OpmsQrFsRfFElKMU7wtzAtYM6lY`）tabId `t.0` の
  「6. お客様の声・フィードバック」内「■ 顧客要望サマリー（2社以上の声・週報共有用）」にも反映する（既出なら社名追記のみ）。
- 既存行の削除はしない。出典が示せない要望は書かない。

## 書き込み方法（gws docs batchUpdate）

複数タブDocへの書き込みは `gog docs write` ではタブ指定ができないので **必ず gws を使う**。
要望まとめDocは単一タブだが、同じ流儀で統一する。

1. `documents get` で段落ごとの `startIndex/endIndex/text` を取り、アンカー行（一意な先頭文字列）を特定する。
2. 追記は「アンカー段落の `endIndex - 1`」に `"\n" + 新しい行` を insertText。
   複数箇所に挿入するときは **index 降順に並べて1回の batchUpdate** にする（前方の挿入で後方の index がずれるのを防ぐ）。
3. 社数更新など既存行の書き換えは **replaceAllText**（`matchCase: true`、置換前に本文中で1件だけ一致することを確認）。
   insertText と replaceAllText は別の batchUpdate に分ける（insert → replace の順）。
4. 書いた後に `documents get` で読み返し、件数（`No.NN` の出現回数など）を確認する。

```bash
gws docs documents batchUpdate \
  --params '{"documentId":"12h8p2HA3Zpgp-G7j0filhmVfy9XTxBvX9jMdn0sTJeM"}' \
  --json '{"requests":[{"insertText":{"location":{"tabId":"t.0","index":<endIndex-1>},"text":"\n【MM/DD】・…"}}]}'
```

実装例: 2026-09-10 セッションの `update_req_doc.py`（アンカー検出→降順 insert→replace→検証の一連）。

## 完了報告

新設／更新した No.・社名・確認した件数（議事録／文字起こし／メール）・Doc URL を短く報告する。
開発要望として上げる「実現できなかったもの」は表（No.／要望／社／現状回答）で示す。

## 関連

- Routine: 「「顧客からの要望まとめ」日次更新（毎日21:00 JST）」 `trig_015FwE4GCRbtYhjUTgDk7Lax`（cron `0 12 * * *`）
- 週報側の拾い上げ（【共有】マーカー）: `.claude/skills/weekly-shared-notes/SKILL.md`（水曜 HAWK週報 Routine `trig_01H9pNo2RxrpTioqPK3QV9yT`）。
  週報の「参照URL」一覧には本Docのリンクを載せる。
- 禁止: `gog auth add` / `gws auth login`、メール送信、Doc 既存行の削除。
