# Google Forms feedback setup

Paste the code below at the bottom of the existing Apps Script `Code.gs`.
Then run `createFeedbackForm`, copy the form URL from the execution log, and run
`installFormSubmitTrigger` once.

```javascript
function createFeedbackForm() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const form = FormApp.create('イベント評価フォーム');

  form.setDescription('LINEで届いたイベント番号を選んで、行きたい/行くを記録します。');
  form.addListItem()
    .setTitle('イベント番号')
    .setRequired(true)
    .setChoiceValues(Array.from({ length: 20 }, function(_, i) { return String(i + 1); }));

  form.addMultipleChoiceItem()
    .setTitle('反応')
    .setRequired(true)
    .setChoiceValues(['行きたい', '行く']);

  form.addTextItem()
    .setTitle('メモ')
    .setRequired(false);

  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  Logger.log('FORM_URL=' + form.getPublishedUrl());
}

function installFormSubmitTrigger() {
  ScriptApp.newTrigger('handleFormSubmit')
    .forSpreadsheet(SpreadsheetApp.getActiveSpreadsheet())
    .onFormSubmit()
    .create();
}

function handleFormSubmit(e) {
  const named = e.namedValues || {};
  const eventNumber = Number(firstValue(named['イベント番号']));
  const actionLabel = firstValue(named['反応']);
  const memo = firstValue(named['メモ']);

  if (!eventNumber || !actionLabel) return;

  const selected = loadSelectedEventsFromSheet();
  const event = selected[eventNumber - 1] || {};
  const action = actionLabel === '行く' ? 'go' : 'want';

  const headers = [
    'created_at',
    'user_id',
    'reply_text',
    'event_number',
    'action',
    'action_label',
    'event_id',
    'event_name',
    'prefecture',
    'venue',
    'url'
  ];

  const sheet = getOrCreateSheet(SHEET_FEEDBACK, headers);
  sheet.appendRow([
    new Date(),
    'google_form',
    eventNumber + ' ' + actionLabel + (memo ? ' / ' + memo : ''),
    eventNumber,
    action,
    actionLabel,
    event.event_id || '',
    event.event_name || '',
    event.prefecture || '',
    event.venue || '',
    event.url || ''
  ]);
}

function loadSelectedEventsFromSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_SELECTED);
  if (!sheet || sheet.getLastRow() < 2) return [];

  const values = sheet.getDataRange().getValues();
  const headers = values[0].map(String);

  return values.slice(1).map(function(row) {
    const item = {};
    headers.forEach(function(header, index) {
      item[header] = row[index];
    });
    return item;
  });
}

function firstValue(value) {
  if (Array.isArray(value)) return value[0] || '';
  return value || '';
}
```

After the form URL is created, add it to GitHub Actions secrets as:

```text
FEEDBACK_FORM_URL
```
