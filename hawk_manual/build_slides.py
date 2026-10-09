"""マスターシートからスライドを作り直す。

    python3 build_slides.py draft        # 下書き版: 全行（差戻し・置換済以外）。見え方の確認用。未承認行は機能名が赤字
    python3 build_slides.py prod         # 本番版: 承認済 × 提供中 の行だけ
    python3 build_slides.py prod --lite  # 本番・簡易版: さらに「簡易版」チェックの行だけ
    python3 build_slides.py prod --archive  # 本番を作り直したあと PDF を日付付きで保存し版管理に記録

プレゼンは毎回「同じファイルの中身を全部差し替え」る。URL が変わらないので
お客様に配ったリンクはそのまま最新になる。初回だけ新規作成し config.json に ID を書き戻す。
見た目（色・寸法・部品）は layout.py、ページ構成はこのファイルの render()。
"""
import argparse
import datetime as dt
import hashlib
import math
import json
import pathlib
import re
import subprocess

import assets
from gws import call, read_tab
from layout import (BODY_BOTTOM, BODY_TOP, GREEN, GREEN_DARK, GREEN_LIGHT, GREEN_PALE, MUTED, MX, RED, SUB,
                    TEXT, WHITE, W, H, Deck, est_lines, paginate)
from schema import APPROVED, CATEGORIES, CATEGORY_ORDER, RELEASED, REJECTED, SUPERSEDED

HERE = pathlib.Path(__file__).parent
CONFIG = HERE / "config.json"
JST = dt.timezone(dt.timedelta(hours=9))

TITLES = {
    "draft": "【下書き】HAWK 機能取扱説明書",
    "prod": "HAWK 機能取扱説明書",
    "prod_lite": "HAWK 機能取扱説明書（簡易版）",
}
# 初期設定・連携はオンボーディングで済むので運用の流れには入れない（章としては残す）
STEPS = [("BRF", "与件"), ("EST", "設計・見積り"),
         ("DLV", "配信設計"), ("OPS", "運用"), ("RPT", "レポート")]
MENUS = ["DealDesk", "与件", "キャンペーン", "オブジェクト", "ワークスペース"]


# ---- データ読み込み --------------------------------------------------------------
def load_rows(sid: str, mode: str, lite: bool) -> dict[str, list[dict]]:
    def ok(r: dict, need_release: bool) -> bool:
        if mode == "draft":
            return r.get("承認") not in (REJECTED, SUPERSEDED)
        if r.get("承認") != APPROVED:
            return False
        if need_release and r.get("提供状態", RELEASED) not in (RELEASED, ""):
            return False
        return not lite or r.get("簡易版", "").upper() == "TRUE"

    def latest_per_id(rows: list[dict], id_col: str) -> list[dict]:
        # 同じIDの行が複数あれば後ろ（新しい）を採用。仕様変更は同IDの新しい行として足す運用のため
        by_id: dict[str, dict] = {}
        for r in rows:
            by_id[r[id_col]] = r
        return list(by_id.values())

    out = {
        "機能一覧": latest_per_id([r for r in read_tab(sid, "機能一覧") if ok(r, True)], "機能ID"),
        "サイトマップ": latest_per_id([r for r in read_tab(sid, "サイトマップ")
                                  if mode == "draft" and r.get("承認") not in (REJECTED, SUPERSEDED)
                                  or r.get("承認") == APPROVED], "画面ID"),
        "逆引き": latest_per_id([r for r in read_tab(sid, "逆引き") if ok(r, False)], "UCID"),
        "FAQ": latest_per_id([r for r in read_tab(sid, "FAQ") if ok(r, False)], "FAQID"),
        "更新履歴": [r for r in read_tab(sid, "更新履歴") if mode == "draft" or r.get("反映状況") == APPROVED],
    }
    # 本番に出ない機能を参照している逆引きは、参照を落とす（空になれば逆引きごと落とす）
    live = {r["機能ID"] for r in out["機能一覧"]}
    ucs = []
    for r in out["逆引き"]:
        ids = [i for i in split_ids(r.get("使う機能ID", "")) if i in live]
        if ids or mode == "draft":
            ucs.append({**r, "使う機能ID": "、".join(ids) if mode != "draft" else r.get("使う機能ID", "")})
    out["逆引き"] = ucs
    return out


def split_ids(s: str) -> list[str]:
    return [i.strip() for i in re.split(r"[,、\s]+", s or "") if i.strip()]


def cat_of(feature_id: str) -> str:
    prefix = feature_id.split("-")[1] if "-" in feature_id else ""
    return dict((p, c) for c, p in CATEGORIES).get(prefix, "その他")


# ---- ページ構成 ------------------------------------------------------------------
def render(data: dict, mode: str, lite: bool, art: dict, today: str, toc: dict[str, int] | None,
           screen_pages: dict[str, int] | None, version: str = "") -> tuple[Deck, dict, dict]:
    kind = "prod_lite" if lite else mode
    footer = (f"{TITLES[kind]}｜{today} 版｜このスライドは随時更新されます（リンク先は常に最新版）"
              if mode != "draft" else f"【下書き{version}・社外秘】{today} 生成｜赤字の機能名は未承認（全件未承認のときは色分けなし）")
    urls, sizes = art["urls"], art["sizes"]
    d = Deck(f"b{dt.datetime.now(JST).strftime('%H%M%S')}", urls, footer)
    feats, screens, ucs, faqs, changes = (data[k] for k in ("機能一覧", "サイトマップ", "逆引き", "FAQ", "更新履歴"))
    by_screen = {s["画面ID"]: s for s in screens}
    names = {r["機能ID"]: r["機能名"] for r in feats}
    unapproved = {r["機能ID"] for r in feats if r.get("承認") != APPROVED}
    if len(unapproved) == len(feats):  # 全部未承認なら赤字にしても情報にならない
        unapproved = set()
    toc = toc or {}
    screen_pages = screen_pages or {}
    found_toc, found_screens = {}, {}

    # 表紙
    d.new_page(bg=WHITE)
    d.rect(0, 0, 300, H, GREEN)
    d.text(28, 120, 260, 40, "HAWK", size=30, bold=True, color=WHITE)
    d.text(28, 160, 260, 60, TITLES[kind].replace("HAWK ", ""), size=20, bold=True, color=WHITE)
    d.text(28, 230, 250, 40, "SNS広告伴走型AIエージェント HAWK の\n画面と機能をまとめた取扱説明書です。", size=9, color=WHITE)
    d.text(28, 360, 250, 16, f"{today} 時点" + (f"｜下書き {version}" if version else ""), size=9, color=GREEN_PALE)
    if urls.get("logo_hawk"):
        d.image(330, 40, 120, 39, urls["logo_hawk"], border=False)
    stats = [("機能", len(feats)), ("画面", len(screens)), ("逆引き", len(ucs)), ("FAQ", len(faqs))]
    for i, (label, n) in enumerate(stats):
        x = 330 + i * 92
        d.rect(x, 150, 84, 70, GREEN_PALE)
        d.text(x, 158, 84, 30, str(n), size=22, bold=True, color=GREEN_DARK, align="CENTER")
        d.text(x, 192, 84, 16, label, size=8, color=SUB, align="CENTER")
    d.text(330, 250, 360, 80,
           "・このスライドはマスターデータから自動生成しています。\n"
           "・機能の追加・仕様変更があると内容が更新されます。共有リンクを開けば常に最新版です。\n"
           "・印刷・保存用の PDF は日付つきでお渡しできます。", size=8, color=SUB)
    if mode == "draft":
        d.text(330, 330, 360, 20, "【下書き】社内確認用。お客様には本番版のリンクを共有してください。", size=8, color=RED, bold=True)

    # 目次
    d.frame("目次・この資料の使い方")
    chapters = [("全体像", "HAWK でできること（運用の流れ）"), ("サイトマップ", "画面構成（どの画面で何をするか）"),
                ("最近の更新", "新しく使えるようになった機能")] + \
               [(c, c) for c in CATEGORY_ORDER if any(cat_of(r["機能ID"]) == c for r in feats)] + \
               ([("逆引き", "やりたいことから探す")] if ucs else []) + ([("FAQ", "よくあるご質問")] if faqs else [])
    lines = [f"{label}" for _, label in chapters]
    pages = [f"p.{toc.get(key, '')}" for key, _ in chapters]
    half = math.ceil(len(lines) / 2) if len(lines) > 8 else len(lines)
    for col, (ls, ps) in enumerate(((lines[:half], pages[:half]), (lines[half:], pages[half:]))):
        x = MX + 9 + col * 230
        for i, (l, p) in enumerate(zip(ls, ps)):
            y = BODY_TOP + 8 + i * 22
            d.rect(x, y + 3, 3, 12, GREEN_LIGHT)
            d.text(x + 8, y, 170, 18, l, size=9, valign="MIDDLE")
            d.text(x + 175, y, 40, 18, p, size=9, color=GREEN, bold=True, align="END", valign="MIDDLE")
    gx = MX + 480
    d.rect(gx, BODY_TOP + 8, W - MX - gx, 300, GREEN_PALE)
    d.text(gx + 10, BODY_TOP + 16, W - MX - gx - 20, 290,
           "使い方\n\n"
           "■ まず全体像とサイトマップで、HAWK の流れと画面の場所をつかみます。\n\n"
           "■ 各章は「1画面 = 1ページ」。左に画面、右にその画面でできること・設定項目・注意点をまとめています。\n\n"
           "■ 「〇〇したい」から探すときは逆引き、細かい仕様は FAQ をご覧ください。\n\n"
           "■ 表の見方\n【設定】設定できる項目・選択肢\n【目的】何のための機能か\n【注意】制約・ご注意点",
           size=8, color=TEXT, runs=[(0, 3, {"bold": True, "size": 10, "color": GREEN_DARK})])

    # 全体像
    found_toc["全体像"] = d.page_no + 1
    d.frame("HAWK でできること（運用の流れ）", "全体像", "メモを貼るだけで、与件整理 → 設計・見積り → 配信設計 → 運用 → レポートまでを1つの画面で進められます。")
    gap = 6
    cw = (W - 2 * MX - (len(STEPS) - 1) * gap) / len(STEPS)
    for i, (prefix, label) in enumerate(STEPS):
        x = MX + i * (cw + gap)
        d.rect(x, BODY_TOP + 4, cw, 30, GREEN)
        d.text(x, BODY_TOP + 4, cw, 30, f"STEP {i + 1}　{label}", size=10, bold=True, color=WHITE, align="CENTER", valign="MIDDLE")
        if i < len(STEPS) - 1:  # 左→右の流れを示す矢印
            d.text(x + cw - 2, BODY_TOP + 4, gap + 4, 30, "▶", size=7, color=GREEN_LIGHT, align="CENTER", valign="MIDDLE")
        items = [short_name(r["機能名"]) for r in feats if r["機能ID"].split("-")[1] == prefix]
        box_h = 262
        size = 8.5  # 箱に収まるまで文字を小さくする（省略はしない）
        while size > 6.5 and sum(est_lines(f"・{n}", cw - 10, size) for n in items) * size * 1.3 > box_h - 10:
            size -= 0.25
        d.rect(x, BODY_TOP + 36, cw, box_h, GREEN_PALE)
        d.text(x + 6, BODY_TOP + 41, cw - 10, box_h - 6, "\n".join(f"・{n}" for n in items), size=size, color=TEXT)
    bands = [(c, [short_name(r["機能名"]) for r in feats if cat_of(r["機能ID"]) == c])
             for c in ("DealDesk（提案書作成）", "クリエイティブ・オブジェクト", "ワークスペース・権限")]
    y, bw = BODY_TOP + 36 + 262 + 4, (W - 2 * MX - 2 * gap) / 3
    for i, (c, items) in enumerate(bands):
        x = MX + i * (bw + gap)
        head = f"{c}　→ p.{toc.get(c, '')}"
        body = "／".join(items[:3]) + ("　など" if len(items) > 3 else "")
        d.text(x, y, bw, BODY_BOTTOM - y + 2, f"{head}\n{body}", size=7, color=TEXT, fill="#f6f8f2",
               runs=[(0, len(head), {"bold": True, "size": 7.5, "color": GREEN_DARK})])

    # サイトマップ
    found_toc["サイトマップ"] = d.page_no + 1
    d.frame("サイトマップ（画面構成）", "サイトマップ",
            "ログイン後、画面上部のメニューから各画面に移動します。右の数字はこの資料の掲載ページです。ワークスペースメニューは管理者のみ表示されます。")
    top = [s for s in screens if s.get("階層1") in ("ログイン", "ヘッダー")]
    d.text(MX, BODY_TOP + 4, W - 2 * MX, 16, "  →  ".join(s["画面名"] for s in top) + "  →  各メニュー",
           size=8, color=WHITE, bold=True, fill=GREEN_DARK, valign="MIDDLE")
    mw = (W - 2 * MX - 4 * 6) / 5
    for i, menu in enumerate(MENUS):
        x = MX + i * (mw + 6)
        y = BODY_TOP + 26
        d.rect(x, y, mw, 18, GREEN)
        d.text(x, y, mw, 18, menu, size=8.5, bold=True, color=WHITE, align="CENTER", valign="MIDDLE")
        y += 22
        for s in [s for s in screens if norm_menu(s.get("階層1", "")) == menu]:
            p = screen_pages.get(s["画面ID"], "")
            ptxt = f"p.{p}" if p else ""
            if s.get("階層3"):  # モーダル等は字下げして小さく。名前は省略せず折り返す
                h = est_lines(s["画面名"], mw - 44, 6.5) * 6.5 * 1.3 + 2
                d.text(x + 4, y, 8, h, "└", size=6.5, color=SUB)
                d.text(x + 12, y, mw - 44, h, s["画面名"], size=6.5, color=SUB)
                d.text(x + mw - 32, y, 32, 10, ptxt, size=6.5, color=GREEN, align="END")
                y += h + 1
            else:
                h = max(est_lines(s["画面名"], mw - 40, 7) * 7 * 1.3 + 6, 15)
                d.rect(x, y, mw, h, GREEN_PALE)
                d.text(x + 4, y, mw - 40, h, s["画面名"], size=7, bold=True, color=GREEN_DARK, valign="MIDDLE")
                d.text(x + mw - 36, y, 34, h, ptxt, size=7, color=GREEN, bold=True, align="END", valign="MIDDLE")
                y += h + 2

    # 最近の更新
    if changes:
        found_toc["最近の更新"] = d.page_no + 1
        recent = sorted(changes, key=lambda r: r.get("リリース日") or r.get("検知日") or "", reverse=True)[: (10 if lite else 22)]
        rows = [[r.get("リリース日") or r.get("検知日"), r.get("種別", ""), r["内容"],
                 "、".join(names.get(i, i) for i in split_ids(r.get("対象ID", "")))] for r in recent]
        widths = [62, 36, 410, W - 2 * MX - 62 - 36 - 410]
        for k, chunk in enumerate(paginate(rows, widths, 7, BODY_BOTTOM - BODY_TOP - 4)):
            d.frame("最近の更新" + ("（続き）" if k else ""), "最近の更新", "新しく使えるようになった機能・変更点です（新しい順）。")
            d.table(MX, BODY_TOP + 2, widths, ["日付", "区分", "内容", "関連する機能"], chunk, size=7)

    # 機能（カテゴリ → 画面ごと）
    for cat in CATEGORY_ORDER:
        cfeats = [r for r in feats if cat_of(r["機能ID"]) == cat]
        if not cfeats:
            continue
        found_toc[cat] = d.page_no + 1
        groups: dict[str, list[dict]] = {}
        if cat.startswith("はじめに"):
            groups[""] = cfeats
        else:
            for r in cfeats:
                groups.setdefault(r.get("画面ID", ""), []).append(r)
            # スクショが無く機能が少ない画面はまとめて1表に
            small = [k for k, v in groups.items() if (not k or k not in urls) and len(v) <= 2 and len(groups) > 1]
            if len(small) > 1:
                merged = [r for k in small for r in groups.pop(k)]
                groups["__misc"] = merged
        for sid_, rows_ in groups.items():
            screen = by_screen.get(sid_, {})
            if sid_ and sid_ != "__misc":
                found_screens.setdefault(sid_, d.page_no + 1)
            render_feature_group(d, cat, sid_, screen, rows_, urls, sizes, screens, unapproved, mode, ucs)
            if sid_ == "__misc":
                for r in rows_:
                    if r.get("画面ID"):
                        found_screens.setdefault(r["画面ID"], d.page_no)

    # 逆引き
    if ucs:
        found_toc["逆引き"] = d.page_no + 1
        order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
        ucs_sorted = sorted(ucs, key=lambda r: (order.get(r.get("カテゴリ"), 99), r["UCID"]))
        rows = [[r["やりたいこと"], r.get("手順（概要）", ""),
                 "、".join(names.get(i, i) for i in split_ids(r.get("使う機能ID", ""))),
                 (r.get("カテゴリ") or "").split("（")[0]] for r in ucs_sorted]
        widths = [190, 300, 130, W - 2 * MX - 620]
        for k, chunk in enumerate(paginate(rows, widths, 7, BODY_BOTTOM - BODY_TOP - 4)):
            d.frame("逆引き：やりたいことから探す" + ("（続き）" if k else ""), "逆引き",
                    "「〇〇したい」から、使う画面と手順を引けます。機能の詳細は各章をご覧ください。")
            d.table(MX, BODY_TOP + 2, widths, ["やりたいこと", "手順", "使う機能", "章"], chunk, size=7)

    # FAQ
    if faqs:
        found_toc["FAQ"] = d.page_no + 1
        order = {c: i for i, c in enumerate(["全般", "対応媒体・目的", "アカウント・連携", "与件・配信設計", "見積", "クリエイティブ・入稿",
                                             "レポート", "予算・運用", "権限・ユーザー", "セキュリティ・データ", "料金・契約", "導入・サポート"])}
        fs = sorted(faqs, key=lambda r: (order.get(r.get("カテゴリ"), 99), r["FAQID"]))
        rows = [[r.get("カテゴリ", ""), r["質問"], r.get("回答", "") or "（確認中）"] for r in fs]
        widths = [62, 210, W - 2 * MX - 272]
        for k, chunk in enumerate(paginate(rows, widths, 7, BODY_BOTTOM - BODY_TOP - 4)):
            d.frame("よくあるご質問（FAQ）" + ("（続き）" if k else ""), "FAQ")
            d.table(MX, BODY_TOP - 10, widths, ["分類", "ご質問", "回答"], chunk, size=7)
    return d, found_toc, found_screens


def short_name(name: str) -> str:
    """一覧用の短い機能名。カッコ書きの補足を落とす（省略記号は使わない）。"""
    return re.sub(r"[（(][^）)]*[）)]", "", name).strip() or name


def norm_menu(level1: str) -> str:
    return "DealDesk" if level1.replace("-", "").lower() == "dealdesk" else level1


def feature_rows(rows: list[dict], with_settings_col: bool) -> list[list[str]]:
    out = []
    for r in rows:
        body = r.get("できること", "")
        if r.get("何のため（目的）"):
            body += f"\n【目的】{r['何のため（目的）']}"
        if not with_settings_col and r.get("設定項目・選択肢"):
            body += f"\n【設定】{r['設定項目・選択肢']}"
        media = r.get("対応媒体", "")
        name = r["機能名"] + (f"\n（{media}）" if media not in ("", "共通", "Meta・TikTok") and media not in r["機能名"] else "")
        if r.get("提供状態") not in (RELEASED, ""):
            name += f"\n［{r['提供状態']}］"
        row = [name, body]
        if with_settings_col:
            row.append(r.get("設定項目・選択肢", ""))
        row.append(r.get("制約・注意", ""))
        out.append(row)
    return out


def render_feature_group(d: Deck, cat: str, sid_: str, screen: dict, rows: list[dict], urls: dict, sizes: dict,
                         screens: list[dict], unapproved: set, mode: str, ucs: list[dict]):
    title = screen.get("画面名") if screen else ("その他の機能" if sid_ == "__misc" else cat.split("（")[0])
    path = " ＞ ".join(x for x in (screen.get("階層1"), screen.get("階層2"), screen.get("階層3")) if x) if screen else ""
    lead = screen.get("この画面でやること", "") if screen else ""
    has_img = bool(sid_ and sid_ in urls)
    marks_all = [i for i, r in enumerate(rows) if mode == "draft" and r["機能ID"] in unapproved]
    if has_img:
        # 左: 画面 / 右: 機能表（機能・できること＋目的＋設定・注意）
        lw = 318
        widths = [76, 196, W - 2 * MX - lw - 8 - 76 - 196]
        trs = feature_rows(rows, with_settings_col=False)
        chunks = paginate(trs, widths, 7, BODY_BOTTOM - BODY_TOP - 2)
        start = 0
        for k, chunk in enumerate(chunks):
            d.frame(title + ("（続き）" if k else ""), cat, "")
            # 画面（縦横比を保って枠に収める）
            iw, ih = sizes.get(sid_, (16, 9))
            bw, bh = lw, 190
            scale = min(bw / iw, bh / ih)
            w, h = iw * scale, ih * scale
            d.image(MX, BODY_TOP - 12, w, h, urls[sid_])
            y = BODY_TOP - 12 + h + 6
            kids = [s for s in screens if s.get("遷移元", "").startswith(sid_) and s.get("階層3") and s["画面ID"] in urls]
            if k == 0 and kids:
                kw = (lw - 6) / 2
                for j, kid in enumerate(kids[:2]):
                    kiw, kih = sizes.get(kid["画面ID"], (16, 9))
                    ks = min(kw / kiw, 80 / kih)
                    d.image(MX + j * (kw + 6), y, kiw * ks, kih * ks, urls[kid["画面ID"]])
                    d.text(MX + j * (kw + 6), y + kih * ks + 1, kw, 10, f"▲ {kid['画面名']}", size=6.5, color=SUB)
                y += 80 + 14
            info = (f"画面の場所：{path}\n" if path else "") + (lead if k == 0 else "（前ページの続き）")
            ih_ = est_lines(info, lw, 7.5) * 7.5 * 1.3 + 8
            d.text(MX, y, lw, ih_, info, size=7.5, color=TEXT, fill="#f6f8f2",
                   runs=[(0, len("画面の場所：") if path else 0, {"bold": True, "color": GREEN_DARK})])
            y += ih_ + 6
            # 余白にはこの画面を使う逆引き（やりたいこと）を入れる
            ids = {r["機能ID"] for r in rows}
            related = [u for u in ucs if ids & set(split_ids(u.get("使う機能ID", "")))]
            if k == 0 and related and BODY_BOTTOM - y > 30:
                head = "この画面でできる「やりたいこと」"
                lines, used = [], 14.0
                for u in related:
                    t = f"・{u['やりたいこと']}　{u.get('手順（概要）', '')}"
                    h_ = est_lines(t, lw, 6.8) * 6.8 * 1.3
                    if used + h_ > BODY_BOTTOM - y - 4:
                        break
                    lines.append(t)
                    used += h_
                body = head + "\n" + "\n".join(lines)
                if lines:  # 1件も入らないときは見出しだけ残さない
                    d.text(MX, y, lw, BODY_BOTTOM - y, body, size=6.8, color=TEXT,
                           runs=[(0, len(head), {"bold": True, "size": 7.5, "color": GREEN_DARK})])
            marks = {i - start for i in marks_all if start <= i < start + len(chunk)}
            d.table(MX + lw + 8, BODY_TOP - 12, widths, ["機能", "できること", "注意"], chunk, size=7, marks=marks)
            start += len(chunk)
    else:
        widths = [118, 270, 150, W - 2 * MX - 118 - 270 - 150]
        trs = feature_rows(rows, with_settings_col=True)
        lead_text = (f"画面の場所：{path}　" if path else "") + lead
        chunks = paginate(trs, widths, 7, BODY_BOTTOM - BODY_TOP - (6 if lead_text else -10))
        start = 0
        for k, chunk in enumerate(chunks):
            d.frame(title + ("（続き）" if k else ""), cat, lead_text)
            marks = {i - start for i in marks_all if start <= i < start + len(chunk)}
            d.table(MX, BODY_TOP + (2 if lead_text else -10), widths, ["機能", "できること", "設定項目・選択肢", "注意"],
                    chunk, size=7, marks=marks)
            start += len(chunk)


# ---- 出力 ------------------------------------------------------------------------
def next_draft_version(sid: str) -> int:
    return sum(1 for r in read_tab(sid, "版管理") if r.get("種類") == "draft") + 1


def new_presentation(cfg: dict, title: str) -> str:
    pid = call("slides.presentations.create", {}, {"title": title})["presentationId"]
    if cfg.get("folder_id"):
        subprocess.run(["gog", "--account", cfg["account"], "drive", "move", pid, "--parent", cfg["folder_id"]],
                       capture_output=True, check=True)
    return pid


def record_version(cfg: dict, label: str, kind: str, pid: str, n_approved: int, memo: str, pdf: str = ""):
    call("sheets.spreadsheets.values.append",
         {"spreadsheetId": cfg["master_sheet_id"], "range": "版管理!A1", "valueInputOption": "RAW"},
         {"values": [[label, dt.datetime.now(JST).isoformat(timespec="minutes"), kind,
                      f"https://docs.google.com/presentation/d/{pid}/edit", pdf, n_approved, memo]]})


def ensure_presentation(cfg: dict, key: str, title: str) -> str:
    pid = cfg.get(key)
    if not pid:
        pid = call("slides.presentations.create", {}, {"title": title})["presentationId"]
        if cfg.get("folder_id"):
            subprocess.run(["gog", "--account", cfg["account"], "drive", "move", pid, "--parent", cfg["folder_id"]],
                           capture_output=True, check=True)
        cfg[key] = pid
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return pid


def replace_all(pid: str, deck: Deck):
    old = [s["objectId"] for s in call("slides.presentations.get", {"presentationId": pid, "fields": "slides(objectId)"}).get("slides", [])]
    reqs = deck.req + [{"deleteObject": {"objectId": o}} for o in old]
    # コマンドライン引数の長さ制限があるので、約60KBずつ分けて送る
    batch, size = [], 0
    for r in reqs:
        n = len(json.dumps(r, ensure_ascii=False).encode())
        if batch and size + n > 60_000:
            call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": batch})
            batch, size = [], 0
        batch.append(r)
        size += n
    if batch:
        call("slides.presentations.batchUpdate", {"presentationId": pid}, {"requests": batch})


def data_hash(data: dict) -> str:
    """掲載内容（行データ）のハッシュ。表紙の日付だけ変わった場合は同じ値になる。"""
    return hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def last_archived_hash(sid: str, kind: str) -> str:
    rows = [r for r in read_tab(sid, "版管理") if r.get("種類") == kind]
    return rows[-1].get("メモ", "").removeprefix("hash:") if rows else ""


def archive(cfg: dict, pid: str, kind: str, n_rows: int, digest: str):
    stamp = dt.datetime.now(JST).strftime("%Y%m%d")
    from pdf_export import export_pdf  # Drive export のサイズ上限を避けて分割書き出し
    pdf = export_pdf(pid, HERE / f"{TITLES[kind]}_{stamp}.pdf")
    link = ""
    if cfg.get("archive_folder_id"):
        up = subprocess.run(["gog", "--account", cfg["account"], "-j", "drive", "upload", str(pdf),
                             "--parent", cfg["archive_folder_id"]], capture_output=True, text=True, check=True)
        res = json.loads(up.stdout)
        link = (res.get("file") or res).get("webViewLink", "")
        pdf.unlink()
    call("sheets.spreadsheets.values.append",
         {"spreadsheetId": cfg["master_sheet_id"], "range": "版管理!A1", "valueInputOption": "RAW"},
         {"values": [[stamp, dt.datetime.now(JST).isoformat(timespec="minutes"), kind,
                      f"https://docs.google.com/presentation/d/{pid}/edit", link or str(pdf), n_rows, f"hash:{digest}"]]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["draft", "prod"])
    ap.add_argument("--lite", action="store_true")
    ap.add_argument("--archive", action="store_true")
    ap.add_argument("--note", default="", help="版管理のメモ欄に書く変更内容")
    ap.add_argument("--same-version", action="store_true",
                    help="下書き: 版番号を上げず、最新の下書き版を作り直す（同じ修正回の中での再生成用）")
    a = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    kind = "prod_lite" if a.lite else a.mode
    picked = assets.pick_up_screenshot_folder(cfg)
    if picked:
        print(f"スクショ用フォルダから {picked} 件をサイトマップに反映")
    art = assets.sync(cfg)
    data = load_rows(cfg["master_sheet_id"], a.mode, a.lite)
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    n = next_draft_version(cfg["master_sheet_id"]) - (1 if a.same_version else 0)
    version = f"v{n}" if a.mode == "draft" else ""
    # 1回目でページ番号を確定させ、2回目で目次・サイトマップに番号を入れて本番描画
    _, toc, sp = render(data, a.mode, a.lite, art, today, None, None, version)
    deck, _, _ = render(data, a.mode, a.lite, art, today, toc, sp, version)
    if a.mode == "draft" and a.same_version:
        pid = cfg["draft_presentation_id"]  # 最新版を上書き
        replace_all(pid, deck)
    elif a.mode == "draft":
        # 下書きは版ごとに別ファイルで残す（v1, v2, ...）。URL は版管理タブに記録
        pid = new_presentation(cfg, f"{TITLES['draft']} {version}（{today}）")
        replace_all(pid, deck)
        n_ok = sum(1 for r in data["機能一覧"] if r.get("承認") == APPROVED)
        record_version(cfg, f"下書き{version}", "draft", pid, n_ok, f"{deck.page_no}ページ" + (f"／{a.note}" if a.note else ""))
        cfg["draft_presentation_id"] = pid
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    else:
        pid = ensure_presentation(cfg, f"{kind}_presentation_id", TITLES[kind])
        replace_all(pid, deck)
    print(f"{kind}{(' ' + version) if version else ''}: {deck.page_no} pages, {len(data['機能一覧'])} features")
    print(f"https://docs.google.com/presentation/d/{pid}/edit")
    if a.archive and a.mode == "prod":
        digest = data_hash(data)
        if digest == last_archived_hash(cfg["master_sheet_id"], kind):
            print("内容に変化なし。PDF 保存はスキップ")
        else:
            archive(cfg, pid, kind, len(data["機能一覧"]), digest)
            print("PDF を保存し版管理に記録")


if __name__ == "__main__":
    main()
