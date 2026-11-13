/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const readSource = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const hook = readSource('../src/shared/composables/use-fullscreen-loading.ts');
const indexSetList = readSource('../src/features/index-sets/components/index-set/list/index.vue');
const collectionStep = readSource('../src/features/collection/access/step-field.vue');
const archiveSlider = readSource('../src/features/archive/classic/archive-repository/repository-slider.vue');

test('command loading instances are native, independently owned, and released on unmount', () => {
  assert.match(hook, /LoadingPlugin/);
  assert.match(hook, /new Set<OwnedLoadingInstance>/);
  assert.match(hook, /onBeforeUnmount\(\(\) =>/);
  assert.match(hook, /loadingInstance\.hide\(\)/);
  assert.match(hook, /renderLoadingSkeleton\(\)/);
  assert.match(hook, /options\.opacity \?\? 0\.9/);
  assert.match(hook, /background-color', 'transparent'/);
  assert.match(hook, /queueMicrotask\(normalizeOverlay\)/);

  for (const source of [indexSetList, collectionStep, archiveSlider]) {
    assert.match(source, /useFullscreenLoading/);
    assert.match(source, /showFullscreenLoading/);
    assert.doesNotMatch(source, /\$bkLoading/);
  }

  assert.match(indexSetList, /confirmFn: async \(\) =>/);
  assert.match(indexSetList, /showFullscreenLoading\(\{ opacity: 0\.6 \}\)/);
  assert.match(indexSetList, /finally \{\s*loading\.hide\(\)/);
  assert.match(collectionStep, /finally \{\s*loading\.hide\(\)/);
  assert.match(archiveSlider, /finally \{\s*loading\.hide\(\)/);
});
