# 生収集_0804 「会社名 / 会社URL / フォームURL」3点セット補完

対象シート: https://docs.google.com/spreadsheets/d/1iyhwVNhN_HJNdIBL_pREhrhBdQu2it5ktFOYq-DDm_w/edit?gid=1849606060
タブ: `生収集_0804`

## 現状（2026-08-10 時点）

全 486 行（データ行）中:

| 状態 | 件数 |
|---|---|
| 3点セット揃い | 61 |
| フォームURLのみ欠け | 292 |
| 会社URL・フォームURL両方欠け | 133 |
| 会社名が空 | 0 |

会社URLだけが欠けている行は無い（会社URLが無い行はフォームURLも無い）。

## ファイル

- `need_form.json` … 会社URLはあるがフォームURLが無い 292 行。`{row, no, name, url}`
- `need_both.json` … 会社URL・フォームURL両方が無い 133 行。`{row, no, name}`

`row` はシートの行番号（1行目がヘッダなのでそのまま A1 記法で使える）。

## 列レイアウト

| 列 | 内容 |
|---|---|
| A | No |
| B | 会社名 |
| C | 会社URL |
| D | フォームURL |
| E | 特徴（1行） |
| F | 収集元記事（集約） |
| G | 出現回数 |
| H | 収集日 |
| I | 要確認 |
| J | 別表記 |

## 補完済み

| 行 | 会社名 | フォームURL |
|---|---|---|
| 19 | 株式会社AKEY | https://akey.co.jp/contact |
| 20 | 株式会社BlueDine | https://bluedine.co.jp/contact/ |
| 21 | 株式会社Z世代 | https://zgeneration.co.jp/contact/ |
| 22 | 株式会社ブラーヴォ | https://line-sm.com/contact/ |
| 23 | 株式会社リベルテ | https://www.liberte-group.co.jp/contact/ |

（`need_form.json` はこの5行を含んだ時点のスナップショット。再開時はシートを読み直して差分を取り直すこと）

## ブロッカー: egress ポリシー

このクラウドセッションでは外部サイトへの通信が組織のネットワークポリシーで全面的に
拒否されている。`curl` も `WebFetch` も同じゲートウェイで止まる。

```
curl https://e-pace.co.jp/
  → curl: (56) CONNECT tunnel failed, response 403

WebFetch https://e-pace.co.jp/
  → EGRESS_BLOCKED: Access to e-pace.co.jp is blocked by the network egress proxy.
```

`curl -sS "$HTTPS_PROXY/__agentproxy/status"` の `recentRelayFailures` に
`connect_rejected / gateway answered 403 to CONNECT` として記録される。

そのため「各社サイトを開いてヘッダ・フッタから問い合わせリンクを辿る」という
本来のやり方が使えない。

### 使えるのは WebSearch のみ、かつ精度が出ない

`site:<domain> お問い合わせ contact` で検索インデックスに載っているフォームURLは
拾えるが、載っていないドメインは検索語を変えても出てこない。11社試した実測で
確定できたのは 5社（約45%）。

未確定だった例: e-pace.co.jp / initialbrain.jp / business.textrade.org /
original-inc.com / in-line.jp

この方式で 425 行を総当たりしても埋まるのは推定 5〜6 割。

## 再開手順

1. Claude Code on the web の環境設定でネットワークポリシーを緩める
   （全許可、または対象ドメインを許可リストに追加）。
   参考: https://code.claude.com/docs/en/claude-code-on-the-web
2. ポリシーはコンテナ起動時に効くため、**新しいセッションを開始する**。
3. 疎通確認: `curl -sS -o /dev/null -w "%{http_code}\n" https://e-pace.co.jp/`
4. シートを読み直して `need_form` / `need_both` を作り直す。
5. `need_form` は各社トップページを取得 → ヘッダ/フッタから
   `contact` / `inquiry` / `toiawase` / `問い合わせ` を含むリンクを抽出 → 200 を確認して D 列へ。
6. `need_both` は会社名で検索して公式サイトを特定 → C 列へ → 5 と同じ流れで D 列へ。

## 方針（ユーザー決定事項）

- 確定できなかった行は**空欄のまま**にする。推測URL（`会社URL + /contact/`）は書かない。
- 代わりに I 列「要確認」に `フォームURL未確認` と記録する。
