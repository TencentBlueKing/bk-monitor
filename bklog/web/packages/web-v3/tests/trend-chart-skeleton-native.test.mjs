import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import * as Vue from 'vue';

function fixture() {
  const source = readFileSync(new URL('../src/features/retrieval/workbench/search-result-chart/index.tsx', import.meta.url), 'utf8');
  const stateStart = source.indexOf('    const isLoading = computed');
  const stateEnd = source.indexOf('    const finishPolling', stateStart);
  const renderStart = source.indexOf('    // 渲染主入口');
  const renderEnd = source.lastIndexOf('  },');
  const renderSource = source.slice(renderStart, renderEnd).replace('return () => (', 'const renderTrend = () => (');
  const context = {
    computed: Vue.computed,
    trendStatus: Vue.ref('loading'), trendLoadingCovered: Vue.ref(false), dynamicHeight: Vue.ref(130),
    isFold: Vue.ref(false), chartContainer: Vue.ref(null), trendChartCanvas: Vue.ref(null),
    chartTitleContent: () => Vue.h('header', 'Toolbar'), t: value => value,
    ChartSkeleton: { name: 'ChartSkeleton' },
  };
  const output = ts.transpileModule(source.slice(stateStart, stateEnd) + renderSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' } }).outputText;
  const render = new Function('exports', 'require', ...Object.keys(context), output + '\nreturn renderTrend;')({}, createRequire(import.meta.url), ...Object.values(context));
  return { ...context, render };
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return;
  if (predicate(node)) return node;
  for (const child of Array.isArray(node.children) ? node.children : []) {
    const result = find(child, predicate);
    if (result) return result;
  }
}
const byClass = (root, name) => find(root, node => node.props?.class === name);

test('trend first response uses the full skeleton; progressive responses keep the canvas visible', () => {
  const f = fixture();
  const tree = f.render();
  assert.ok(byClass(tree, 'trend-chart-loading-overlay'));
  const chart = find(tree, node => node.type === f.ChartSkeleton);
  assert.equal(chart.props.type, 'bar');
  assert.equal(chart.props.length, 40);
  assert.equal(chart.props.height, 130);
  assert.ok(find(tree, node => node.ref?.r === f.trendChartCanvas));
  assert.equal(find(tree, node => node.props?.['data-testid'] === 'trend-chart-progress'), undefined);
  f.dynamicHeight.value = 240;
  assert.equal(find(f.render(), node => node.type === f.ChartSkeleton).props.height, 240);
  f.trendLoadingCovered.value = true;
  assert.equal(byClass(f.render(), 'trend-chart-loading-overlay'), undefined);
  f.trendLoadingCovered.value = false;
  f.trendStatus.value = 'polling';
  assert.equal(byClass(f.render(), 'trend-chart-loading-overlay'), undefined);
  assert.ok(find(f.render(), node => node.props?.['data-testid'] === 'trend-chart-progress'));
  assert.ok(find(f.render(), node => node.ref?.r === f.trendChartCanvas));
  f.isFold.value = true;
  assert.equal(find(f.render(), node => node.props?.['data-testid'] === 'trend-chart-progress'), undefined);
  f.isFold.value = false;
  f.trendLoadingCovered.value = true;
  assert.equal(find(f.render(), node => node.props?.['data-testid'] === 'trend-chart-progress'), undefined);
});

test('trend ready, empty and folding retain their existing branches', () => {
  const f = fixture();
  f.trendStatus.value = 'ready';
  assert.equal(byClass(f.render(), 'trend-chart-loading-overlay'), undefined);
  assert.ok(find(f.render(), node => node.ref?.r === f.trendChartCanvas));
  f.trendStatus.value = 'empty';
  assert.ok(byClass(f.render(), 'trend-chart-empty'));
  assert.equal(byClass(f.render(), 'trend-chart-loading-overlay'), undefined);
  f.isFold.value = true;
  assert.equal(byClass(f.render(), 'echart-wrapper').props['v-show'], false);
});
