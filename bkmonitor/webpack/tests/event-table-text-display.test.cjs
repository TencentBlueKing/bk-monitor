const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

test('事件指标名提示使用换行纯文本', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/fta-solutions/pages/event/event-table.tsx'),
    'utf8'
  );

  assert.match(source, /handleMetricMouseenter\(e:\s*MouseEvent,\s*data:\s*IEventItem\['metric_display'\]\)/);
  assert.match(source, /content:\s*data\.map\(item => item\.name \|\| item\.id\)\.join\('\\n'\)/);
  assert.match(source, /this\.popoverInstance = this\.\$bkPopover\(e\.target,\s*\{[^}]*allowHTML:\s*false[^}]*\}\)/s);
  assert.match(source, /content:\s*data\.map\(item => item\.name \|\| item\.id\)\.join\('\\n'\)[\s\S]{0,80}allowHTML:\s*false/);
  assert.doesNotMatch(source, /content:\s*`<div>\$\{item\.name \|\| item\.id\}<\/div>`/);
  assert.doesNotMatch(source, /<div class="dimension-desc">/);
  assert.match(source, /join\('\\n'\)/);
});

test('事故名称与标签提示使用纯文本', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/fta-solutions/pages/event/incident-table.tsx'),
    'utf8'
  );

  assert.match(source, /id:\s*'incident_name'/);
  assert.match(source, /showOverflowTooltip:\s*true/);
  assert.match(
    source,
    /content:\s*data\s*\.map\(item => \(typeof item === 'string' \? item : `\$\{item\.key\}：\$\{item\.value\}`\)\)\s*\.join\('\\n'\)/
  );
  assert.match(source, /this\.popoperInstance = this\.\$bkPopover\(e\.target,\s*\{[^}]*allowHTML:\s*false[^}]*\}\)/s);
  assert.doesNotMatch(source, /<div class="dimension-desc">/);
});

test('动作详情提示使用纯文本并保留多行内容', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/fta-solutions/pages/event/event-detail/action-detail.tsx'),
    'utf8'
  );

  assert.match(source, /this\.popoverInstance = this\.\$bkPopover\(e\.target,\s*\{[^}]*allowHTML:\s*false[^}]*\}\)/s);
  assert.match(source, /arr\?\.filter\(Boolean\)\.join\('\\n'\)|filter\(Boolean\)[\s\S]*join\('\\n'\)/);
  assert.doesNotMatch(source, /<div>\$\{item\}<\/div>/);
});
