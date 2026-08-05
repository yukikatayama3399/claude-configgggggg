# SNS・インフルエンサー イベントレーダー

東京のインフルエンサー企業 / SNS 運用代行企業などが開催する
**勉強会・セミナー・交流会**を毎朝拾って、Slack の自分宛 DM に流すルーティン。

| 項目 | 値 |
|---|---|
| Routine ID | `trig_013oTonFuJxWfofKWVS8KL1G` |
| 実行タイミング | 毎日 **8:00 JST**（cron `0 23 * * *` = UTC） |
| 実行形態 | 毎回まっさらな新規セッション（`create_new_session_on_fire=true`） |
| モデル | ⚠️ **未設定**（下記「残作業」参照。安いモデルに変える必要あり） |
| 通知先 | Slack 自分宛 DM `U0B7FMCR8JU`（DM チャンネルは `D0B6P80CF6D`） |
| 重複排除の台帳 | [通知ログ スプレッドシート](https://docs.google.com/spreadsheets/d/1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4/edit) |
| Sheet ID | `1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4` |

## 🚧 残作業（これをやるまで DM は飛ばない）

Routine は登録済みだが、**MCP ツールの実行ができないので現状は動かない**。
下記 2 点はどちらも API 側で拒否されたため、
**claude.ai の Routines UI から手で設定する必要がある**。

| やること | なぜ API で出来ないか |
|---|---|
| **① Slack コネクタを紐付ける** | `create_trigger` の `connectors` が `not available for this organization` で拒否される。コネクタ無しで作られた Routine の発火セッションには `mcp__Slack__*` が無く、DM を送れない（2026-08-05 のテスト発火で無反応を確認） |
| **② モデルを安いものに変える** | `update_trigger` の `model` が `model_update_disabled` で拒否される |

①が終わるまでは DM も台帳追記も動かない。②は動作には影響しないがコストに効く。

> Slack コネクタが紐付かない場合の代替案: Slack への直接 HTTP も
> egress ポリシーで塞がれている（`hooks.slack.com` / `slack.com` ともに 403）ため、
> Webhook による回避は**できない**。その場合は既存の HAWK 系ルーティンと同じく
> **Mac ローカル cron 方式**（`scheduled-task-routine` スキル）に載せ替えるのが早い。

> **このファイルが手順の正**。内容を変えたら `update_trigger` で
> Routine の prompt にも反映すること。Routine は毎回まっさらな新規セッションで
> 起動するので、prompt 自体が自己完結している必要がある。

---

## ⚠️ 最大の制約: 外部サイトに直接アクセスできない

この環境の egress ポリシーは**一般 Web ホストへの接続を全面ブロック**している。
2026-08-05 に実測した結果:

| 手段 | 結果 |
|---|---|
| `curl` / Bash | ❌ 全滅。`example.com` すら `CONNECT tunnel failed, response 403` |
| `WebFetch` | ❌ 全滅。kokuchpro / techplay / peatix / connpass / hottolink / comnico すべて 403 |
| **`WebSearch`** | ✅ **これだけ通る**（Anthropic 側の経路を通るため） |

したがって **情報源は WebSearch のみ**。イベント一覧ページを開いて
パースする方式は使えない。検索結果のタイトル＋要約から拾う。

### 精度を上げたいなら（任意）

Claude Code on the web の**環境のネットワークポリシー**で下記ホストを許可すると、
`WebFetch` で一覧ページを直接読めるようになり、東京オフラインの交流会まで
拾えるようになる（今は検索に出やすいオンライン企業セミナーに偏る）。

```
www.kokuchpro.com
peatix.com / feature.peatix.com
connpass.com
techplay.jp
doorkeeper.jp
www.hottolink.co.jp
www.comnico.jp
```

設定は https://code.claude.com/docs/en/claude-code-on-the-web を参照。
許可したら、この手順書の「探す」節を WebFetch ベースに書き換えること。

---

## 手順

### 1. 台帳を読む（重複排除の準備）

```bash
gog --account yuki.katayama@fout.jp sheets get \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A2:I" -p
```

列は `通知日 / イベント名 / 開催日 / 形式 / 会場・オンライン / 主催 / 費用 / 申込URL / 一言メモ`。
**申込URL 列が既出判定のキー**。ここに載っている URL のイベントは新着として扱わない。
URL が同じでもイベント名と開催日が違えば別イベント（企業の一覧ページ URL を
使い回す主催者があるため、名前＋開催日でも突き合わせる）。

gog が使えない場合（トークン切れ等）は、DM 履歴を
`slack_read_channel(channel_id="U0B7FMCR8JU", limit=60)` で読んで代替判定する。
その場合も DM は必ず送る（黙って止まらない）。

### 2. イベントを探す（WebSearch のみ）

日付が変わるので**毎回検索し直す**。検索クエリは年月を明示的に含めること
（含めないと過去のイベントばかり返る）。当月と翌月の 2 パターン投げる。

クエリ例:

- `"2026年8月" SNSマーケティング セミナー 東京 無料 申込 インフルエンサー`
- `"2026年9月" マーケター 交流会 東京 懇親会 SNS 申込 Peatix`
- `"2026年8月" インフルエンサーマーケティング 勉強会 東京 申込`
- `<社名> セミナー "2026年9月" 申込` （下記の社名リストを回す）

**狙う主催者**（実際にセミナーを定期開催していて検索に出るのを確認済み）

- 株式会社ホットリンク — https://www.hottolink.co.jp/event/
- 株式会社コムニコ — https://www.comnico.jp/sns-seminar
- 株式会社THECOO — https://bizpartner.thecoo.co.jp/seminar
- Find Model（ソーシャルワイヤー） — https://find-model.jp/insta-lab/entry-seminar/

**その他の狙い目社名**（URL は推測せず、社名 + 「セミナー」で検索してから当たる）:
サイバー・バズ / テテマーチ / SAKIYOMI / LIDDELL / トリドリ / BitStar /
Natee / UUUM / CANDEE / ガイアックス。

**イベントサイト**は検索経由でしか見えないが、`site:` 的にサイト名を
クエリに足すと拾える: こくちーずプロ / Peatix / connpass / TECH PLAY / Doorkeeper。

### 3. 絞り込む

**含める**

- 開催日が **今日〜60日先**
- 東京都内のオフライン開催 **または** オンライン開催（ウェビナー）
- テーマが SNS マーケ / インフルエンサー施策 / ショート動画 / UGC /
  TikTok・Instagram・YouTube 運用 / SNS 運用代行 / クリエイターエコノミー /
  マーケター交流会・懇親会 のいずれか
- **有料でも可**。ただし 3 万円超は費用欄に `⚠️高額` を付ける

**除外する**

- 情報商材・副業勧誘・MLM・「月収◯◯万」系の匂いがするもの
- 学生／就活限定、特定資格保有者限定など対象外のもの
- 東京以外のオフライン開催（オンライン併催なら可）
- 開催日が特定できないもの（常時申込の資料 DL・個別相談会など）
- **申込 URL が特定できないもの**（リンクが無いと動けないので載せない）
- 台帳に既出のもの

**上限 8 件**。多い時は「開催が近い順 → 交流会要素があるもの優先」で切る。
切り捨てた件数と理由は DM 末尾に 1 行で明記する（黙って落とさない）。

**新着が 1 件でも DM を送る。**「少ないからまとめて明日」はしない。

WebSearch の要約は情報が古い / 曖昧なことがある。**日時・費用を断定できない項目は
推測で埋めず「要確認」と書く**。捏造するくらいなら空欄にする。

### 4. リマインド分を拾う

台帳の**通知済みイベント**のうち、**開催日が今日〜3日以内**のものを拾う。
「そろそろ申し込んだ？」のリマインドとして DM の後半に載せる。

### 5. Slack DM を送る

`slack_send_message(channel_id="U0B7FMCR8JU", message=...)`。

**新着もリマインドも 0 件のときだけ DM を送らない**（無意味な毎朝通知を避ける）。
その場合は台帳への追記も不要。

フォーマット:

```
:mega: *SNS/インフルエンサー イベントレーダー* — 8/5(水)
新着 3 件

*1. 〈イベント名〉*
🗓 8/20(木) 19:00–21:00 ／ 💴 無料 ／ 📍 渋谷（オフライン・懇親会あり）
🏢 株式会社◯◯
📝 〈一言サマリ。何が学べて誰が来るか〉
🔗 https://...

*2. …*

---
:alarm_clock: *開催が近い（通知済み）*
・8/7(金) 〈イベント名〉 → https://...
```

- 交流会・懇親会があるものは 📍 行に「懇親会あり」と明記する
- オンラインは 📍 を「オンライン」にする
- 日付は必ず `M/D(曜)` 形式。曜日は `date -d <YYYY-MM-DD> +%a` で確認する

### 6. 台帳に追記する

DM に載せた**新着分のみ**を追記する（リマインド分は追記しない）。

`--values-json` で 2 次元配列を渡すこと。位置引数で並べると
**全部 1 セルに連結されてしまう**（実測済み）。複数件は配列に並べれば 1 回で入る。

```bash
gog --account yuki.katayama@fout.jp sheets append \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A:I" \
  --values-json '[["2026-08-05","イベント名","2026-08-20","オフライン","渋谷","株式会社◯◯","無料","https://...","一言メモ"]]'
```

DM 送信 → 台帳追記の順にする。逆にすると、DM 送信に失敗した時に
「台帳には載っているが通知されていない」イベントが生まれて二度と通知されない。

---

## メンテナンス

- Routine の一覧・ID 確認: `list_triggers`
- 文面や頻度を変える: `update_trigger`（run 履歴が残るので削除→再作成より good）
- モデルを変える: `update_trigger` の `model`
- 止める: `update_trigger` で `enabled=false`、完全撤去は `delete_trigger`
- 手動で今すぐ流したい: `fire_trigger`

### コストを下げる打ち手

1. **モデル**: Sonnet 5 で運用中。さらに削るなら Haiku 4.5 に落とせるが、
   情報商材の除外判断など「匂いを嗅ぐ」精度が落ちるのでノイズが増える見込み。
2. **検索回数**: 手順 2 のクエリを増やすほど線形にコストが増える。
   現状は 3〜6 本を目安にする。
3. **頻度**: 毎日 → 週2（`0 23 * * 0,3`）にすると単純に 1/3。
   新着イベントは 1 日単位でそんなに増えないので、費用が気になったらここが一番効く。

### gog のトークンが切れたら

台帳の読み書きができなくなる。会社 Mac で `bash sync_gog_token.sh --reauth` を
実行し、Claude Code on the web の環境変数を更新する（詳細は CLAUDE.md）。
