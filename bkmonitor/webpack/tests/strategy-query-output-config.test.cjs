const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(
  path.resolve(
    __dirname,
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/strategy-config-set.tsx'
  ),
  'utf8'
);

test('策略编辑和页面克隆均不透明透传 query_output_config', () => {
  assert.match(source, /query_output_config:[ \t\r\n]*queryOutputConfig/);
  assert.match(source, /this[.]queryOutputConfig[ \t]*=[ \t]*queryOutputConfig/);
  assert.match(source, /handleSetDefaultData[(][)][^]*?this[.]queryOutputConfig[ ]*=[ ]*undefined;/);
});
