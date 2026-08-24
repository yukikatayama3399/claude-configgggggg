#!/usr/bin/env python3
"""company_match の照合ロジックの自己テスト。`python3 test_company_match.py` で実行。

表記ゆれで既存顧客に営業をかけるのが一番まずいので、実際に取りこぼした表記を
そのままケースにしてある。逆に「似ているだけの別会社」を落とさないことも見る。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_match import Exclusion, domain, key, load_extra

EXCLUDED = [
    "株式会社電通デジタル", "トランスコスモス株式会社", "パナソニック コネクト株式会社",
    "株式会社ADKマーケティング・ソリューションズ", "楽天グループ株式会社",
    "株式会社サイバーエージェント", "ラクスル株式会社", "株式会社ｅｃｂｅｉｎｇ",
    "株式会社UPVILLAGE", "株式会社W-ENDLESS", "株式会社売れるネット広告社",
    "株式会社LiB", "Blue株式会社", "株式会社ライト", "株式会社ハンズ", "株式会社ポート",
    "株式会社ライン", "エッセンス株式会社",
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
    # 2026-08-24 から「迷ったら落とす」に変更した分（以前は通していた）
    "株式会社Lib Work": "株式会社LiB",        # 社名の一部だけ一致
    "Blue Zone株式会社": "Blue株式会社",      # 社名の一部だけ一致
    "合同会社ライト": "株式会社ライト",          # 法人格違いの完全一致
}
# 落としてはいけない社名。正規化の副作用で偶然文字列が含まれるだけのもの。
# ここまで落とすと正常な見込み客が100社以上飛ぶので、線はここに引いてある。
MUST_MISS = [
    "みらい人材サポート株式会社",   # 「サポート」に「ポート」が含まれるだけ
    "株式会社アズライト",         # 「アズライト」に「ライト」が含まれるだけ
    "株式会社スタートライン",      # 「スタートライン」に「ライン」が含まれるだけ
    "ホワイトエッセンス株式会社",   # 「ホワイトエッセンス」に「エッセンス」が含まれるだけ
    "株式会社よその知らない会社",
]
# exclude_extra.tsv で個別に落とすもの（社名変更・親子会社・迷う先）
MUST_HIT_EXTRA = [
    "クラシル株式会社",                              # 旧 dely株式会社
    "株式会社メディカルハンズ",
    "NTT東日本株式会社",
    "株式会社フロンティアダイレクト デジタルソリューション部",  # 個別指定 + 部署付き
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    extra = load_extra(os.path.join(here, "exclude_extra.tsv"))
    if not extra:
        print("NG exclude_extra.tsv が読めていない")
        return 1
    ex = Exclusion(EXCLUDED, extra)
    failed = 0
    for name, src in MUST_HIT.items():
        hit = ex.hit(name)
        if not hit or hit[1] != src:
            print(f"NG 落とせていない: {name} -> {hit}")
            failed += 1
    for name in MUST_HIT_EXTRA:
        if not ex.hit(name):
            print(f"NG 個別指定が効いていない: {name}")
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
    total = len(MUST_HIT) + len(MUST_HIT_EXTRA) + len(MUST_MISS)
    print(f"{total}件中 {failed}件 失敗")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
