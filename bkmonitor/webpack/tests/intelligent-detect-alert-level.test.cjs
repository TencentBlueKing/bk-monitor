const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/monitor-pc/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const {
  createAiAlertLevelValue,
  getConfiguredAlertLevels,
  hydrateAiLevelSelectValue,
  isAutoAlertLevelRule,
  serializeAiLevelSelectValue,
  serializeAiAlertLevelValue,
  switchAiAlertLevelMode,
} = require('../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/alert-level.ts');
const {
  FormItem,
  syncAiLevelAutoEnabled,
} = require('../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/form/utils.ts');

const intelligentDetectSource = fs.readFileSync(
  path.resolve(
    __dirname,
    '../src/monitor-pc/pages/strategy-config/strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect.tsx'
  ),
  'utf8'
);

test('SDK 新建单指标异常检测默认使用自动级别并全选输出范围', () => {
  assert.deepEqual(createAiAlertLevelValue(undefined, true), {
    mode: 'auto',
    level: 2,
    alertLevels: [1, 2, 3],
  });
});

test('非 SDK 新建和既有手动策略保持手动级别', () => {
  assert.deepEqual(createAiAlertLevelValue(undefined, false), {
    mode: 'manual',
    level: 1,
    alertLevels: [],
  });
  assert.deepEqual(createAiAlertLevelValue({ level: 3, config: {} }, true), {
    mode: 'manual',
    level: 3,
    alertLevels: [],
  });
});

test('自动级别配置回填输出范围并固定技术级别为预警', () => {
  const value = createAiAlertLevelValue({ level: 2, config: { alert_level_mode: 'auto', alert_levels: [3, 1] } }, true);

  assert.deepEqual(value, { mode: 'auto', level: 2, alertLevels: [1, 3] });
  assert.deepEqual(serializeAiAlertLevelValue(value), {
    level: 2,
    config: { alert_level_mode: 'auto', alert_levels: [1, 3] },
  });
});

test('自动与手动模式切换采用确认的默认值', () => {
  const manual = switchAiAlertLevelMode({ mode: 'auto', level: 2, alertLevels: [2, 3] }, 'manual');
  assert.deepEqual(manual, { mode: 'manual', level: 1, alertLevels: [] });
  assert.deepEqual(switchAiAlertLevelMode(manual, 'auto'), {
    mode: 'auto',
    level: 2,
    alertLevels: [1, 2, 3],
  });
});

test('下游告警处理使用自动输出范围而不是技术级别', () => {
  const rule = {
    type: 'IntelligentDetect',
    level: 2,
    config: { alert_level_mode: 'auto', alert_levels: [1, 3] },
  };

  assert.equal(isAutoAlertLevelRule(rule), true);
  assert.deepEqual(getConfiguredAlertLevels(rule), [1, 3]);
  assert.deepEqual(getConfiguredAlertLevels({ level: 2, config: { alert_level_mode: 'manual' } }), [2]);
});

test('复用级别组件兼容既有算法的数字和数组模型', () => {
  assert.deepEqual(hydrateAiLevelSelectValue(3), {
    mode: 'manual',
    level: 3,
    alertLevels: [],
  });
  assert.deepEqual(hydrateAiLevelSelectValue([3, 1]), {
    mode: 'auto',
    level: 2,
    alertLevels: [1, 3],
  });
  assert.equal(serializeAiLevelSelectValue({ mode: 'manual', level: 3, alertLevels: [] }, false), 3);
  assert.deepEqual(serializeAiLevelSelectValue({ mode: 'auto', level: 2, alertLevels: [1, 3] }, false), [1, 3]);
});

test('算法组合变化时实时同步自动等级可用性', () => {
  const levelItem = new FormItem({
    autoEnabled: true,
    field: 'level',
    label: '告警级别',
    type: 'ai-level',
    value: { mode: 'manual', level: 2, alertLevels: [] },
  });
  const modelItem = new FormItem({ field: 'model', label: '模型', type: 'model-select', value: '' });

  syncAiLevelAutoEnabled([levelItem, modelItem], false);

  assert.equal(levelItem.autoEnabled, false);
  assert.equal(modelItem.autoEnabled, false);
});

test('智能异常检测组件监听自动等级可用性属性', () => {
  assert.match(intelligentDetectSource, /@Watch\('autoLevelEnabled'/);
  assert.match(intelligentDetectSource, /syncAiLevelAutoEnabled\(this\.staticFormItem, autoLevelEnabled\)/);
});
