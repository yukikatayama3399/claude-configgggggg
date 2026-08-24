/**
 * 自動追加中リスト_SNS広告求人 の新着取込
 *
 * 目的:
 *   作業シートを「静的な値」に保ったまま新着だけを追記し、
 *   H列(入力状況) / I列(送信日時) を外部作業者が手入力できる普通のセルにしておく。
 *
 * しくみ:
 *   _取込元_SNS広告求人 … IMPORTRANGE + FILTER の生データ（隠しシート・編集禁止）
 *   自動追加中リスト_SNS広告求人 … 静的な値のみ。会社名(B列)をキーに未取込の行だけ追記する。
 *   追記時に書くのは A:G と J:O だけ。H:I は絶対に触らないので入力が消えない・ズレない。
 */

var WORK_SHEET = '自動追加中リスト_SNS広告求人';
var RAW_SHEET  = '_取込元_SNS広告求人';
var LOG_SHEET  = '_同期ログ';

var KEY_COL   = 2;  // B列 = 会社名（重複判定キー）
var LAST_COL  = 15; // O列まで
/** 追記する列ブロック [開始列, 終了列]。H(8)・I(9) は意図的に除外している。 */
var WRITE_BLOCKS = [[1, 7], [10, 15]];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('新着取込')
    .addItem('🔄 いま取り込む', 'syncNewRows')
    .addSeparator()
    .addItem('⏰ 自動取込を有効化（1時間ごと）', 'installTrigger')
    .addItem('⏹ 自動取込を停止', 'removeTrigger')
    .addItem('ℹ 状態を確認', 'showStatus')
    .addToUi();
}

/** 新着行だけを作業シートに追記する。 */
function syncNewRows() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30 * 1000)) {
    log_('SKIP', 0, '他の同期が実行中');
    return 0;
  }
  try {
    var ss = SpreadsheetApp.getActive();
    var work = mustGetSheet_(ss, WORK_SHEET);
    var raw  = mustGetSheet_(ss, RAW_SHEET);

    var rawRows = readRaw_(raw);           // ヘッダー除いた生データ
    var header  = work.getRange(1, 1, 1, LAST_COL).getValues()[0];
    assertHeaderMatches_(raw, header);

    var existing = existingKeys_(work);
    var fresh = [];
    var seen  = {};
    for (var i = 0; i < rawRows.length; i++) {
      var key = normKey_(rawRows[i][KEY_COL - 1]);
      if (!key || existing[key] || seen[key]) continue;
      seen[key] = true;
      fresh.push(rawRows[i]);
    }

    if (fresh.length === 0) {
      log_('OK', 0, '新着なし');
      return 0;
    }

    var startRow = lastDataRow_(work) + 1;
    var need = startRow + fresh.length - 1;
    if (need > work.getMaxRows()) work.insertRowsAfter(work.getMaxRows(), need - work.getMaxRows() + 100);

    // H:I を跨がないよう列ブロックごとに書き込む
    WRITE_BLOCKS.forEach(function (block) {
      var from = block[0], to = block[1];
      var slice = fresh.map(function (r) { return r.slice(from - 1, to); });
      work.getRange(startRow, from, slice.length, to - from + 1).setValues(slice);
    });

    log_('OK', fresh.length, '追記 ' + startRow + '〜' + (startRow + fresh.length - 1) + '行目');
    return fresh.length;
  } catch (e) {
    log_('ERROR', 0, String(e && e.message ? e.message : e));
    throw e;
  } finally {
    lock.releaseLock();
  }
}

/** 取込元シートを読む。壊れた取込（#REF! / 読込中 / 空）なら例外を投げて追記させない。 */
function readRaw_(raw) {
  var last = raw.getLastRow();
  if (last < 2) throw new Error(RAW_SHEET + ' にデータがありません（IMPORTRANGE が失敗している可能性）');

  var values   = raw.getRange(1, 1, last, LAST_COL).getValues();
  var displays = raw.getRange(1, 1, Math.min(last, 5), LAST_COL).getDisplayValues();
  for (var r = 0; r < displays.length; r++) {
    for (var c = 0; c < displays[r].length; c++) {
      var d = String(displays[r][c]);
      if (d.indexOf('#REF') === 0 || d.indexOf('#N/A') === 0 || d.indexOf('#ERROR') === 0 || d === 'Loading...') {
        throw new Error(RAW_SHEET + ' が ' + d + ' 状態です。取込を中止しました');
      }
    }
  }

  var rows = values.slice(1).filter(function (r) { return normKey_(r[KEY_COL - 1]) !== ''; });
  if (rows.length === 0) throw new Error(RAW_SHEET + ' の有効行が 0 件です。取込を中止しました');
  return rows;
}

/** 取込元と作業シートの列構成がずれていたら止める（列を足したときの事故防止）。 */
function assertHeaderMatches_(raw, workHeader) {
  var rawHeader = raw.getRange(1, 1, 1, LAST_COL).getValues()[0];
  for (var i = 0; i < LAST_COL; i++) {
    if (normKey_(rawHeader[i]) !== normKey_(workHeader[i])) {
      throw new Error('列構成が一致しません（' + colLetter_(i + 1) + '列: 取込元「' +
        rawHeader[i] + '」/ 作業シート「' + workHeader[i] + '」）。取込を中止しました');
    }
  }
}

function existingKeys_(work) {
  var last = lastDataRow_(work);
  var map = {};
  if (last < 2) return map;
  work.getRange(2, KEY_COL, last - 1, 1).getValues().forEach(function (r) {
    var k = normKey_(r[0]);
    if (k) map[k] = true;
  });
  return map;
}

/** H:I だけ入力された行を「データあり」と誤認しないよう、キー列で最終行を判定する。 */
function lastDataRow_(work) {
  var max = work.getLastRow();
  if (max < 2) return 1;
  var keys = work.getRange(2, KEY_COL, max - 1, 1).getValues();
  for (var i = keys.length - 1; i >= 0; i--) {
    if (normKey_(keys[i][0])) return i + 2;
  }
  return 1;
}

function normKey_(v) {
  return String(v === null || v === undefined ? '' : v).replace(/\s+/g, '').trim();
}

function colLetter_(n) {
  var s = '';
  while (n > 0) { var m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = (n - 1 - m) / 26; }
  return s;
}

function log_(status, count, note) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(LOG_SHEET);
  if (!sh) {
    sh = ss.insertSheet(LOG_SHEET);
    sh.hideSheet();
    sh.getRange(1, 1, 1, 4).setValues([['実行時刻', '結果', '追記件数', '備考']]).setFontWeight('bold');
  }
  sh.insertRowAfter(1);
  sh.getRange(2, 1, 1, 4).setValues([[new Date(), status, count, note]]);
  sh.getRange(2, 1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
}

function mustGetSheet_(ss, name) {
  var sh = ss.getSheetByName(name);
  if (!sh) throw new Error('シート「' + name + '」が見つかりません');
  return sh;
}

function installTrigger() {
  removeTrigger();
  ScriptApp.newTrigger('syncNewRows').timeBased().everyHours(1).create();
  SpreadsheetApp.getActive().toast('1時間ごとの自動取込を有効にしました');
}

function removeTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'syncNewRows') ScriptApp.deleteTrigger(t);
  });
}

function showStatus() {
  var ss = SpreadsheetApp.getActive();
  var work = mustGetSheet_(ss, WORK_SHEET);
  var raw  = mustGetSheet_(ss, RAW_SHEET);
  var triggers = ScriptApp.getProjectTriggers().filter(function (t) {
    return t.getHandlerFunction() === 'syncNewRows';
  });
  SpreadsheetApp.getUi().alert([
    '作業シート行数（データ行）: ' + (lastDataRow_(work) - 1),
    '取込元の候補行数: ' + Math.max(raw.getLastRow() - 1, 0),
    '自動取込: ' + (triggers.length ? '有効（1時間ごと）' : '無効')
  ].join('\n'));
}
