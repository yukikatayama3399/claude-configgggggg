# sns-event-radar

## 目的

東京のインフルエンサー企業・SNS 運用代行企業などが開催する
**勉強会 / セミナー / 交流会**を毎朝拾い、新着があれば Slack の自分宛 DM に流す。
参加できるイベントを取りこぼさないための「行ける会の常時レーダー」。

## トリガー

- cron: `0 8 * * *`（**Asia/Tokyo** / 毎日 8:00 JST）
- 8:00 台は他ルーティン（9:00 の hawk-url-index 系）と衝突しない。ジッター不要。
- **Claude Code 起動中にのみ発火する。** Mac がスリープ中／Claude Code 停止中の回はスキップされる。
  1 日飛んでも台帳ベースの重複排除が効くので、翌日にまとめて拾い直せる。

## 実行内容

使用ツール: `WebSearch` / `WebFetch` / `Bash`(gog, date) / `mcp__Slack__slack_send_message`

### 1. 台帳を読む（重複排除の準備）

```bash
gog --account yuki.katayama@fout.jp sheets get \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A2:I" -p
```

- Sheet: [SNS・インフルエンサー イベントレーダー 通知ログ](https://docs.google.com/spreadsheets/d/1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4/edit)
- 列: `通知日 / イベント名 / 開催日 / 形式 / 会場・オンライン / 主催 / 費用 / 申込URL / 一言メモ`
- **既出判定のキーは申込 URL**。ただし企業の一覧ページ URL を使い回す主催者
  （ホットリンク等）があるので、URL が同じでも「イベント名＋開催日」が違えば別イベント。

> このステップが失敗しても**止まらないこと**。
> `slack_read_channel(channel_id="U0B7FMCR8JU", limit=60)` で過去 DM を読んで
> 既出判定に切り替え、DM は必ず送る。復旧手順は下記「復旧手順」を参照。
>
> なお別ルーティンが「gog トークンが 7/21 から `invalid_grant` で失効中」と
> DM で報告しているが、**2026-08-05 にクラウド側で検証したところトークンは有効**
> （22 スコープ健在、Sheets / Gmail / Calendar すべて疎通、保存日時 2026-07-13）。
> 同じリフレッシュトークンが動いている以上グラントは revoke されていないので、
> 失敗するなら Mac ローカルの keyring 側（`GOG_KEYRING_PASSWORD` 不一致など）を疑う。
> **`gog auth add` は絶対に叩かないこと**（`--services` 既定が `user` でスコープが縮む）。

### 2. イベントを探す

Mac ローカル実行なのでネットワーク制限は無い。**一覧ページを直接読むのが主**、
WebSearch は補助。

**イベント情報サイト（WebFetch で直接読む）**

| サイト | URL |
|---|---|
| こくちーずプロ SNS × 東京 | https://www.kokuchpro.com/s/tag-SNS/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/ |
| こくちーずプロ インフルエンサー × 東京 | https://www.kokuchpro.com/s/tag-%E3%82%A4%E3%83%B3%E3%83%95%E3%83%AB%E3%82%A8%E3%83%B3%E3%82%B5%E3%83%BC/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/ |
| こくちーずプロ 交流会 × マーケ/広告 × 東京 | https://www.kokuchpro.com/s/q-%E4%BA%A4%E6%B5%81%E4%BC%9A/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/g-5/ |
| Peatix マーケター | https://feature.peatix.com/discover/business-marketing/marketer |
| connpass | https://connpass.com/ （SNS / マーケ / クリエイター で検索） |
| TECH PLAY | https://techplay.jp/event/search?keyword=SNS |

**事業者の自社セミナーページ（URL 確認済み）**

- 株式会社ホットリンク — https://www.hottolink.co.jp/event/
- 株式会社コムニコ — https://www.comnico.jp/sns-seminar
- 株式会社THECOO — https://bizpartner.thecoo.co.jp/seminar
- Find Model（ソーシャルワイヤー） — https://find-model.jp/insta-lab/entry-seminar/

**その他の狙い目社名**は URL を推測せず、社名 + 「セミナー」で WebSearch してから当たる:
サイバー・バズ / テテマーチ / SAKIYOMI / LIDDELL / トリドリ / BitStar /
Natee / UUUM / CANDEE / ガイアックス。

WebSearch を使うときは**クエリに年月を明示的に入れる**
（入れないと過去のイベントばかり返る）。例: `"2026年9月" インフルエンサーマーケティング 勉強会 東京 申込`

### 3. 絞り込む

**含める**

- 開催日が **今日〜60日先**
- 東京都内のオフライン開催 **または** オンライン開催（ウェビナー）
- テーマが SNS マーケ / インフルエンサー施策 / ショート動画 / UGC /
  TikTok・Instagram・YouTube 運用 / SNS 運用代行 / クリエイターエコノミー /
  マーケター交流会・懇親会 のいずれか
- **有料も可**。3 万円超は費用欄に `⚠️高額` を付ける

**除外する**（ここは編集しやすいよう箇条書きで維持する）

- 情報商材・副業勧誘・MLM・「月収◯◯万」系の匂いがするもの
- 学生／就活限定、特定資格保有者限定
- 東京以外のオフライン開催（オンライン併催なら可）
- 開催日が特定できないもの（常時申込の資料 DL・個別相談会）
- 申込 URL が特定できないもの
- 台帳に既出のもの

**上限 8 件**。多い時は「開催が近い順 → 交流会要素があるもの優先」で切り、
切り捨てた件数と理由を DM 末尾に 1 行で書く（黙って落とさない）。

**新着が 1 件でも DM を送る。**「少ないから明日まとめて」はしない。

日時・費用を断定できない項目は推測で埋めず「要確認」と書く。**捏造しない。**

### 4. リマインド分を拾う

台帳の通知済みイベントのうち、**開催日が今日〜3 日以内**のものを DM 後半に載せる。

### 5. Slack DM を送る

`slack_send_message(channel_id="U0B7FMCR8JU", message=...)`
（DM チャンネルは `D0B6P80CF6D`）

**新着もリマインドも 0 件のときだけ送らない。**

```
:mega: *SNS/インフルエンサー イベントレーダー* — M/D(曜)
新着 N 件

*1. 〈イベント名〉*
🗓 M/D(曜) HH:MM–HH:MM ／ 💴 無料 ／ 📍 渋谷（オフライン・懇親会あり）
🏢 主催社名
📝 〈一言サマリ。何が学べて誰が来るか〉
🔗 https://...

---
:alarm_clock: *開催が近い（通知済み）*
・M/D(曜) 〈イベント名〉 → https://...
```

- 交流会・懇親会があるものは 📍 行に「懇親会あり」と明記
- オンラインは 📍 を「オンライン」に
- 曜日は `date -d <YYYY-MM-DD> +%a`（macOS は `date -j -f %Y-%m-%d <日付> +%a`）で確認してから書く

### 6. 台帳に追記

DM に載せた**新着分のみ**（リマインド分は追記しない）。

`--values-json` で 2 次元配列を渡すこと。位置引数で並べると
**全部 1 セルに連結される**（実測済み）。複数件は配列に並べれば 1 回で入る。

```bash
gog --account yuki.katayama@fout.jp sheets append \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A:I" \
  --values-json '[["2026-08-05","イベント名","2026-08-20","オフライン","渋谷","株式会社◯◯","無料","https://...","一言メモ"]]'
```

## 安全設計

- **このルーティンは破壊的操作を一切しない。** 台帳シートへは
  `append`（追記）のみで、`update` / `clear` / 行削除はしない。
- Slack は**自分宛 DM への送信のみ**。他人・チャンネルには一切投稿しない。
- Gmail 送信・カレンダー変更は行わない。
- 台帳が読めない場合も**シートを初期化したりしない**。DM 履歴での代替判定に落とす。
- 必ず「**DM 送信 → 台帳追記**」の順。逆にすると DM 失敗時に
  「台帳にはあるが通知されていない」イベントが生まれ、二度と通知されなくなる。

## チューニングのメモ

| 変えたいもの | 変える場所 |
|---|---|
| 頻度 | cron `0 8 * * *`。週 2 なら `0 8 * * 1,4`、平日のみなら `0 8 * * 1-5` |
| 時刻 | cron の時。8:00 → 7:00 なら `0 7 * * *` |
| 拾う先の期間 | 手順 3 の「今日〜60日先」 |
| 1 回の最大件数 | 手順 3 の「上限 8 件」 |
| 高額判定のライン | 手順 3 の「3 万円超」 |
| リマインドの前倒し日数 | 手順 4 の「今日〜3 日以内」 |
| 監視する主催者 | 手順 2 の事業者リスト。増やすほど実行時間とコストが伸びる |
| ノイズが多い時 | 手順 3 の「除外する」に条件を足す。こくちーずプロは情報商材系が混ざりやすい |

## 復旧手順

### 新しい Mac / 再登録

1. iCloud `scheduled-tasks/sns-event-radar.md` をローカル `~/.claude/scheduled-tasks/` へコピー
2. Claude Code に「`sns-event-radar.md` を cron `0 8 * * *`（Asia/Tokyo）のルーティンとして登録して」と依頼
3. **初回に 1 回手動実行**して、WebFetch / Slack MCP / Bash(gog) の権限承認を全部通す
   （やらないと無人実行時に権限待ちで止まる）

詳細は `setup_new_mac.md`（iCloud `Claude/memory`）。

### gog トークン失効（`invalid_grant`）

台帳の読み書きだけが死ぬ。DM は代替判定で動き続ける。
「正」の会社 Mac で下記を実行し、出力された 3 値をクラウド環境変数と
GitHub Secrets の**両方**へ配る。

```bash
bash sync_gog_token.sh --reauth
```

家 Mac・クラウド・CI で `gog auth add` を直接叩かないこと（スコープが縮んで壊れる）。
詳細は CLAUDE.md の「認証は『1台』でしかやらない」。

### 台帳シートを作り直す場合

ヘッダー行はこれ。作成後、この文書内の Sheet ID を差し替える。

```
通知日,イベント名,開催日,形式,会場/オンライン,主催,費用,申込URL,一言メモ
```

---

## 付録: クラウド（Claude Code on the web）で動かなかった経緯

最初はクラウドの Routine 機能で組んだが、下記 2 点により断念して Mac ローカルへ移した。

- `create_trigger` の `connectors` がこの組織で無効。コネクタ無しの Routine の
  発火セッションには `mcp__Slack__*` が渡らず DM を送れない（テスト発火で無反応を確認）
- `update_trigger` の `model` が `model_update_disabled` で拒否され、安いモデルに落とせない

さらにクラウド環境は egress ポリシーで**一般 Web ホストへの接続が全面ブロック**
されており（`example.com` すら 403、`curl` も `WebFetch` も同様、`hooks.slack.com` も 403）、
使える情報源が `WebSearch` のみだった。Mac ローカルにはこの制約が無いため、
手順 2 で一覧ページを直接読む設計に戻している。
