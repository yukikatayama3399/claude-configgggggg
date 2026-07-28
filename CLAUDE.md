# claude-configgggggg

## HAWK 商談資料の「正」【正本】

商談準備・仮予定への添付・メール下書きで HAWK の資料を出すときは、**必ずここを正とする**。
「HAWK関連資料 URL一覧集」台帳（`1dnSL89LwWqYN-IxFlb-YX7IoKSNSjAVhRpJSxrwefa8`）には
**載っていない資料があるため、台帳だけを見ると取り違える。**

| 資料 | ID | 備考 |
|---|---|---|
| **HAWK Overview 202607版**（媒体資料／ピッチ） | `presentation/d/1rvFIO3jDTaI6Dif6-mRpwMb55xI1Uy-JRVx18dJpw30` | **★これが正**（本人指定 2026-07-28）。台帳未登録 |
| HAWK_ピッチ台本_1st&2nd_FAQ（社内用・先方共有不可） | `document/d/1KFHlRccC-bdgXFVcW4i1NyVo8Gsi1bgsB6_7BgXYA-A` | |
| HAWK入稿用テキストテンプレート | `document/d/1syzwx6PsZDSFC9lNC9_kanK1lT6ZkB17A97EwjWGsN0` | 「入稿用テンプレ」「カスタムテンプレート」 |
| HAWK_METAインサイトレポート_demo用 | `presentation/d/1qfWAIBUkxQ4OfoSCis6-Y0ltySMF7slsw8eSy-oMaIs` | 「リカート」「カスタムレポート」 |
| hawk_product_demo（デモ映像） | `drive.google.com/file/d/1RTV8UCMpPipkbiiMtPq1uq1hylXtYmtS` | |

**使ってはいけない旧Overview**（過去の定義ファイルに残っていることがある）:
`1jNYfsyb…` ／ `1YO2Lmgs…（HAWK Overview 05182026）`

Overview が差し替わったら本人にIDを確認し、**この表**と
`~/.claude/skills/hawk-shodan-prep/SKILL.md`「固定値」、
`~/.claude/skills/hawk-inbound-lead/SKILL.md`「前提・固定値」＋
`~/.claude/skills/hawk-inbound-lead/references/templates.md`「標準添付セット【正本】」
を**まとめて更新する**（スキル側はコンテナ再作成で消えるため、この表が最終的な拠り所）。

## Google Workspace 操作は gog を最優先で使う

Google Sheets / Docs / Calendar / Gmail / Drive などの Google Workspace 操作は、
**原則 gog (gogcli) を最優先で使う**こと。

理由:
- MCP の Google 連携（Google Drive コネクタ等）は読み取り中心で、
  Sheets のセル書き込みや Docs 本文書き込みのツールが無い。**書き込みが絡むタスクは gog を使う。**
- gog はスコープに sheets / docs / drive(full) 等を保有しており、
  Drive 権限があれば他人所有ファイルにも読み書きできる（検証済み）。

### セットアップ
- クラウド(web)セッションでは SessionStart フック
  (`.claude/hooks/session-start.sh`) が開始時に自動セットアップする。
- 手動で使う場合: `bash setup_gog_remote.sh`

### 使い方の基本
- アカウント指定: `--account yuki.katayama@fout.jp`
- 読み取り専用にしたい時: `--readonly`
- JSON 出力: `-j`

### よく使う例
```bash
# Sheets 読み
gog --account yuki.katayama@fout.jp sheets get <ID> "<タブ名>!A1:C3"
# Sheets 書き
gog --account yuki.katayama@fout.jp sheets update <ID> "<タブ名>!W1633" "値"
# Docs 読み
gog --account yuki.katayama@fout.jp docs cat <docId>
# Docs 書き
gog --account yuki.katayama@fout.jp docs write <docId> --text "本文"
```
