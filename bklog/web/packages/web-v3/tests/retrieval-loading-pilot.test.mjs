/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(
  new URL('../src/features/retrieval/workspace/search-result/log-clustering/log-table/index.tsx', import.meta.url),
  'utf8',
);
const style = readFileSync(
  new URL('../src/features/retrieval/workspace/search-result/log-clustering/log-table/index.scss', import.meta.url),
  'utf8',
);
const skeleton = readFileSync(new URL('../src/app/skeleton/clustering-loader.vue', import.meta.url), 'utf8');

test('cluster table uses native TDesign loading without changing request ownership', () => {
  assert.match(source, /Loading as TLoading/);
  assert.match(source, /loading=\{tableLoading\.value\}/);
  assert.match(source, /showOverlay/);
  assert.match(source, /zIndex=\{0\}/);
  assert.match(source, /data-testid='cluster-table-loading'/);
  assert.match(source, /@\/shared\/ui\/loading\/native/);
  assert.doesNotMatch(source, /v-bkloading/);

  assert.match(source, /const seq = refreshSeq/);
  assert.match(source, /seq !== refreshSeq \|\| isUnmounted/);
  assert.match(source, /\.finally\(\(\) =>/);
  assert.match(style, /\.cluster-table-loading/);
  assert.match(style, /min-height: 0/);
  assert.match(style, /background-color: transparent/);
  assert.match(source, /indicator=\{false\}/);

  assert.doesNotMatch(skeleton, /<bk-table/);
  assert.match(skeleton, /class="skeleton-table__row"/);
  assert.match(skeleton, /height: 43px/);
});
