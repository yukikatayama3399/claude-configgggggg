#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""あゆみのほけん相談室の「過去キャンペーン実績」サンプル10件を生成する。

数値の整合ルール（既存サンプル行から逆算した仕様）:
  消化額 = imp * CPM / 1000
  クリック = imp * クリック率
  リーチ   = imp / フリークエンシー
  平均行   = インプレッション加重平均（CPM・クリック率とも）

目的別のクリック率の着地点:
  リード / 売上(CV)  -> 加重平均 1.34%
  認知               -> 加重平均 0.60%
"""
import json

ADVERTISER = "株式会社あゆみのほけん相談室"
ACCOUNT = "あゆみのほけん相談室"

# (キャンペーン名, 目的, 消化額, CPM狙い, クリック率, フリークエンシー, 開始, 終了)
ROWS = [
    # ---- リード獲得 5本（クリック率 加重平均 1.34% に着地）----
    ("あゆみのほけん相談室_新年の家計見直し無料相談リード_2501", "リード", 1_240_000, 712, 1.12, 1.42, "2025/01/14", "2025/02/13"),
    ("あゆみのほけん相談室_新生活ライフプラン相談リード_2504",   "リード", 1_680_000, 768, 1.28, 1.61, "2025/04/07", "2025/05/11"),
    ("あゆみのほけん相談室_学資保険オンライン相談リード_2509",   "リード", 2_150_000, 803, 1.41, 1.88, "2025/09/01", "2025/10/05"),
    ("あゆみのほけん相談室_年末保険見直しキャンペーンリード_2511","リード", 1_090_000, 690, 1.54, 1.35, "2025/11/04", "2025/12/14"),
    ("あゆみのほけん相談室_老後資金セミナー予約リード_2603",     "リード", 1_460_000, 845, 1.35, 1.74, "2026/03/02", "2026/04/05"),
    # ---- 認知 5本（クリック率 加重平均 0.60% に着地）----
    ("あゆみのほけん相談室_ブランド認知_2502",                   "認知",   1_320_000, 402, 0.50, 2.35, "2025/02/20", "2025/03/23"),
    ("あゆみのほけん相談室_相談無料訴求リーチ拡大認知_2506",     "認知",   2_480_000, 366, 0.57, 2.78, "2025/06/02", "2025/07/13"),
    ("あゆみのほけん相談室_新店舗オープン告知認知_2510",         "認知",   1_150_000, 448, 0.63, 1.92, "2025/10/06", "2025/11/09"),
    ("あゆみのほけん相談室_子育てファミリー層認知_2601",         "認知",   1_010_000, 421, 0.69, 1.63, "2026/01/13", "2026/02/15"),
    ("あゆみのほけん相談室_春の保険見直し認知_2604",             "認知",   1_420_000, 385, 0.66, 2.21, "2026/04/13", "2026/05/17"),
]


def build():
    out = []
    for name, purpose, spend, cpm_target, ctr, freq, start, end in ROWS:
        imp = round(spend / cpm_target * 1000)
        cpm = round(spend / imp * 1000)          # 表示用CPMを実数から再計算（整合保証）
        clicks = round(imp * ctr / 100)
        ctr_disp = round(clicks / imp * 100, 2)  # 表示用クリック率も再計算
        reach = round(imp / freq)
        freq_disp = round(imp / reach, 2)
        out.append({
            "advertiser": ADVERTISER,
            "campaign_name": name,
            "ad_account": ACCOUNT,
            "objective": purpose,
            "impressions": imp,
            "cpm": cpm,
            "clicks": clicks,
            "ctr": ctr_disp,
            "reach": reach,
            "frequency": freq_disp,
            "spend": spend,
            "start_date": start,
            "end_date": end,
        })
    return out


HEADERS = ["広告主", "キャンペーン名", "広告アカウント", "目的", "imp", "CPM",
           "クリック", "クリック率", "リーチ", "フリークエンシー", "消化額",
           "配信開始", "配信終了", "配信期間"]


def tsv(rows):
    lines = ["\t".join(HEADERS)]
    for r in rows:
        lines.append("\t".join([
            r["advertiser"], r["campaign_name"], r["ad_account"], r["objective"],
            str(r["impressions"]), str(r["cpm"]), str(r["clicks"]),
            f'{r["ctr"]:.2f}%', str(r["reach"]), f'{r["frequency"]:.2f}',
            str(r["spend"]), r["start_date"], r["end_date"],
            f'{r["start_date"]}〜{r["end_date"]}',
        ]))
    return "\n".join(lines) + "\n"


def summary(rows):
    def agg(sub):
        imp = sum(r["imp"] if "imp" in r else r["impressions"] for r in sub)
        clk = sum(r["clicks"] for r in sub)
        spd = sum(r["spend"] for r in sub)
        return {
            "件数": len(sub),
            "imp合計": imp,
            "加重CPM": round(spd / imp * 1000),
            "加重クリック率": round(clk / imp * 100, 3),
            "消化額合計": spd,
            "消化額平均": round(spd / len(sub)),
            "消化額min": min(r["spend"] for r in sub),
            "消化額max": max(r["spend"] for r in sub),
        }
    lead = [r for r in rows if r["objective"] in ("リード", "売上")]
    awa = [r for r in rows if r["objective"] == "認知"]
    return {"リード系": agg(lead), "認知": agg(awa), "全体": agg(rows)}


if __name__ == "__main__":
    import os, sys
    rows = build()
    d = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(d, "ayumi_campaign_samples.tsv"), "w", encoding="utf-8") as f:
        f.write(tsv(rows))
    with open(os.path.join(d, "ayumi_campaign_samples.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    json.dump(summary(rows), sys.stdout, ensure_ascii=False, indent=2)
    print()
