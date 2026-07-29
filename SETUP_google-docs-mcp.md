> # ⚠️ この手順書は不要になりました（2026-07-29）
>
> **この作業をやる必要はありません。Composio への登録も課金も不要です。**
>
> 前提だった「既存の Google ドキュメントへ直接編集ができない」という制約は、
> **gog で解消済み**です。実測で確認しました:
>
> - `gog docs find-replace <docId> <find> <replace>` → 既存 Doc を直接置換できる（`replacements 1`）
> - `gog docs write` / `edit` / `sed` / `format` も既存 Doc に対して動く
> - 原本ピッチ台本（`1KFHlRcc...`）も `gog docs cat` で読み取り可能
>
> したがって「新規ドキュメント作成＋手動貼り付け」の運用も不要です。
> 使い方は `CLAUDE.md` を参照してください。
>
> 未確認の点: 原本ピッチ台本は共有ドライブ上にあり、書き込み権限は
> 共有ドライブのメンバー権限に依存します。読み取りは確認済みですが、
> 書き込みは実際に書いてみるまで断定できないため、原本には手を出していません。
> 原本を編集させたい場合はその旨を指示してください。
>
> 以下は歴史的経緯として残しています。**実行しないでください。**

---

# Googleドキュメント編集MCPの有効化手順（Composio）※廃止

## なぜ必要か（※当時の前提。現在は gog で解決済み）
- 現在この実行環境のGoogle Drive連携は「読み取り／新規作成／コピー」のみで、**既存のGoogleドキュメント（例：HAWK_ピッチ台本_1st&2nd_FAQ）への直接編集ができない**。
- そのため、FAQへの追記は今は「新規ドキュメント作成＋手動貼り付け」で運用している。
- 既存Docを直接編集できるようにするには、Google Docs編集対応の外部MCPを1つ追加する必要がある。

## ⚠️ Claudeが自動でできなかった部分
`.mcp.json`（エージェントの起動設定）への書き込みは、ハーネスのセキュリティ層が「自己改変」としてブロックする。チャットでの口頭許可では解除されないため、**下記「手順4」のファイル作成は片山さんが行う**（または settings に Write/Bash の許可ルールを追加して明示的に解禁する）。

---

## 手順（片山さんの作業・一度きり）

1. **Composio に登録**：https://composio.dev
2. **「Google Docs」ツールキットを追加**し、原本を編集できるGoogleアカウント（`yuki.katayama@fout.jp`）を OAuth 接続（同意）する。
3. 発行される **「MCP URL」** と **「APIキー」** を控える。
4. **リポジトリ直下に `.mcp.json` を作成**し、以下を貼る（APIキーは平文で書かず環境変数で渡す）：

   ```json
   {
     "mcpServers": {
       "google-docs": {
         "type": "http",
         "url": "${GOOGLE_DOCS_MCP_URL}",
         "headers": {
           "X-API-Key": "${GOOGLE_DOCS_MCP_API_KEY}"
         }
       }
     }
   }
   ```

   ※ Composio以外（Pipedream / Zapier 等で「単一URLにトークン内蔵」型）の場合は `headers` 行は不要。URLだけにする。

5. **この実行環境の「環境変数」に設定**：
   - `GOOGLE_DOCS_MCP_URL` = （Composio の MCP URL）
   - `GOOGLE_DOCS_MCP_API_KEY` = （Composio の APIキー）
6. **セッションを再起動**する（新セッションはこのブランチ上で開始するか、このブランチを既定ブランチへマージしてから開始）。
7. 初回利用時に Google の OAuth 同意画面が出たら許可する。

---

## 再起動後、Claudeに貼る指示（コピペ用）

> google-docs MCP が有効になっています。原本Doc（ID: `1KFHlRccC-bdgXFVcW4i1NyVo8Gsi1bgsB6_7BgXYA-A`／HAWK_ピッチ台本 TAB3）に、
> `HAWK_FAQ_オンボーディング編_TAB3追加候補_20260611.md`（= Googleドキュメント `1r3qcaC7oU3horEN6Ilfj890_jIyi8fjXqjuLK4Nh1Bo`）の
> 「レベル2.7：オンボーディング編」セクションを追記してください。既存の本文は消さないこと。

---

## 関連ファイル
- ピッチ台本（追記先・原本）：`1KFHlRccC-bdgXFVcW4i1NyVo8Gsi1bgsB6_7BgXYA-A`
- オンボーディング編FAQ（追記元・Doc）：`1r3qcaC7oU3horEN6Ilfj890_jIyi8fjXqjuLK4Nh1Bo`
- 議事録まとめ（Doc）：`1rj_q1V-nirtm3SuirqBmvgEm0LKsOpuqhqQ_6012aGA`
