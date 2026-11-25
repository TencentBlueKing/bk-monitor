/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { resolveSceneEmptyView } from '../src/features/retrieval/workspace/scene-empty-view.ts';

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

test('scene results show the matching empty state only after the field request settles', () => {
  const initial = {
    isSceneMode: true,
    isSceneFilterEmpty: false,
    isFieldListFetched: false,
    isFieldListEmpty: false,
    hasFieldRequestError: false,
    isSceneLoading: true,
  };
  const loading = {
    showSceneEmptyTip: false,
    showFieldEmptyTip: false,
    showFieldErrorTip: false,
    hideSearchResult: true,
    showResultSkeleton: true,
  };
  assert.deepEqual(resolveSceneEmptyView(initial), loading);
  const refreshingEmpty = { ...initial, isFieldListFetched: true, isFieldListEmpty: true };
  assert.deepEqual(resolveSceneEmptyView(refreshingEmpty), loading);
  assert.deepEqual(resolveSceneEmptyView({ ...refreshingEmpty, isSceneLoading: false }), {
    ...loading,
    showFieldEmptyTip: true,
    showResultSkeleton: false,
  });
  const failed = { ...refreshingEmpty, hasFieldRequestError: true };
  assert.deepEqual(resolveSceneEmptyView(failed), loading);
  assert.deepEqual(resolveSceneEmptyView({ ...failed, isSceneLoading: false }), {
    ...loading,
    showFieldErrorTip: true,
    showResultSkeleton: false,
  });
  assert.deepEqual(resolveSceneEmptyView({ ...initial, isSceneFilterEmpty: true }), {
    ...loading,
    showSceneEmptyTip: true,
    showResultSkeleton: false,
  });
  for (const input of [{ ...initial, isSceneMode: false }, { ...initial, isFieldListFetched: true }]) {
    assert.deepEqual(resolveSceneEmptyView(input), {
      ...loading,
      hideSearchResult: false,
      showResultSkeleton: false,
    });
  }
});
