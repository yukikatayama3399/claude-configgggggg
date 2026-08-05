# クラウド Routine から Google Sheets に書けるようにする

## 何が起きていたか

競合ウォッチ Routine が毎日「⚠️台帳未記帳」を出し続け、台帳シートは
**2026-07-30 を最後に記帳が止まっていた**（2026-08-05 に 9 件を手動バックフィル済み）。

原因は Routine のセッションに gog が入っていないこと。

| | |
|---|---|
| Routine が clone するリポジトリ | `yukikatayama3399/claude-config`（旧） |
| そこにあるもの | `.md` メモ類のみ |
| **無いもの** | `setup_gog_remote.sh` / `bin/` の gog tarball / `.claude/hooks/session-start.sh` |

gog セットアップ一式は `claude-configgggggg`（新）にしか無い。
Routine の `sources` は API から変更できないので、**プロンプト側で gog を自前セットアップする**。

MCP の Google Drive コネクタでは代替できない（セル書き込みのツールが無い）。

## エージェントからは直せない

`update_trigger` は `http_api` で作られた Routine を拒否する:

> this routine was created via "http_api", not by an agent.
> Agents can only update routines they created (via create_trigger).

該当する Routine（要手動差し替え）:

- 競合ウォッチ 朝のブリーフィング … `trig_01NbZFsiw8x1tJH6XyPRuAuq`
- hawk-url-index-original-refresh … `trig_01H3eK8s6RAMj3to5SQFpQhi`（同じ症状。TSV を Slack に貼って手動ペーストさせている）

**Claude Code on the web の Routine 設定画面からプロンプトを差し替える**必要がある。

## 再利用できる gog ブートストラップ

Routine プロンプトの冒頭に貼る。3値（`GOG_CREDENTIALS_B64` /
`GOG_TOKEN_EXPORT_B64` / `GOG_KEYRING_PASSWORD`）は環境変数として
環境（Default）に入っているので、セッション側で用意する必要はない。

````markdown
## 手順0. gog セットアップ（Sheets の読み書きに必須。最初に必ず実行する）

このセッションには Google Sheets に書き込める MCP ツールが無い。gog (gogcli) を使う。
セットアップスクリプトが無いリポジトリなので、以下を Bash で直接実行する。

```bash
set -e
for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64 GOG_KEYRING_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "MISSING:$v"; exit 1; }
done
mkdir -p "$HOME/bin" "$HOME/.config/gogcli"
if ! command -v gog >/dev/null 2>&1; then
  curl -fsSL -o /tmp/gog.tgz https://github.com/openclaw/gogcli/releases/download/v0.19.0/gogcli_0.19.0_linux_amd64.tar.gz
  tar -xzf /tmp/gog.tgz -C /tmp
  install -m 0755 /tmp/gog "$HOME/bin/gog"
fi
export PATH="$HOME/bin:$PATH"
export GOG_KEYRING_BACKEND=file
gog auth keyring file --no-input >/dev/null 2>&1 || true
echo "$GOG_CREDENTIALS_B64" | base64 -d > "$HOME/.config/gogcli/credentials.json"
chmod 600 "$HOME/.config/gogcli/credentials.json"
gog auth credentials set "$HOME/.config/gogcli/credentials.json" --no-input
echo "$GOG_TOKEN_EXPORT_B64" | base64 -d > /tmp/tok.json
gog auth tokens import /tmp/tok.json --no-input --force
rm -f /tmp/tok.json
gog auth doctor --check --no-input
```

以降 gog を使うときは毎回 `export PATH="$HOME/bin:$PATH"` を先に入れる。
グローバルフラグはサブコマンドの「前」に置く（後ろだと unknown flag）。
セットアップに失敗した場合だけ、従来の代替（Slack へ貼り付け用テキストを出す）に倒す。
````

疎通は 2026-08-05 に確認済み（GitHub Releases への curl は HTTP 200、
このリポジトリのクラウドセッションから実 API 書き込みも成功）。

## 競合ウォッチ：差し替え後のプロンプト全文

`trig_01NbZFsiw8x1tJH6XyPRuAuq` のプロンプトをこれで丸ごと置き換える。
変更点は3か所だけ（手順0の追加 / 手順1b を gog 読みに / 手順5 を gog 書きに）。
監視対象リストと投稿フォーマットは元のまま。

---

あなたはHAWK競合ウォッチ担当のリサーチアシスタントです。以下を順に実行してください。

背景：ユーザー（片山優希）はフリークアウトでSNS/Meta広告運用AIエージェント「HAWK」を拡販している。監視目的はHAWKの競合・隣接プレイヤーの新発表の早期検知。

## 手順0. gog セットアップ（台帳の読み書きに必須。最初に必ず実行する）

このセッションには Google Sheets に書き込めるMCPツールが無い。台帳の読み書きは gog (gogcli) で行う。
このリポジトリには gog のセットアップスクリプトが無いので、以下を Bash で直接実行してセットアップする。

```bash
set -e
# 3つの環境変数が無ければ gog は使えない。その場合はセットアップを諦めて手順5の代替に進む。
for v in GOG_CREDENTIALS_B64 GOG_TOKEN_EXPORT_B64 GOG_KEYRING_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "MISSING:$v"; exit 1; }
done
mkdir -p "$HOME/bin" "$HOME/.config/gogcli"
if ! command -v gog >/dev/null 2>&1; then
  curl -fsSL -o /tmp/gog.tgz https://github.com/openclaw/gogcli/releases/download/v0.19.0/gogcli_0.19.0_linux_amd64.tar.gz
  tar -xzf /tmp/gog.tgz -C /tmp
  install -m 0755 /tmp/gog "$HOME/bin/gog"
fi
export PATH="$HOME/bin:$PATH"
export GOG_KEYRING_BACKEND=file
gog auth keyring file --no-input >/dev/null 2>&1 || true
echo "$GOG_CREDENTIALS_B64" | base64 -d > "$HOME/.config/gogcli/credentials.json"
chmod 600 "$HOME/.config/gogcli/credentials.json"
gog auth credentials set "$HOME/.config/gogcli/credentials.json" --no-input
echo "$GOG_TOKEN_EXPORT_B64" | base64 -d > /tmp/tok.json
gog auth tokens import /tmp/tok.json --no-input --force
rm -f /tmp/tok.json
gog auth doctor --check --no-input
```

以降 gog を使うときは毎回 `export PATH="$HOME/bin:$PATH"` を先に入れること。
グローバルフラグはサブコマンドの前に置く（`gog --account ... sheets get ...`）。後ろだと unknown flag になる。
セットアップに失敗した場合だけ、手順5の代替（⚠️台帳未記帳）に倒す。成功したら必ず台帳へ書くこと。

## 監視対象（このリストが正であり、外部ファイルは読まない）
1. AIエージェント・自然言語広告運用【毎日】:
   Shirofune / Smartly(Synapse含む) / CyberAgent効果おまかせAI / JAPAN AI MARKETING /
   ラクアドAI / Picaro.AI / スニフアウト / ExpreTech / NoimosAI / AdMarket(JPC) /
   SynergyAIマカセルくん / Ryze AI
2. 予算管理・入札最適化・運用自動化【毎日】:
   Optmyzr / Skai / Marin Software / Fluency / Madgicx / Revealbot
3. 広告クリエイティブ自動生成（運用一体型）【毎日】:
   AdCreative.ai / Omneky / Pencil / リチカ / CA極予測AI / SHORTBOOSTER
4. 新媒体・媒体純正AI【毎日】:
   ChatGPT広告(OpenAI)エコシステム（出稿支援を発表する代理店含む） /
   Meta Advantage+ / Google P-MAX / TikTok Smart+
   ※「ツール不要化」圧力・対応媒体格差の観点で監視
5. レポート自動化・周辺【月曜のみ調査】:
   Databeat Explore / ATOM / アドレポ / glu / Roboma / Supermetrics / Funnel /
   NinjaCat / AgencyAnalytics / Whatagraph / dfplus.io / コマースフロー / ニフティライフスタイルDFO

## 手順
1. 【重複排除・必須】投稿前に次の2つを必ず読む:
   a. Slackチャンネル #competitor-watch（channel_id: C0B9NH3JUTS）の直近14日分の投稿
   b. 投稿済み台帳シート（Google Sheets ID: 1eL80eA0_awTm6boaCrMWIRq4mN1Vk8l7d9McDwlPwEE / タブ名 `Untitled`）
      読み方: `gog --account yuki.katayama@fout.jp sheets get 1eL80eA0_awTm6boaCrMWIRq4mN1Vk8l7d9McDwlPwEE "Untitled!A1:F200" -p`
      列は 掲載日 / 社名・ツール名 / 発表タイトル/内容 / 発表日 / カテゴリ / 出典URL。掲載日の降順（新しい行が上）。
   →「社名×発表内容」または出典URLがどちらかに一致する項目は掲載禁止。
   同じ発表の続報・再掲・「継続ウォッチ」枠は禁止。同一社でも掲載できるのは未掲載の新しい発表があるときのみ。
2. WebSearchで各社の「料金・機能・プレス/発表・資金調達」の過去1週間の差分を調べる。
   カテゴリ5は月曜のみ調査する。リスト未掲載の新規参入（同カテゴリ）も拾う。
3. 掲載基準: 発表日が過去7日以内 かつ 手順1で未掲載と確認できたもののみ。
   誤報を避け、不確かな情報は推測で書かない（必ず出典を確認）。
4. #competitor-watch に slack_send_message で投稿する。フォーマット:
   - 1行目:『🔍 競合ウォッチ（YYYY/MM/DD JST）』
   - 各項目: 社名｜発表日｜内容2〜3行｜HAWKとの差別化観点1〜2行｜出典URL（タイトル＋URLをそのまま貼る）
   - 新着ゼロのカテゴリは見出しごと省略。全カテゴリゼロの日は
     『🔍 競合ウォッチ（YYYY/MM/DD JST）: 本日新着なし』の1行のみ投稿。
   - リスト未掲載の新規参入は【追記提案】として社名・概要・出典URLを含める
     （監視対象リストへの反映はユーザーが判断する。ファイルやリポジトリは一切編集しない）。
5. 【投稿後・必須】掲載した全項目（追記提案・新着なし以外）を台帳シートに記帳する。
   **台帳は掲載日の降順なので、末尾に append せず先頭（2行目）に挿入すること。**

   ```bash
   export PATH="$HOME/bin:$PATH"
   SID=1eL80eA0_awTm6boaCrMWIRq4mN1Vk8l7d9McDwlPwEE
   N=<今回書く行数>
   gog --account yuki.katayama@fout.jp sheets insert "$SID" "Untitled" rows 2 --count "$N" --no-input
   gog --account yuki.katayama@fout.jp sheets update "$SID" "Untitled!A2:F$((N+1))" \
     --values-json '[["掲載日","社名","発表タイトル/内容","発表日","カテゴリ","URL"], ...]' \
     --input USER_ENTERED --no-input
   ```

   - 掲載日・発表日は `YYYY-MM-DD` 形式（USER_ENTERED で日付として入る。既存行と揃う）。
   - カテゴリは既存行で使われている値を優先して流用する
     （例: AIエージェント運用 / 予算管理・運用自動化 / クリエイティブ自動生成 / 新媒体ウォッチ / フィード管理 / 周辺トレンド）。
   - 書いたら `sheets get "Untitled!A1:F12" -p` で読み返し、行数と並び順が意図どおりか検証する。
   - 手順0のセットアップに失敗した等で本当に書けなかった場合のみ、投稿の末尾に
     『⚠️台帳未記帳』と、未記帳の項目を明記する。書けたなら絶対にこの警告を出さない。

注意: すべて日本語で出力。最終的に必ず #competitor-watch へ投稿し、台帳記帳まで完了させること。

---

## 台帳シートの実測メモ（2026-08-05）

| 項目 | 値 |
|---|---|
| spreadsheetId | `1eL80eA0_awTm6boaCrMWIRq4mN1Vk8l7d9McDwlPwEE` |
| タイトル | competitor-watch_投稿済み台帳 |
| タブ名 | `Untitled`（1枚のみ） |
| 列 | 掲載日 / 社名・ツール名 / 発表タイトル/内容 / 発表日 / カテゴリ / 出典URL |
| 並び | 掲載日の**降順**（新しい行が上）。append ではなく2行目に insert する |
| 日付セル | 文字列ではなく**日付**（例: 2026-07-30 = シリアル 46233）。`--input USER_ENTERED` で揃う |
