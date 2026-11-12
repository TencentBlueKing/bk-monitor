/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const source = readFileSync(
  new URL(
    '../src/features/collection/current/components/create-operation/step2-custom-report.tsx',
    import.meta.url,
  ),
  'utf8',
);
const style = readFileSync(
  new URL(
    '../src/features/collection/current/components/create-operation/step2-custom-report.scss',
    import.meta.url,
  ),
  'utf8',
);

test('custom report collection step uses native TDesign loading and always releases initialization state', () => {
  assert.match(source, /Loading as TLoading/);
  assert.match(source, /data-testid='collection-custom-report-loading'/);
  assert.match(source, /loading=\{loading\.value\}/);
  assert.match(source, /showOverlay/);
  assert.match(source, /zIndex=\{1000\}/);
  assert.match(source, /@\/shared\/ui\/loading\/native/);
  assert.doesNotMatch(source, /v-bkloading/);

  assert.match(source, /try \{/);
  assert.match(source, /finally \{\s*loading\.value = false;\s*isInitializing\.value = false;/);
  assert.match(style, /\.operation-step2-custom-report-loading/);
  assert.match(style, /background-color: rgba\(255, 255, 255, 0\.9\)/);
});
