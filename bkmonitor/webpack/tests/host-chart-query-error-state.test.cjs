const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

global.innerHeight = 1000;
global.window = { i18n: { t: value => value } };

const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const toValue = value => {
  if (typeof value === 'function') return value();
  return value && typeof value === 'object' && 'value' in value ? value.value : value;
};

const vueStub = {
  computed: getter => ({
    get value() {
      return getter();
    },
  }),
  inject: (_key, defaultValue) => defaultValue,
  onBeforeUnmount: () => {},
  onMounted: () => {},
  shallowRef: value => ({ value }),
  toValue,
  watch: () => {},
};

const createEchartsContext = ({ query, targetCount = 1 }) => {
  const originalLoad = Module._load;

  Module._load = function loadWithEchartsStubs(request, parent, isMain) {
    if (request === 'vue') return vueStub;
    if (request === 'dayjs') return {};
    if (request === 'monitor-api/cancel') {
      return {
        CancelToken: class CancelToken {
          constructor(register) {
            register(() => {});
          }
        },
      };
    }
    if (request === 'monitor-common/utils') return { random: () => 'chart-id' };
    if (request === 'monitor-common/utils/equal') return { arraysEqual: () => false };
    if (request === 'monitor-ui/chart-plugins/constants/charts') return { COLOR_LIST_BAR: [] };
    if (request === 'monitor-ui/monitor-echarts/valueFormats/valueFormats') {
      return { getValueFormat: () => ({ func: value => value }) };
    }
    if (request === '../../../../components/time-range/utils') {
      return { DEFAULT_TIME_RANGE: [100, 200], handleTransformToTimestamp: value => value };
    }
    if (request === './use-chart-tooltips') {
      return { useChartTooltips: () => ({ tooltipsOptions: { value: {} } }) };
    }
    if (request === './use-chart-view-option') {
      return { useChartViewOption: () => ({ applyPeakMarkPoint: () => {}, watchHighlightPeak: () => {} }) };
    }
    if (request === './utils') {
      return {
        handleGetMinPrecision: () => 0,
        handleSetMarkPoints: () => ({}),
        handleSetMarkTimeRange: () => ({}),
        handleSetThresholdArea: () => undefined,
        handleSetThresholdLine: () => ({}),
        mergeOverlappingArrays: () => null,
        processLineSymbols: value => value,
      };
    }
    if (request === '@/pages/host/components/dashbords/variables/resolve') {
      return { resolveVariables: value => value };
    }
    return originalLoad(request, parent, isMain);
  };

  try {
    const modulePath = require.resolve('../src/trace/pages/trace-explore/components/explore-chart/use-echarts.ts');
    delete require.cache[modulePath];
    const { useEcharts } = require(modulePath);
    return useEcharts({
      $api: { metric: { query } },
      chartRef: { value: null },
      customOptions: {},
      panel: {
        options: { time_series: {} },
        targets: Array.from({ length: targetCount }, (_, index) => ({
          apiFunc: 'query',
          apiModule: 'metric',
          data: { index },
        })),
      },
      params: {},
    });
  } finally {
    Module._load = originalLoad;
  }
};

const emptyResponse = { metrics: [], series: [] };

test('主机单图唯一查询失败时必须保留错误态', async () => {
  const context = createEchartsContext({ query: () => Promise.reject(new Error('query failed')) });

  await context.getEchartOptions();

  assert.equal(context.loadError.value, true);
  assert.equal(context.options.value, undefined);
});

test('主机单图查询成功但无序列时仍是正常空数据', async () => {
  const context = createEchartsContext({ query: () => Promise.resolve(emptyResponse) });

  await context.getEchartOptions();

  assert.equal(context.loadError.value, false);
});

test('多目标查询部分成功时保留可用结果而非整图报错', async () => {
  const responses = [Promise.reject(new Error('one target failed')), Promise.resolve(emptyResponse)];
  const context = createEchartsContext({ query: () => responses.shift(), targetCount: 2 });

  await context.getEchartOptions();

  assert.equal(context.loadError.value, false);
});

test('旧图表查询失败不得覆盖后发成功状态', async () => {
  const firstRequest = deferred();
  const secondRequest = deferred();
  const requests = [firstRequest, secondRequest];
  const context = createEchartsContext({ query: () => requests.shift().promise });
  const firstLoad = context.getEchartOptions();
  const secondLoad = context.getEchartOptions();

  secondRequest.resolve(emptyResponse);
  await secondLoad;
  firstRequest.reject(new Error('stale query failed'));
  await firstLoad;

  assert.equal(context.loadError.value, false);
});

test('主机时序卡区分查询错误、真实空数据并提供重试', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/dashbords/components/time-series-card.tsx'),
    'utf8'
  );

  assert.match(source, /const \{[\s\S]*loadError[\s\S]*getEchartOptions[\s\S]*\} = useEcharts/);
  assert.match(source, /const handleRetry = async \(\) =>/);
  assert.match(source, /this\.loadError[\s\S]*<EmptyStatus[\s\S]*type='500'/);
  assert.match(source, /<EmptyStatus[\s\S]*onOperation=\{this\.handleRetry\}/);
  assert.match(source, /time-series-card__empty[\s\S]*暂无数据/);
});
