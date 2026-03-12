/**
 * Aaron Wolf — 30/60/90 Day Onboarding Dashboard
 * Google Apps Script Web App — with Google Sheets persistence
 *
 * SETUP:
 * 1. Create a new Google Sheet in your desired Drive folder
 * 2. Copy the Sheet ID from the URL (the long string between /d/ and /edit)
 * 3. Paste it into SPREADSHEET_ID below
 * 4. Deploy: Extensions > Apps Script > Deploy > New deployment > Web app
 *    - Execute as: Me
 *    - Who has access: Anyone (or your org)
 *
 * The script auto-creates two sheets on first run:
 *   "TaskState"  — one row per task with status
 *   "Notes"      — one row per task with note text
 */

// ══════════════════════════════════════════════════════════════════════
// CONFIG — paste your Google Sheet ID here
// ══════════════════════════════════════════════════════════════════════
var SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID_HERE';

// ══════════════════════════════════════════════════════════════════════
// WEB APP ENTRY POINT
// ══════════════════════════════════════════════════════════════════════
function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Aaron Wolf — 30/60/90 Day Onboarding Dashboard')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0');
}

// ══════════════════════════════════════════════════════════════════════
// SHEETS HELPERS
// ══════════════════════════════════════════════════════════════════════
function getOrCreateSheet_(name, headers) {
  var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  }
  return sheet;
}

// ══════════════════════════════════════════════════════════════════════
// LOAD STATE — called from client via google.script.run
// Returns: { statuses: { "1": "done", ... }, focusId: 3, notes: { "1": "text", ... } }
// ══════════════════════════════════════════════════════════════════════
function loadState() {
  var result = { statuses: {}, focusId: null, notes: {} };

  try {
    // ── Task statuses ──
    var stateSheet = getOrCreateSheet_('TaskState', ['taskId', 'status', 'lastUpdated']);
    var stateData = stateSheet.getDataRange().getValues();
    for (var i = 1; i < stateData.length; i++) {
      var taskId = String(stateData[i][0]);
      var status = stateData[i][1];
      if (taskId && status) {
        result.statuses[taskId] = status;
      }
    }

    // ── Notes ──
    var notesSheet = getOrCreateSheet_('Notes', ['taskId', 'note', 'lastUpdated']);
    var notesData = notesSheet.getDataRange().getValues();
    for (var j = 1; j < notesData.length; j++) {
      var nTaskId = String(notesData[j][0]);
      var note = notesData[j][1];
      if (nTaskId && note) {
        result.notes[nTaskId] = note;
      }
    }

    // ── Focus ID ──
    var metaSheet = getOrCreateSheet_('Meta', ['key', 'value', 'lastUpdated']);
    var metaData = metaSheet.getDataRange().getValues();
    for (var k = 1; k < metaData.length; k++) {
      if (metaData[k][0] === 'focusId') {
        result.focusId = metaData[k][1] ? Number(metaData[k][1]) : null;
      }
    }
  } catch (e) {
    Logger.log('loadState error: ' + e.message);
  }

  return result;
}

// ══════════════════════════════════════════════════════════════════════
// SAVE STATE — called from client via google.script.run
// Accepts: { statuses: { "1": "done", ... }, focusId: 3, notes: { "1": "text", ... } }
// ══════════════════════════════════════════════════════════════════════
function saveState(data) {
  try {
    var now = new Date().toISOString();

    // ── Task statuses ──
    var stateSheet = getOrCreateSheet_('TaskState', ['taskId', 'status', 'lastUpdated']);
    var rows = [['taskId', 'status', 'lastUpdated']];
    var statuses = data.statuses || {};
    for (var id in statuses) {
      if (statuses.hasOwnProperty(id)) {
        rows.push([id, statuses[id], now]);
      }
    }
    stateSheet.clearContents();
    if (rows.length > 0) {
      stateSheet.getRange(1, 1, rows.length, 3).setValues(rows);
      stateSheet.getRange(1, 1, 1, 3).setFontWeight('bold');
    }

    // ── Notes ──
    var notesSheet = getOrCreateSheet_('Notes', ['taskId', 'note', 'lastUpdated']);
    var noteRows = [['taskId', 'note', 'lastUpdated']];
    var notes = data.notes || {};
    for (var nId in notes) {
      if (notes.hasOwnProperty(nId) && notes[nId]) {
        noteRows.push([nId, notes[nId], now]);
      }
    }
    notesSheet.clearContents();
    if (noteRows.length > 0) {
      notesSheet.getRange(1, 1, noteRows.length, 3).setValues(noteRows);
      notesSheet.getRange(1, 1, 1, 3).setFontWeight('bold');
    }

    // ── Focus ID ──
    var metaSheet = getOrCreateSheet_('Meta', ['key', 'value', 'lastUpdated']);
    metaSheet.clearContents();
    metaSheet.getRange(1, 1, 2, 3).setValues([
      ['key', 'value', 'lastUpdated'],
      ['focusId', data.focusId || '', now]
    ]);
    metaSheet.getRange(1, 1, 1, 3).setFontWeight('bold');

    return { success: true };
  } catch (e) {
    Logger.log('saveState error: ' + e.message);
    return { success: false, error: e.message };
  }
}
