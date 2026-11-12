/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const readSource = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const loading = readSource('../src/shared/ui/loading/index.tsx');
const style = readSource('../src/shared/ui/loading/index.scss');
const dashboard = readSource('../src/features/dashboards/old-index.vue');
const dataLinks = readSource('../src/features/data-links/manage-data-link-conf/index.vue');

test('small domains use the shared native TDesign loading component', () => {
  assert.match(loading, /Loading as TLoading/);
  assert.match(loading, /@\/shared\/ui\/loading\/native/);
  assert.match(loading, /opacity:[\s\S]*default: 0\.9/);
  assert.match(loading, /zIndex:[\s\S]*default: Z_INDEX_LAYERS\.PAGE/);
  assert.match(loading, /toOverlayColor/);
  assert.match(style, /var\(--bklog-loading-overlay-color\)/);

  assert.match(dashboard, /data-testid="dashboard-loading"/);
  assert.match(dashboard, /:loading="isLoading"/);
  assert.doesNotMatch(dashboard, /v-bkloading/);

  assert.match(dataLinks, /data-testid="data-link-table-loading"/);
  assert.match(dataLinks, /:loading="tableLoading"/);
  assert.doesNotMatch(dataLinks, /v-bkloading/);
});
