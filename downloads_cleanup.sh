#!/bin/bash
# ダウンロードフォルダ整理スクリプト（2026-11-17 作成）
#
#   bash downloads_cleanup.sh        … 予定を表示するだけ（何も動かさない）
#   bash downloads_cleanup.sh --go   … 実行する
#
# - 「削除」はすべて ~/.Trash（ゴミ箱）へ移すだけ。ゴミ箱を空にするまで戻せる。
# - 「Drive へ移動」は Google Drive for Desktop のフォルダへ mv する（自動でアップロードされる）。
# - 移動先に同名ファイルがある場合は上書きせずスキップする。
# - 判定は 2026-11-17 時点のダウンロード一覧（md5）と Drive の照合結果に基づく。
set -u
GO=0; [ "${1:-}" = "--go" ] && GO=1
DL="$HOME/Downloads"

# ---- Google Drive for Desktop のパス検出 ----
ROOT=$(ls -d "$HOME"/Library/CloudStorage/GoogleDrive-* 2>/dev/null | head -1)
[ -z "$ROOT" ] && { echo "Google Drive for Desktop のフォルダが見つかりません"; exit 1; }
if [ -d "$ROOT/マイドライブ" ]; then MY="$ROOT/マイドライブ"; else MY="$ROOT/My Drive"; fi
if [ -d "$ROOT/共有ドライブ" ]; then SH="$ROOT/共有ドライブ"; else SH="$ROOT/Shared drives"; fi

UUUM="$MY/01_Desktop共有/UUUM関連_Yuki"
UUUM_TEIAN="$UUUM/UUUM提案書"
HAWK="$SH/FreakOut BizAll/07_HAWK"
H_GAIYO="$HAWK/01_概要資料"
H_OLD="$H_GAIYO/旧バージョン"
H_SALES="$HAWK/03_セールス活動"
H_SHIRYO=$(ls -d "$HAWK"/05_* 2>/dev/null | head -1)
H_HIRO="$HAWK/14_HIROGARU"
H_REPORT="$MY/01_Desktop共有/HAWKレポート出力"
BAITAI="$MY/70_他部署・媒体資料"
KOJIN="$MY/90_個人"
KOHO="$MY/_削除候補/Downloads整理_20261117"
SECRETS="$HOME/.secrets/google"

n_trash=0; n_move=0; n_skip=0
trash() {
  local f="$DL/$1"
  [ -e "$f" ] || { echo "  (なし) $1"; return; }
  if [ $GO = 1 ]; then
    local dst="$HOME/.Trash/$1"; [ -e "$dst" ] && dst="$HOME/.Trash/$(date +%H%M%S)_$1"
    mv "$f" "$dst" && echo "  🗑  $1"
  else echo "  🗑  $1"; fi
  n_trash=$((n_trash+1))
}
move() {  # move <ファイル名> <移動先フォルダ> [新しい名前]
  local f="$DL/$1" dir="$2" name="${3:-$1}"
  [ -e "$f" ] || { echo "  (なし) $1"; return; }
  if [ ! -d "$(dirname "$dir")" ]; then echo "  ⚠ 移動先の親フォルダがない: $dir → スキップ"; n_skip=$((n_skip+1)); return; fi
  if [ -e "$dir/$name" ]; then echo "  ⚠ 移動先に同名あり: $name → スキップ"; n_skip=$((n_skip+1)); return; fi
  if [ $GO = 1 ]; then mkdir -p "$dir" && mv "$f" "$dir/$name" && echo "  →  $name"; else echo "  →  $name"; fi
  n_move=$((n_move+1))
}

echo "Drive: $ROOT"
[ $GO = 0 ] && echo "※ 予定表示モード。実行するには: bash $0 --go"

echo; echo "■ 1. Drive に同じファイルがある → ゴミ箱（中身の md5 一致）"
for f in \
 "01_UUUMマーケ秘密保持契約書-1.docx" "02_UUUMマーケ委託業務委託基本契約書.docx" \
 "20_UUUMマーケ受託プロモーション業務委託基本契約書タイアップ案件用.docx" \
 "20260907_株式会社ツナググループ・ホールディングス_秘密保持契約書_tghd1021_FO1028.docx" \
 "2609_UUUMマーケティング株式会社_説明資料_.pdf" "【リックコミュニケーションズ様】UUUMマーケティング_説明資料.pdf" \
 "842574268_1779764443086136_1600483669560707582_n.png" \
 "Allis志村様_【Freakout】alpakaレポートサンプル資料_2026年6月版.pptx のコピー.pptx" \
 "Allis志村様_【Freakout】alpakaレポートサンプル資料_2026年6月版.pptx のコピー(1).pptx" \
 "AROUND様_HAWK_申込書_0713.xlsx" "ASE媒体資料_2026_07-09.pptx.pdf" "FO_HAWK press release drafting 052826.pdf" \
 "FreakOut DOOH_ご紹介資料_202607-09.pdf" "FreakOut_alpaka媒体資料_2026_10-12月.pptx" \
 "【薬院オーガニック株式会社様】FreakOut_alpaka媒体資料_2026_10-12月.pptx" "04_FreakOut_alpaka媒体資料_2026_10-12月.pdf" \
 "FreakOut_HAWK_Overview_2026_10-12.pdf" "【gaaboo様】HAWK_META_TIKTOK_セットアップガイド_オンボーディング.pdf" \
 "gmo_nikko_sales_pitch_07022026.mp4" "GP_媒体資料2026.pptx.pdf" "HAWK_DealDesk_概要_1枚版.pdf" \
 "HAWK_Overview_202610版_20261026.pdf" "HAWK_ウェビナー資料_株式会社フリークアウト_0929.pdf" \
 "HAWK_お申込みフォーム_利用規約・特記事項.docx" "Hawkサービス利用規約_0401制定.docx" "hirogaru_info.pdf" \
 "HIROGARU_フォーム入力シート_0817.csv" "result0814-1.csv" "result0814-1 (1).csv" \
 "image (3).png" "image (4).png" "image (5).png" "image (6).png" "image (7).png" "image (8).png" \
 "image (9).png" "image (10).png" "image (11).png" "image (12).png" "image (13).png" "【新機能】DealDeskのご案内.png" \
 "IMG_4352.JPG" "IMG_4353.JPG" "IMG_4397.JPG" "IMG_4420.JPG" "IMG_4436.JPG" "IMG_4436 2.JPG" \
 "IMG_4446.JPG" "IMG_4447.JPG" "IMG_4462.JPG" \
 "Instagramオリエンシート商材名_クリエイター名2609.xlsx" "YouTubeオリエンシート商材名_クリエイター名260801-4.xlsx" \
 "フォーマット_PORT募集施策_オリエンシート-1.xlsx" "【再生保証PKG】Influencer PORT.pptx" "【再生保証PKG】Influencer PORT (1).pptx" \
 "【最新】Influencer PORT_PORT募集 概要資料 .pdf" \
 "【MASCODE】UUUMオリエンシート_ストーリーズ_仮入力_261021.xlsx" "【MASCODE】UUUMオリエンシート_リール_仮入力_261021.xlsx" \
 "Meta_インサイトレポート_FreakOut_採用_20260625_163835.pptx" "Meta_インサイトレポート_FreakOut_採用_20260625_163835 (1).pptx" \
 "UUUMマーケ4Q事業報告会_2026-09-29_スライド抜き出し.pdf" "UUUMマーケティング申込書個別契約内容.docx" \
 "UUUM様 ライブ監視POC ディスカッションペーパー.pdf" "アーカイブ録画.mp4" "【オーリーズ様】HAWK_申込書_0915.xlsx" \
 "ツナグHD様_システム導入ヒアリングリスト_1005.xlsx" \
 "【六本木セントラルタワー】来客事前予約システム-ユーザーマニュアル2025.1.10.pdf" \
 ; do trash "$f"; done

echo; echo "■ 2. Drive に同じ資料の別形式・新しい版がある → ゴミ箱"
for f in \
 "CMB登壇資料_Google様LCSチーム向け×UUUM.pptx" \
 "Allis志村様_04_パッケージ_メンズ美容業界.pdf" "Allis志村様_【alpaka】業種別マスキング事例 のコピー.pdf" \
 "Allis志村様_GP_ABS_VTBSでの実績.pdf" "Allis志村様_VTBS.pdf" "Allis志村様_セルフサーブ.pdf" \
 "【Allis様】HAWK_META_TIKTOK_セットアップガイド_オンボーディング.pptx" \
 "【オーリーズ様】HAWK_META_TIKTOK_セットアップガイド_オンボーディング.pptx のコピー.pptx" \
 "【ピーエーシー様】UUUMマーケティング ご紹介 ディスカッションシート_20261028.pdf" \
 "【ビジョン様】HAWKオンボーディング_ディスカッションシート_20261016.pdf" \
 "HAWK Overview 05182026（日本語版・最新）.pdf" "HAWK Overview 202607版.pdf" "HAWK_Overview_202607.pdf" \
 "HAWK 顧客要望・Q&A 集約シート_10_19時点（開発優先度すり合わせ用） のコピー.xlsx" \
 "HAWK_DeepResearch_プロンプト設計と基本情報パック_20260920.md" "HAWK_申込書_リソースクリエーション様_0721.xlsx" \
 "HAWK紹介パートナープログラム_ver1.pdf" "HAWK紹介パートナープログラム_ver1 (1).pdf" "HAWK_競合比較.pptx" \
 "HAWKアタックリスト - HIROGARUリスト.csv" "HAWK_共催ウェビナー資料_株式会社フリークアウト_1027.pdf" \
 "Meta_インサイトレポート_FO_526_鳴門ボートレース_20260716_143048.pptx" \
 "mns-orri-eos (2026-09-18 18_28 GMT+9).mp4" "フリークアウト会社案内_20260408.pptx.pdf" \
 "【FreakOut】alpaka媒体資料_2026_4-6月.pptx.pdf" "【BtoB ソリューションのご紹介】_Ver.4.pptx.pdf" \
 "05_【alpaka】業種別事例.pdf" \
 ; do trash "$f"; done

echo; echo "■ 3. 不要（インストーラー・一時ファイル・重複・展開済み zip）→ ゴミ箱"
for f in \
 "Antigravity IDE.dmg" "Antigravity.dmg" "Aqua-Voice-macOS-arm64.dmg" "Chatwork.dmg" "Gemini.dmg" "Obsidian-1.12.7.dmg" \
 "Claude.dmg" "Claude (1).dmg" "Claude (2).dmg" "Claude (3).dmg" "Claude (4).dmg" \
 "gogcli_0.19.0_linux_amd64.tar.gz" \
 "~\$260907_株式会社ツナググループ・ホールディングス_秘密保持契約書.docx" \
 "gdocs-hyperlink.skill" "hawk-inbound-lead.skill" "kabeuchi-grill.skill" "scheduled-task-routine.skill" "SKILL.md" \
 "New chat - Claude.html" "New chat - Claude_files" \
 "fwd.zip" "re.zip" "HiroLocal.zip" \
 "(1) 入退館用QRコード - 211842.gif" "(1) 入退館用QRコード - 811664.gif" "largebanner-k-airism-image0601-sp-jp.avif" \
 "HAWK_simulator_panorama (1).png" \
 "Meta_インサイトレポート_SNS広告伴走型AIエージェント_HAWK_20260818_135537 (1).pptx" \
 "IMG_4615 (1).jpg" "IMG_4615 2.jpg" "S__79667221_0 (1).jpg" "S__79667221_0 (2).jpg" "S__79667221_0 (3).jpg" \
 "client_secret_2_317751427169-bdbna2uqshmrs782e1csaj6evc6rab54.apps.googleusercontent.com (1).json" \
 "client_secret_2_317751427169-bdbna2uqshmrs782e1csaj6evc6rab54.apps.googleusercontent.com (2).json" \
 "client_secret_2_317751427169-bdbna2uqshmrs782e1csaj6evc6rab54.apps.googleusercontent.com (3).json" \
 ; do trash "$f"; done

echo; echo "■ 4. UUUM → マイドライブ/01_Desktop共有/UUUM関連_Yuki"
move "250402｜UUUMインフルエンサーマーケ（エントリープラン） (1).pptx" "$UUUM" "250402｜UUUMインフルエンサーマーケ（エントリープラン）.pptx"
move "UUUM_テックソリューション_リデザイン.pptx" "$UUUM_TEIAN"
move "UUUMマーケティングテックソリューション.pptx" "$UUUM_TEIAN"

echo; echo "■ 5. HAWK → 共有ドライブ FreakOut BizAll/07_HAWK"
move "【概要資料】HAWK_Overview_株式会社フリークアウト.pdf" "$H_GAIYO"
move "HAWK_概要資料_Yuki作_0531 (5).pptx" "$H_OLD" "HAWK_概要資料_Yuki作_0531.pptx"
move "HAWK_simulator_panorama.png" "$H_SHIRYO"
move "hawk-simulator.png" "$H_SHIRYO"
move "HAWK_レポートサンプル.pdf" "$H_SHIRYO"
for f in "HAWK向け顧客リスト（株式会社ありで検索）.csv" "HAWK向け顧客リスト（株式会社ありで検索）_携帯電話追加.csv" \
 "HAWK向け顧客リスト（株式会社なしで検索）.csv" "HAWK向け顧客リスト（株式会社なしで検索）_携帯電話追加.csv" \
 "HAWK_S級エンリッチ済み_20260817.tsv" "HAWK採用シグナルリスト_20260817.tsv" "送信成功リスト.csv"; do move "$f" "$H_SALES"; done
move "HIROGARU_フォーム入力シート_0817 - リスト元データ.csv" "$H_HIRO"
move "form01_0813].csv" "$H_HIRO"

echo; echo "■ 6. HAWK が出力したレポート試作 → マイドライブ/01_Desktop共有/HAWKレポート出力（共有ドライブに入れるとノイズなので個人側）"
for f in "$DL"/Meta_インサイトレポート_*.pptx "$DL"/Meta_パフォーマンスレポート_*.xlsx "$DL"/meta_insight_campaign_*.pptx \
         "$DL"/meta_performance_*.xlsx "$DL"/tiktok_insight_campaign_*.pptx "$DL"/施策プラン_*.pptx; do
  [ -e "$f" ] && move "$(basename "$f")" "$H_REPORT"
done

echo; echo "■ 7. その他 → マイドライブ"
move "2608_TSIスペシャルサンクスセール_実施概要_配信用.pdf" "$BAITAI"
move "講談社様 10月度定例会資料20261016.pdf" "$BAITAI"
move "労務オリエンテーション20260515版（正社員入社対象） .pdf" "$KOJIN"

echo; echo "■ 8. 中身が判断できないもの → マイドライブ/_削除候補/Downloads整理_20261117（後で見て消す）"
for f in "229.jpg" "229 2.jpg" "S__79667220_0.jpg" "S__79667221_0.jpg" "S__79667222_0.jpg" "IMG_4014_Original.jpg" "IMG_4615.jpg" \
 "image.png" "image (1).png" "image (2).png" "6a869c5b47af2_スクリーンショット 2026-08-20 15.13.51.png" \
 "スクリーンショット 2026-06-01 171449.png" "スクリーンショット 2026-07-02 11.00.08.png" "スクリーンショット 2026-07-21 18.45.38.png" \
 "screencapture-ai-tool-userlocal-jp-llmo-checker-reports-FtQr7zy2cLAkvdwPeRaS4Mx5-2026-08-24-18_01_31.pdf" \
 "screencapture-fout-qiita-Monta-wara-items-7093a7fa68448a858f06-2026-09-04-15_04_04.pdf" \
 "screencapture-fout-qiita-Monta-wara-items-7093a7fa68448a858f06-2026-09-04-15_04_04.png" \
 "______________________________________20260401.xlsx" "【入稿シート】2026.xlsx" "rakurakuLunch.zip" \
 "competitorwatchshare.md" "chrome-mv3" "fwd" "re"; do move "$f" "$KOHO"; done

echo; echo "■ 9. 認証情報（Drive には上げない）→ ~/.secrets/google（本人のみ読める）"
if [ $GO = 1 ]; then mkdir -p "$SECRETS" && chmod 700 "$HOME/.secrets" "$SECRETS"; fi
S="client_secret_2_317751427169-bdbna2uqshmrs782e1csaj6evc6rab54.apps.googleusercontent.com"
for pair in "$S.json|gog-fout_client_secret_A.json" "$S (4).json|gog-fout_client_secret_B.json" \
            "spreadsheet-sync-bot-1d3f49791b76.json|spreadsheet-sync-bot-1d3f49791b76.json"; do
  src="${pair%%|*}"; dst="${pair##*|}"
  [ -e "$DL/$src" ] || { echo "  (なし) $src"; continue; }
  if [ -e "$SECRETS/$dst" ]; then echo "  ⚠ 同名あり: $dst → スキップ"; continue; fi
  if [ $GO = 1 ]; then mv "$DL/$src" "$SECRETS/$dst" && chmod 600 "$SECRETS/$dst"; fi
  echo "  🔒 $src → ~/.secrets/google/$dst"
done

echo; echo "■ 残すもの（触らない）: HiroLocal フォルダ（中身を確認してから判断）"
echo; echo "ゴミ箱: ${n_trash} 件 / Drive へ移動: ${n_move} 件 / スキップ: ${n_skip} 件"
echo; echo "ダウンロードに残っているもの:"; ls -1A "$DL" | grep -v '^\.DS_Store$' | grep -v '^\.localized$' | sed 's/^/  /'
