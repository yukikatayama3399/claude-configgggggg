# sns-event-radar

東京のインフルエンサー企業・SNS運用代行企業などが開催する**勉強会 / セミナー / 交流会**を
毎朝拾い、新着があれば Slack の自分宛 DM に流す。行ける会を取りこぼさないためのレーダー。

- cron: `0 8 * * *`（Asia/Tokyo / 毎日 8:00）
- Claude Code 起動中にのみ発火する。スリープ中・停止中の回はスキップされるが、
  台帳ベースの重複排除が効くので翌日にまとめて拾い直せる。

## 絶対ルール

1. **破壊的操作をしない。** 台帳シートへは `append`（追記）のみ。
   `update` / `clear` / 行削除は禁止。
2. **Slack は自分宛 DM への送信のみ。** 他人・チャンネルへは一切投稿しない。
   Gmail 送信・カレンダー変更もしない。
3. **必ず「DM送信 → 台帳追記」の順。** 逆にすると DM 失敗時に
   「台帳にはあるが通知されていない」イベントが生まれ、二度と通知されなくなる。
4. **日時・費用を断定できない項目は推測で埋めず「要確認」と書く。捏造しない。**

## アカウント

- `yuki.katayama@fout.jp`（Sheets 操作はすべて gog CLI = Bash）
- **`--account yuki.katayama@fout.jp` を必ず付ける。** 付けないと個人 gmail
  （gmail スコープのみ）で実行され `403 forbidden` になる。
- グローバルフラグはサブコマンドの**前**に置く（後ろだと `unknown flag`）。

## 台帳

[SNS・インフルエンサー イベントレーダー 通知ログ](https://docs.google.com/spreadsheets/d/1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4/edit)
（`1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4`）

列: `通知日 / イベント名 / 開催日 / 形式 / 会場・オンライン / 主催 / 費用 / 申込URL / 一言メモ`

state.json は使わない。台帳シートが状態そのもので、片山さんが自分で
「どのイベントを通知済みか」を見返せるようにしてある。

## 手順

### 1. 台帳を読む（重複排除の準備）

```bash
gog --account yuki.katayama@fout.jp sheets get \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A2:I" -p
```

既出判定のキーは**申込URL**。ただし企業の一覧ページ URL を使い回す主催者
（ホットリンク等）があるので、URL が同じでも「イベント名＋開催日」が違えば別イベント。

**このステップが失敗しても止まらないこと。**
`slack_read_channel(channel_id="U0B7FMCR8JU", limit=60)` で過去 DM を読んで
既出判定に切り替え、DM は必ず送る。失敗の切り分けは `bash ~/claude-configgggggg/diagnose_gog.sh`。
**403 forbidden は権限不足であって失効ではない**（`--account` の付け忘れを疑う）。

### 2. イベントを探す

一覧ページを直接読むのが主、WebSearch は補助。日付が変わるので毎回引き直す。

| サイト | URL |
|---|---|
| こくちーずプロ SNS × 東京 | https://www.kokuchpro.com/s/tag-SNS/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/ |
| こくちーずプロ インフルエンサー × 東京 | https://www.kokuchpro.com/s/tag-%E3%82%A4%E3%83%B3%E3%83%95%E3%83%AB%E3%82%A8%E3%83%B3%E3%82%B5%E3%83%BC/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/ |
| こくちーずプロ 交流会 × マーケ/広告 × 東京 | https://www.kokuchpro.com/s/q-%E4%BA%A4%E6%B5%81%E4%BC%9A/area-%E6%9D%B1%E4%BA%AC%E9%83%BD/g-5/ |
| Peatix マーケター | https://feature.peatix.com/discover/business-marketing/marketer |
| connpass | https://connpass.com/ （SNS / マーケ / クリエイター で検索） |
| TECH PLAY | https://techplay.jp/event/search?keyword=SNS |

事業者の自社セミナーページ（URL 確認済み）:

- 株式会社ホットリンク — https://www.hottolink.co.jp/event/
- 株式会社コムニコ — https://www.comnico.jp/sns-seminar
- 株式会社THECOO — https://bizpartner.thecoo.co.jp/seminar
- Find Model（ソーシャルワイヤー） — https://find-model.jp/insta-lab/entry-seminar/

その他の狙い目社名は**URL を推測せず**、社名 +「セミナー」で WebSearch してから当たる:
サイバー・バズ / テテマーチ / SAKIYOMI / LIDDELL / トリドリ / BitStar /
Natee / UUUM / CANDEE / ガイアックス。

WebSearch を使うときは**クエリに年月を明示的に入れる**（入れないと過去のイベントばかり返る）。
例: `"2026年9月" インフルエンサーマーケティング 勉強会 東京 申込`

### 3. 絞り込む

**含める**

- 開催日が今日〜60日先
- 東京都内のオフライン開催 **または** オンライン開催（ウェビナー）
- テーマが SNS マーケ / インフルエンサー施策 / ショート動画 / UGC /
  TikTok・Instagram・YouTube 運用 / SNS 運用代行 / クリエイターエコノミー /
  マーケター交流会・懇親会 のいずれか
- 有料も可。3 万円超は費用欄に `⚠️高額` を付ける

**除外する**（編集しやすいよう箇条書きで維持）

- 情報商材・副業勧誘・MLM・「月収◯◯万」系の匂いがするもの
- 学生／就活限定、特定資格保有者限定
- 東京以外のオフライン開催（オンライン併催なら可）
- 開催日が特定できないもの（常時申込の資料 DL・個別相談会）
- 申込 URL が特定できないもの
- 台帳に既出のもの

**上限 8 件**。多い時は「開催が近い順 → 交流会要素があるもの優先」で切り、
切り捨てた件数と理由を DM 末尾に 1 行で書く（黙って落とさない）。

**新着が 1 件でも DM を送る。**「少ないから明日まとめて」はしない。

### 4. リマインド分を拾う

台帳の通知済みイベントのうち、**開催日が今日〜3 日以内**のものを DM 後半に載せる。

### 5. Slack DM を送る

`slack_send_message(channel_id="U0B7FMCR8JU", ...)`（DM チャンネル `D0B6P80CF6D`）

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
- 曜日は `date -j -f %Y-%m-%d <日付> +%a`（macOS）で確認してから書く

### 6. 台帳に追記

DM に載せた**新着分のみ**（リマインド分は追記しない）。

`--values-json` で 2 次元配列を渡すこと。位置引数で並べると
**全部 1 セルに連結される**（実測済み）。複数件は配列に並べれば 1 回で入る。

```bash
gog --account yuki.katayama@fout.jp sheets append \
  1E6pk0kpPIaA-XanIUAzjhI2qXQxJRH3B9eewISNHyZ4 "A:I" \
  --values-json '[["2026-08-08","イベント名","2026-08-20","オフライン","渋谷","株式会社◯◯","無料","https://...","一言メモ"]]'
```

## チューニング

| 変えたいもの | 変える場所 |
|---|---|
| 頻度 | cron `0 8 * * *`。週2なら `0 8 * * 1,4`、平日のみなら `0 8 * * 1-5` |
| 拾う期間 | 手順3の「今日〜60日先」 |
| 1回の最大件数 | 手順3の「上限 8 件」 |
| 高額判定のライン | 手順3の「3 万円超」 |
| リマインドの前倒し日数 | 手順4の「今日〜3 日以内」 |
| 監視する主催者 | 手順2のリスト。増やすほど実行時間が伸びる |
| ノイズが多い時 | 手順3の「除外する」に条件を足す。こくちーずプロは情報商材系が混ざりやすい |

## 再登録

マスター定義は iCloud `Claude/scheduled-tasks/sns-event-radar/`。
新Macでは local へコピー → cron `0 8 * * *`(Asia/Tokyo) で再登録 →
**初回手動実行で WebFetch / Slack MCP / Bash(gog) の権限承認を全部通す**
（やらないと無人実行時に権限待ちで止まる）。
パス注意: 会社Mac=ユーザー名 `yuki`、家Mac=`FOyuki`（`$HOME` を使えば両対応）。
