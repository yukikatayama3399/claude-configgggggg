# カレンダー色分けスイープ（UI で新規作成・通知ハブから移設）

対象: 新規（旧: trig_01DqE28d24nqRRGhA2LEhxjP → 通知ハブ）

通知ハブ（1つの永続セッション）に紐づいていて、ハブのコンテキストが 63 万トークンまで膨らみ、9/12〜9/23 はほぼ全停止、今も 2〜5 時間遅れる。
手順: UI で新規作成。環境 = Default、コネクタ = **Slack**、スケジュール = 毎日 9:20 / 15:20 JST（UTC `20 0,6 * * *`）、毎回新規セッション。作ったら旧 trig_01DqE28d24nqRRGhA2LEhxjP を**無効化**。

## プロンプト（全文を貼る）

`````
【定期実行】Googleカレンダーの色分けスイープを実行してください（毎日9:20 / 15:20 JST。命名ルーティンの9:00/15:00の直後に走る設計）。

**判定はあなたの裁量ではなく、下のスクリプトが決定論的に行います。**
スクリプトの中身を書き換えたり、独自判断で予定を追加・除外したりしないこと。
あなたの仕事は「gog確認 → スクリプト実行 → 出力をそのまま Slack DM で通知」の3つだけ。
**通知はメールではなく必ず Slack DM。メールは理由を問わず絶対に送らない（gog gmail send 全面禁止。ユーザー指示 2026-09-04）。**

変更するのは予定の色(colorId)だけ。タイトル・時間・出席者・availability・公開範囲には一切触れません。

# 色の設計（2026-09-02 見直し版。変更するときはスクリプトの COLOR だけ直す）

| 色 | colorId | 意味 |
|---|---|---|
| グレー（グラファイト） | 8 | 作業（一人の作業ブロック・準備・メモ書き） |
| オレンジ（タンジェリン） | 6 | オンラインミーティング |
| 紫（グレープ） | 3 | 実際に外出する予定・対面・オフライン。**ランチ・会食・夜の外出・通院なども紫** |
| 赤（トマト） | 11 | その他・関係ないもの。カレンダーの既定色も赤なので「色なし」と見た目が同じ。間違った色が残っている予定だけ明示的に赤で上書きして直す |

# ステップ0: gog の確認

## ステップ0（準備）: リポジトリと gog/gws を用意する
この定期実行セッションにはリポジトリがクローンされておらず、SessionStart フックも走らない（そのせいで過去の実行は空振りしていた）。
まず次をそのまま実行する（認証用の環境変数3つは環境側に設定済み。gog auth add / gws auth login は絶対に叩かない）:

```bash
R="$HOME/claude-configgggggg"
[ -d "$R/.git" ] || git clone -q --depth 1 https://github.com/yukikatayama3399/claude-configgggggg "$R"
cd "$R"
[ -f routines/bootstrap.sh ] || { git fetch -q --depth 1 origin claude/clever-cannon-593o8s && git checkout -q FETCH_HEAD; }
bash routines/bootstrap.sh
```

以降の Bash 呼び出しは毎回、先頭に `source ~/.routine_env && cd "$REPO" && ` を付ける（シェルの状態は呼び出しごとに消える）。
最後に `[bootstrap] gog: NG` 等が出て失敗したら、Google への書き込みは一切せず、エラー本文を報告して終了する。
今日の日付は必ず `TZ=Asia/Tokyo date +%Y/%m/%d` で取る（cron は UTC なので素の date は前日になることがある）。


下の「ステップ0（準備）」のブロックを実行する。失敗したら**カレンダーには一切触れず**、
「gog不調のため色分けを中止」と Slack DM（U0B7FMCR8JU）に1行送って終了。

# ステップ1: スクリプトを書き出す

次の内容を `/tmp/color_sweep.py` に**一字一句そのまま**書き出す:

```python
#!/usr/bin/env python3
"""カレンダー色分けスイープ（作業 / オンライン / 外出対面 / その他 の4バケツ）。

色の設計（2026-09-02 見直し版）:
  グレー(8)   = 作業（一人の作業ブロック）
  オレンジ(6) = オンラインミーティング
  紫(3)       = 実際に外出する予定・対面・オフライン
                （往訪/来訪/社内対面/社外に加え、ランチ・会食・夜の外出・通院なども紫）
  赤(11)      = その他・関係ないもの（カレンダーの既定色も赤なので、
                「色なし」と「明示的な赤」は見た目が同じ）

判定は決定論。変更するのは colorId だけで、タイトル・時間・出席者・公開範囲・
availability には一切触れない。--apply を付けない限り読み取りのみ。

既知の制約1: gog も Google Calendar MCP も「色を既定色に戻す」ことができない。
そのため「その他」バケツは赤(11)を明示的に塗ることで対応する。既定色が赤なので
見た目は変わらず、間違った色が残っている予定も自動で直せる。
色が付いていない「その他」予定は既に赤に見えているので書き込みしない（無駄な変更を避ける）。

既知の制約2: 対面かオンラインかを機械的に判別する材料がカレンダーに無い（2026-08-22 実測）。
  - 会議室を押さえていてもオンラインのことがある（TELECUBE ブース等から接続）
  - Meet リンクがあっても対面のことがある（週次定例、来社勉強会等）
つまり location / 会議室リソース / hangoutLink はどれも判定に使えない。
唯一の確かな手がかりはタイトル先頭の [主タグ] で、これは命名ルーティンが付ける。
タグが無い予定はキーワードと出席者から推定し、推定であることを必ず報告する。
"""
import argparse, json, re, subprocess, sys

ACC = "yuki.katayama@fout.jp"
DAYS = 14

# バケツ -> colorId
COLOR = {"作業": "8", "オンライン": "6", "外出対面": "3", "その他": "11"}

# 外出を伴う私用（ランチ・会食・夜の外出・通院など）→ 紫
OUTING_RE = re.compile(
    r"ランチ|昼食|会食|ディナー|飲み|呑み|宴会|懇親会|外食|外出|"
    r"病院|通院|歯医者|処方箋|薬局|ジム|キックボクシング|美容|散髪|保育|送迎", re.I)

# 外出を伴わない私用・不在 → その他(赤)
PRIVATE_RE = re.compile(r"私用|休暇|有給|不在", re.I)

# タイトルに明記されたオンラインの手がかり（タグ無し予定用）
ONLINE_TITLE_RE = re.compile(r"オンライン|web会議|リモート|zoom|teams", re.I)

# 会議らしいタイトル（出席者情報が無くても人と会う予定と分かる）
MEETING_TITLE_RE = re.compile(
    r"会議|ミーティング|MTG|打ち?合わせ|商談|面談|定例|1on1|説明|勉強会|様|さん\b|氏", re.I)

# 会議「について」の一人作業（mtg準備・会議メモ等）。MEETING_TITLE_RE より先に見る。
WORKISH_RE = re.compile(r"準備|メモ|議事録|振り返り|整理|作成|下書き|リサーチ|確認|レビュー", re.I)

# タイトル先頭の主タグ -> バケツ。タグがあれば実体推定より優先する。
# [Private] だけは中身で分岐する（外出系なら紫、それ以外は赤）ので classify() 内で処理。
TAG_BUCKET = {
    "作業": "作業", "準備": "作業",
    "オンライン社外": "オンライン", "オンライン社内": "オンライン", "オンライン": "オンライン",
    "往訪": "外出対面", "来訪": "外出対面", "社内": "外出対面", "社外": "外出対面",
    "オフライン": "外出対面", "オフライン社内": "外出対面", "オフライン社外": "外出対面",
}


def gog(*args, check=True):
    r = subprocess.run(["gog", "--account", ACC, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"gog {' '.join(args)} failed: {(r.stderr or r.stdout)[:300]}")
    return r


def fetch():
    r = gog("calendar", "events", "--from", "today", "--days", str(DAYS), "--all-pages", "-j")
    return json.loads(r.stdout)["events"]


def main_tag(summary):
    m = re.match(r"\s*[\[［]([^\]］]+)[\]］]", summary or "")
    if not m:
        return None
    head = m.group(1).split("/")[0].split("／")[0]
    return re.sub(r"\s+", "", head)


def classify(e):
    """(バケツ, 理由) を返す。対象外なら (None, 理由)。"""
    summary = e.get("summary", "") or ""

    if e.get("eventType", "default") != "default":
        return None, f"eventType={e.get('eventType')}"
    if e.get("workingLocationProperties"):
        return None, "勤務場所イベント"
    if e.get("status") == "cancelled":
        return None, "キャンセル済み"
    if not e.get("start", {}).get("dateTime"):
        return None, "終日予定"

    tag = main_tag(summary)
    humans = [a for a in e.get("attendees", []) if not a.get("resource") and not a.get("self")]

    # タグがあればそれが唯一の確かな手がかり。必ず優先する。
    if tag:
        if tag.lower() == "private":
            if OUTING_RE.search(summary):
                return "外出対面", f"タグ[{tag}]・外出キーワード"
            return "その他", f"タグ[{tag}]"
        b = TAG_BUCKET.get(tag) or TAG_BUCKET.get(tag.lower())
        return (b, f"タグ[{tag}]") if b else (None, f"未知のタグ[{tag}]")

    # タグ無し: キーワード → 出席者の順で推定
    if OUTING_RE.search(summary):
        return "外出対面", "推定・外出キーワード"
    if PRIVATE_RE.search(summary):
        return "その他", "推定・私用キーワード"

    # タイトルに「オンライン」等が明記されていればオンライン扱い
    # （Meetリンクや会議室は当てにならないが、人が書いたタイトルは信じる）
    if ONLINE_TITLE_RE.search(summary):
        return "オンライン", "推定・タイトルにオンライン"

    # 対面とオンラインは機械的に区別できない（上の「既知の制約2」参照）。
    # 相手がいる予定は対面に倒す。オンラインなら命名ルーティンが [オンライン*] を付ける。
    if humans:
        return "外出対面", f"推定・他{len(humans)}名"

    # 「mtg準備」「会議メモ」のような会議についての一人作業は作業扱い
    if WORKISH_RE.search(summary):
        return "作業", "推定・作業キーワード"

    # 出席者情報が無くてもタイトルが会議らしいものは、対面/オンラインを
    # 決められないので触らない（要タグ付けとして報告する）
    if MEETING_TITLE_RE.search(summary):
        return None, "会議らしいが対面/オンライン判別不能・要タグ付け"

    return "作業", "推定・出席者なし"


def build_plan(events):
    plan, skip, guessed, conflict = [], [], [], []
    seen_series = set()

    for e in events:
        summary = e.get("summary", "") or ""
        when = (e.get("start", {}).get("dateTime") or e.get("start", {}).get("date") or "")[:16]
        bucket, why = classify(e)

        if bucket is None:
            skip.append((when, summary, why))
            continue

        want, cur = COLOR[bucket], e.get("colorId")

        # その他バケツ: 既定色(赤)のまま色なしなら見た目は既に正しいので書かない。
        # 間違った色が付いている場合だけ赤(11)で上書きして直す。
        if bucket == "その他" and not cur:
            continue

        if cur == want:
            continue

        # 推定で「作業(グレー)」にしようとしたが、既にオレンジ/紫が付いている場合は
        # 手動で付けた会議色の可能性が高いので上書きせず報告だけする
        if bucket == "作業" and why.startswith("推定") and cur in ("3", "6"):
            conflict.append((when, summary, cur))
            continue

        target_id, scope = e["id"], "単発"
        if e.get("recurringEventId"):
            target_id, scope = e["recurringEventId"], "シリーズ"
            if target_id in seen_series:
                continue
            seen_series.add(target_id)

        item = {"when": when, "summary": summary, "bucket": bucket, "why": why,
                "cur": cur, "want": want, "id": target_id, "scope": scope}
        plan.append(item)
        if why.startswith("推定"):
            guessed.append(item)

    return plan, skip, guessed, conflict


def apply(plan):
    ok, fail = [], []
    for p in plan:
        r = gog("calendar", "update", "primary", p["id"],
                f"--event-color={p['want']}", "--no-input", check=False)
        (ok if r.returncode == 0 else fail).append(p)
        if r.returncode != 0:
            p["error"] = (r.stderr or r.stdout).strip()[:200]
    return ok, fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に色を書き込む")
    a = ap.parse_args()

    events = fetch()
    plan, skip, guessed, conflict = build_plan(events)

    print(f"取得 {len(events)}件 / 変更対象 {len(plan)}件 / 対象外 {len(skip)}件")

    if not a.apply:
        for p in plan:
            print(f"  DRY {p['when']} →{p['bucket']} {p['cur'] or '-'}→{p['want']} "
                  f"({p['why']}) {p['summary'][:40]}")
        for when, summary, cur in conflict:
            print(f"  保留 {when} 色{cur}のまま（推定グレーと衝突・要タグ付け） {summary[:40]}")
        return 0

    ok, fail = apply(plan)

    # 書いたら必ず読み返して検証する（gog が黙って無視する系のバグを検出するため）
    after = {e.get("recurringEventId") or e["id"]: e.get("colorId") for e in fetch()}
    unverified = [p for p in ok if after.get(p["id"]) != p["want"]]

    print(f"適用 {len(ok)}件 / 失敗 {len(fail)}件 / 反映されなかった {len(unverified)}件")
    for p in ok:
        print(f"  OK   {p['when']} →{p['bucket']} {p['cur'] or '-'}→{p['want']} {p['summary'][:40]}")
    for p in fail:
        print(f"  FAIL {p['when']} {p['summary'][:40]} :: {p.get('error','')}")
    for p in unverified:
        print(f"  未反映 {p['when']} {p['summary'][:40]}（要確認）")
    if guessed:
        print(f"\n推定で決めた {len(guessed)}件（タグが無いのでキーワード・出席者から判定）:")
        for p in guessed:
            print(f"  ? {p['when']} →{p['bucket']} ({p['why']}) {p['summary'][:40]}")
    if conflict:
        print(f"\n触らなかった {len(conflict)}件（推定はグレーだが会議色が付いている・要タグ付け）:")
        for when, summary, cur in conflict:
            print(f"  ! {when} 色{cur} {summary[:40]}")

    return 1 if (fail or unverified) else 0


if __name__ == "__main__":
    sys.exit(main())
```

# ステップ2: ドライラン → 本実行

```bash
source ~/.routine_env && python3 /tmp/color_sweep.py   # まず読み取りのみ
source ~/.routine_env && python3 /tmp/color_sweep.py --apply > /tmp/color_report.txt 2>&1; cat /tmp/color_report.txt
```

ドライランで**変更対象が20件を超えた**場合は `--apply` せずに中止し、
「変更対象が異常に多い(N件)。命名ルーティンかカレンダーに大きな変化があった可能性。要確認」と Slack DM で通知する。
この Routine は毎回新しいセッションで動くので、会話での「適用OK」は引き継がれない。上限を超えた回の適用は、片山が別セッションで手動実行する。
通常は0〜8件で収まる（2026-09-02に初回スイープ適用済みのため）。

# ステップ3: 通知（Slack DM のみ・送信は必ず1回だけ。ここを厳守する）

1. `mcp__Slack__slack_send_message` で channel_id=`U0B7FMCR8JU`（自分宛DM）に**1通**送る。
2. **メールは理由を問わず一切送らない。** `gog gmail send` を含む Gmail 送信は全面禁止。
   Slack 送信が失敗した場合も**メールに切り替えず**、出力全文をテキストに残して終了する。
3. **一度送信に成功したら、絶対に再送しない。** 体裁が気に入らなくても書き直した版を送り直すのも禁止。

本文は**スクリプトの出力の数字をそのまま使う。憶測で件数を書かない。**

```
🎨 カレンダー色分け（YYYY/MM/DD JST）
適用 N件 / 失敗 N件 / 未反映 N件
（変更した予定を1行ずつ）
▼推定で決めた予定（タグなし・要タグ付け）
▼触らなかった予定（会議色と衝突・要タグ付け）
```

適用0件・推定0件・衝突0件なら「🎨 カレンダー色分け（日付）: 変更なし」の1行だけでよい。

# 設計上の約束（守ること）

- 変更するのは colorId のみ。予定の削除・時間変更・タイトル変更・出席者変更は**禁止**
- 終日予定・勤務場所イベント(オフィス/在宅/自宅)・キャンセル済みは**触らない**
- 未知のタグが付いた予定は**触らない**（スクリプトがそう実装されている）
- **Meetリンクや会議室の有無で対面/オンラインを判定してはいけない**（実測で両方とも当てにならない）。
  使ってよいのはタイトルの `[主タグ]` とタイトル中のキーワードだけ
- 推定でグレーにしようとした予定に既にオレンジ/紫が付いていたら上書きしない（手動の意図を尊重）
- スクリプトは書き込み後に必ず読み返して検証する実装になっている。
  「未反映」が出たら gog 側の不具合なので、件数を隠さず報告する
- タグが無い予定は推定なので、必ず報告に出す（人が見て直せるように）
`````
