/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const source = path => new URL('../src/' + path, import.meta.url);

const createHelper = () => loadTypeScript(source('shared/global/ai-assitant/ai-assitant-helper.ts'), {
  vue: Vue, './ai-request': { requestAIResult: async () => ({}) },
}).default;

test('AI first interaction waits for the lazy instance and retains position and action arguments', async () => {
  const helper = createHelper(), calls = [];
  let ready, loads = 0;
  const pending = new Promise(resolve => { ready = resolve; });
  helper.setAiAssitantLoader(async () => { loads++; await pending; helper.getAiAssitantInstance().value = {
    setPosition: (...args) => calls.push(['position', ...args]),
    updateOptions: async (...args) => calls.push(['options', ...args]),
    open: (...args) => calls.push(['open', ...args]),
  }; });
  helper.setPosition(1, 2, 300, 400);
  assert.equal(loads, 0);
  const args = { type: 'synthetic' };
  const action = helper.openAiAssitant(true, args);
  assert.equal(loads, 1);
  assert.deepEqual(calls, []);
  ready();
  await action;
  assert.deepEqual(calls, [['options', {}, 'log_analysis'], ['position', 1, 2, 300, 400], ['open', true, args]]);
  assert.equal(helper.activePosition, 'row-box');
});

test('AI lazy loading failures can retry and old page cleanup cannot clear a newer page loader', async () => {
  const helper = createHelper();
  const dispose = helper.setAiAssitantLoader(async () => { throw Error('synthetic import failure'); });
  await assert.rejects(helper.openAiAssitant(false, {}), /synthetic import failure/);
  let shown;
  helper.setAiAssitantLoader(async () => { helper.getAiAssitantInstance().value = {
    updateOptions: async () => {}, queryStringShowAiAssistant: value => { shown = value; },
  }; });
  dispose();
  await helper.showAiAssitant({}, { description: 'synthetic' });
  assert.deepEqual(shown, { description: 'synthetic' });
});

test('the focused trend renderer retains stacked bars, line, scroll legends, markers and zoom actions', async () => {
  const { buildSync } = await import('esbuild');
  const { mkdtempSync, rmSync, writeFileSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join, resolve } = await import('node:path');
  const { createRequire } = await import('node:module');
  const dir = mkdtempSync(join(tmpdir(), 'bklog-trend-render-'));
  try {
    const compiled = buildSync({ stdin: {
      contents: `export { init } from './src/shared/composables/trend-echarts.ts'; export { setCanvasCreator } from 'echarts/core';`,
      resolveDir: resolve(new URL('..', import.meta.url).pathname), loader: 'ts',
    }, bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent', define: { navigator: 'undefined' } });
    const file = join(dir, 'renderer.cjs');
    writeFileSync(file, compiled.outputFiles[0].contents);
    const { init, setCanvasCreator } = createRequire(import.meta.url)(file);
    const context = new Proxy({ measureText: text => ({ width: String(text).length * 8 }) }, { get: (target, key) => key in target ? target[key] : () => {} });
    const canvas = { width: 800, height: 240, style: {}, addEventListener() {}, removeEventListener() {}, getContext: () => context };
    setCanvasCreator(() => canvas);
    const chart = init(canvas, null, { renderer: 'canvas', width: 800, height: 240 });
    try {
      chart.setOption({ animation: false,
        title: { text: 'Synthetic trend' }, grid: {}, tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', data: ['Synthetic A', 'Synthetic B'] },
        toolbox: { feature: { dataZoom: {}, restore: {}, saveAsImage: {} } },
        xAxis: { type: 'category', data: ['A', 'B', 'C'] }, yAxis: { type: 'value' },
        dataZoom: [{ type: 'inside' }],
        series: [{ name: 'Synthetic A', type: 'bar', stack: 'total', data: [1, 2, 3],
          markLine: { data: [{ yAxis: 2 }] }, markArea: { data: [[{ xAxis: 'A' }, { xAxis: 'B' }]] } },
        { name: 'Synthetic B', type: 'line', data: [3, 2, 1] }],
      });
      assert.equal(chart.getOption().title[0].text, 'Synthetic trend');
      assert.equal(chart.getOption().legend[0].type, 'scroll');
      assert.deepEqual(chart.getOption().series.map(series => series.type), ['bar', 'line']);
      chart.dispatchAction({ type: 'dataZoom', start: 0, end: 50 });
      assert.equal(chart.getOption().dataZoom[0].end, 50);
      chart.dispatchAction({ type: 'restore' });
      assert.equal(chart.getOption().dataZoom[0].end, 100);
    } finally { chart.dispose(); }
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test('bundle measurements include static shared dependencies once and exclude deferred interactions', async () => {
  const { summarizeChunks } = await import('../tools/analyze-bundle.mjs');
  const chunks = [
    { file: 'entry', bytes: 10, gzip: 5, imports: ['shared'], dynamicImports: ['ai'] },
    { file: 'retrieve', bytes: 20, gzip: 8, imports: ['shared', 'trend'] },
    { file: 'shared', bytes: 30, gzip: 10, imports: ['entry'] },
    { file: 'trend', bytes: 40, gzip: 15, imports: [] },
    { file: 'ai', bytes: 1000, gzip: 100, imports: [] },
  ];
  assert.deepEqual(summarizeChunks(chunks, ['entry', 'retrieve']), {
    files: ['entry', 'retrieve', 'shared', 'trend'], bytes: 100, gzip: 38,
  });
});
