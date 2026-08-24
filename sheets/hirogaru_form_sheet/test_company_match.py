#!/usr/bin/env python3
"""company_match の照合ロジックの自己テスト。`python3 test_company_match.py` で実行。

表記ゆれで既存顧客に営業をかけるのが一番まずいので、実際に取りこぼした表記を
そのままケースにしてある。逆に「似ているだけの別会社」を落とさないことも見る。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_match import Exclusion, domain, key

EXCLUDED = [
    "株式会社電通デジタル", "トランスコスモス株式会社", "パナソニック コネクト株式会社",
    "株式会社ADKマーケティング・ソリューションズ", "楽天グループ株式会社",
    "株式会社サイバーエージェント", "ラクスル株式会社", "株式会社ｅｃｂｅｉｎｇ",
    "株式会社UPVILLAGE", "株式会社W-ENDLESS", "株式会社売れるネット広告社",
    "株式会社LiB", "Blue株式会社", "株式会社ライト", "株式会社ハンズ",
    "株式会社フリークアウト", "GMO TECH株式会社", "株式会社DYM",
]
# 落とすべき表記 → 除外リスト上の社名
MUST_HIT = {
    "株式会社電通デジタル 港区": "株式会社電通デジタル",
    "株式会社電通デジタル 大阪市": "株式会社電通デジタル",
    "トランスコスモス株式会社 CX事業統括 サービス推進本部": "トランスコスモス株式会社",
    "トランスコスモス株式会社 渋谷区": "トランスコスモス株式会社",
    "パナソニックコネクト株式会社": "パナソニック コネクト株式会社",
    "ADKマーケティング・ソリューションズ": "株式会社ADKマーケティング・ソリューションズ",
    "楽天グループ": "楽天グループ株式会社",
    "楽天グループ 株式会社 エンジニア採用": "楽天グループ株式会社",
    "サイバーエージェントグループ": "株式会社サイバーエージェント",
    "ラクスルグループ": "ラクスル株式会社",
    "株式会社ecbeing": "株式会社ｅｃｂｅｉｎｇ",
    "株式会社UP VILLAGE": "株式会社UPVILLAGE",
    "株式会社W‐ENDLESS": "株式会社W-ENDLESS",          # ハイフンが全角ダッシュ
    "売れるネット広告社株式会社": "株式会社売れるネット広告社",  # 前株 / 後株
    "株式会社フリークアウト・ホールディングス": "株式会社フリークアウト",
    "GMO TECHホールディングス株式会社": "GMO TECH株式会社",
    "株式会社DYM 品川区": "株式会社DYM",
}
# 落としてはいけない別会社
MUST_MISS = [
    "株式会社Lib Work",        # 除外は 株式会社LiB（住宅メーカーとは別会社）
    "Blue Zone株式会社",       # 除外は Blue株式会社
    "合同会社ライト",           # 除外は 株式会社ライト（法人格が違う）
    "株式会社メディカルハンズ",   # 除外は 株式会社ハンズ
    "株式会社ラクス",           # 除外は ラクスル株式会社
    "株式会社よその知らない会社",
]


def main():
    ex = Exclusion(EXCLUDED)
    failed = 0
    for name, src in MUST_HIT.items():
        hit = ex.hit(name)
        if not hit or hit[1] != src:
            print(f"NG 落とせていない: {name} -> {hit}")
            failed += 1
    for name in MUST_MISS:
        hit = ex.hit(name)
        if hit:
            print(f"NG 別会社を落としている: {name} -> {hit}")
            failed += 1
    # 除外リストが空/極小のまま照合すると全通しになるので、呼び出し側で件数を見る前提
    assert key("株式会社Ｈ・Ｏ・Ｃ") == key("株式会社H・O・C"), "全角半角を吸収できていない"
    assert domain("要確認") == "" and domain("不明") == "", "URLでない値をドメイン扱いしている"
    assert domain("https://www.Example.co.jp/contact") == "example.co.jp"
    print(f"{len(MUST_HIT) + len(MUST_MISS)}件中 {failed}件 失敗")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
