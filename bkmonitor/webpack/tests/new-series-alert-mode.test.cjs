const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(
  path.resolve(
    __dirname,
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/new-series/new-series.tsx'
  ),
  'utf8'
);

test('新维度值检测默认使用仅首次出现模式并保存编辑回填', () => {
  assert.match(source, /alertMode:\s*'once'/);
  assert.match(source, /alert_mode:\s*this\.formData\.alertMode/);
  assert.match(source, /this\.data\.config\?\.alert_mode\s*\?\?\s*'once'/);
});

test('新维度值检测以告警状态表述生命周期且不混入通知语义', () => {
  assert.match(source, /仅首次出现时告警/);
  assert.match(source, /维度持续出现时保持告警/);
  assert.match(source, /不改变通知设置/);
  assert.doesNotMatch(source, /首次告警后是否继续通知/);
});
