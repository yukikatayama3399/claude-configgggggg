# 定期通知は Slack DM に統一（2026-09-04〜）

ユーザー指示（2026-09-04）:
**「email はややこしくなるので一切飛ばさない。そういった連絡は全部 Slack DM で統一」**

自分宛の自動レポートメール（📊 HAWK提案ステータス／🎨 カレンダー色分け）を廃止し、
Slack の自分宛 DM（ユーザーID `U0B7FMCR8JU`）への通知に切り替えた。

## 仕組み: 「通知ハブ」セッション方式

クラウド Routine の `create_trigger` は（この組織では）`connectors` パラメータが使えず、
**新規セッションを起こす Routine には Slack コネクタが載らない**。
これが旧 Routine が毎回メールにフォールバックしていた原因。

対策として、Slack・Gmail コネクタと gog を持つ専用セッション
**「📮 Slack DM通知ハブ」（`session_011ji9Vzp6xTFMdbw5jGkPa5`）** に Routine をバインドした
（`persistent_session_id` 方式。木曜KPI Routine 等と同じ構成）。
Routine が発火するたびにこのセッションが起こされ、セッションが持つ Slack ツールで DM を送る。

**⚠️ このハブセッションをアーカイブすると通知が全部止まる。消さないこと。**
（万一消えたら: 新しいセッションを1つ用意し、下記 Routine を作り直して bind する）

## 現在の Routine 構成

| Routine | trigger_id | cron (UTC) | JST | 状態 |
|---|---|---|---|---|
| HAWK提案ステータス 日次ダイジェスト（Slack DM） | `trig_01NMn8xLGkG3kSU8eR3MfmZY` | `30 0 * * 1-5` | 平日9:30 | ✅ 有効・ハブにbind |
| カレンダー色分けスイープ（Slack DM） | `trig_01DqE28d24nqRRGhA2LEhxjP` | `20 0,6 * * *` | 毎日9:20/15:20 | ✅ 有効・ハブにbind |
| 競合ウォッチ→Slack DM リレー | `trig_018NXbtQtTsj3BMrDfFb36CC` | `10 0 * * 1-5` | 平日9:10 | ✅ 有効・ハブにbind |
| （旧）HAWK提案ステータス 日次ダイジェスト | `trig_012JLJu4RAzFENKjBwiaJ7U4` | `30 0 * * 1-5` | 平日9:30 | ⏸ 無効化（メール送信版。新版が安定したら削除可） |
| （旧）カレンダー色分けスイープ | `trig_01A4nuJQwMT9oXDZDSJJQ79t` | `20 0,6 * * *` | 毎日9:20/15:20 | ⏸ 無効化（同上） |

新版プロンプトの要点:
- 通知は `mcp__Slack__slack_send_message` で `channel_id=U0B7FMCR8JU`（自分宛DM）に1通のみ
- **メールは理由を問わず送らない**（`gog gmail send` 全面禁止）。Slack 失敗時もメールに切り替えず、本文をテキスト出力に残して終了
- 処理本体（ヨミ管理シートの読み方・color_sweep.py）は旧版から変更なし

## 競合ウォッチについて（2026-09-04 調査結果）

「競合ウォッチ 朝のブリーフィング」（`trig_01NbZFsiw8x1tJH6XyPRuAuq`）は**止まっていない**。
平日8:30 JST に起動し、毎朝8:40〜8:50頃に #competitor-watch（`C0B9NH3JUTS`）へ投稿し続けている
（「最近見ない」のは、投稿先がDMでなくチャンネルな上、新着なしの日は1行だけのため）。

- この Routine は **claude.ai UI 管理**（created_via: http_api）のため、
  エージェントからはプロンプト変更・無効化が**できない**（実測: update_trigger が拒否される）。
  変更したい場合は claude.ai の Routines 画面から編集する。
- DM 統一のため、上記の**リレー Routine** が平日9:10 JST にチャンネル投稿を DM へ複製する。
- 既知の不具合: 本体が毎回『⚠️台帳未記帳』を出している（fired session に Sheets が無く、
  台帳シート `1eL80eA0_awTm6boaCrMWIRq4mN1Vk8l7d9McDwlPwEE` へ書けない）。
  直すには UI からプロンプトを編集し、台帳の読み書きを gog（bootstrap ブロック込み）に変える。

## 今後の運用ルール

- **自分宛の定期レポートをメールで送る Routine・スクリプトを新規に作らない。** 通知は Slack DM（`U0B7FMCR8JU`）へ。
- 新しい定期通知を作るときは、Slack コネクタを確実に使うため
  ①通知ハブセッションに bind する（このセッション内から `create_trigger`、`persistent_session_id` 省略で self-bind）か、
  ②claude.ai UI から Slack コネクタ付きで作る。
