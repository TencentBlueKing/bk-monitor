/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';

const source = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8');

function loadTab(isPlatformIndex) {
  const item = {
    index_set_id: '900101',
    scenario_id: 'log',
    collector_config_id: 7,
    support_doris: true,
    is_platform_index: isPlatformIndex,
  };
  const component = loadScriptSetup(
    new URL('../src/features/retrieval/workbench/search-result-tab/index.vue', import.meta.url),
    {
      useApplicationStore: () => ({
        indexItem: { ids: ['900101'] },
        bkBizId: '900001',
        isUnionSearch: false,
        isSceneMode: false,
        retrieveParams: { keyword: '' },
        requestAddition: [],
      }),
      useRetrieveStore: () => ({ $state: { flatIndexSetList: [item], indexSetList: [item] } }),
      useRoute: () => ({ query: {} }),
      useLocale: () => ({ $t: text => text }),
      getFeatureToggleStatus: () => 'on',
      isFeatureToggleOn: () => true,
    },
  );
  return component.setup({ value: 'origin' }, { expose: () => {}, emit: () => {} });
}

test('platform index sets hide the clustering tab while normal index sets keep it', t => {
  const previousWindow = globalThis.window;
  globalThis.window = { IS_EXTERNAL: false };
  t.after(() => {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  });

  const platform = loadTab(true);
  assert.equal(platform.isPlatformIndex.value, true);
  assert.equal(platform.isClusteringEnable.value, false);
  assert.ok(!platform.renderPanelList.value.some(item => item.name === 'clustering'));

  const normal = loadTab(false);
  assert.equal(normal.isPlatformIndex.value, false);
  assert.equal(normal.isClusteringEnable.value, true);
  assert.ok(normal.renderPanelList.value.some(item => item.name === 'clustering'));
});

test('more setting blocks the clustering entry for platform index sets', () => {
  const previousWindow = globalThis.window;
  globalThis.window = { IS_EXTERNAL: false };
  try {
    for (const [isPlatformIndex, expectedEmits] of [
      [true, 0],
      [false, 1],
    ]) {
      const emits = [];
      const state = {
        isExternal: false,
        spaceUid: 'fixture-space',
        indexId: '900101',
        retrieve: {
          flatIndexSetList: [
            {
              index_set_id: '900101',
              scenario_id: 'log',
              collector_scenario_id: 'container',
              is_platform_index: isPlatformIndex,
            },
          ],
        },
        indexSetFieldConfig: { clustering_config: { is_active: true } },
        storeIsShowClusterStep: false,
        bkBizId: '900001',
      };
      const component = loadScriptSetup(
        new URL('../src/features/retrieval/workbench/sub-bar/more-setting.vue', import.meta.url),
        {
          useRetrieveStore: () => ({ $state: state.retrieve }),
          useStore: () => ({ state, getters: { isUnionSearch: false, isShowMaskingTemplate: false } }),
          useRouter: () => ({}),
          useLocale: () => ({ $t: text => text }),
          isFeatureToggleOn: () => false,
        },
      );
      const model = component.setup({}, { expose: () => {}, emit: (...args) => emits.push(args) });
      assert.equal(model.isPlatformIndex.value, isPlatformIndex);
      model.handleMenuClick('clustering');
      assert.equal(emits.length, expectedEmits);
    }
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});

test('master V2 runtime and hidden-field changes are mirrored in the V3 sources', () => {
  const constants = source('shared/constants/index.ts');
  assert.match(constants, /'__log_signature'/);
  assert.match(constants, /'__log_cluster_publish_revision'/);

  const headNavi = source('shared/global/head-navi/index.tsx');
  assert.match(headNavi, /ESB_DISABLED/);
  assert.match(headNavi, /\/api\/v3\/open-web\/tenant\/current-user\/language\//);
  assert.match(headNavi, /BK_USER_WEB_TENANT_ID/);

  const helper = source('features/retrieval/classic/helper.ts');
  for (const name of ['ESB_DISABLED', 'BK_USER_WEB_API_URL', 'BK_USER_WEB_TENANT_ID']) {
    assert.match(helper, new RegExp(`'${name}'`));
  }
  assert.match(helper, /replace\(\/<\/g, '\\\\u003c'\)/);

  const types = source('shared/types/index.d.ts');
  for (const name of ['ESB_DISABLED', 'BK_USER_WEB_API_URL', 'BK_USER_WEB_TENANT_ID', 'BKBASE_V4_URL']) {
    assert.match(types, new RegExp(name));
  }

  const retrieve = source('features/retrieval/services/retrieve.ts');
  assert.match(retrieve, /is_platform_index\?: boolean/);

  const container = source('features/retrieval/workspace/search-result/index.tsx');
  assert.match(container, /isPlatformIndex/);
  assert.match(container, /resolvedTab/);

  const template = readFileSync(new URL('../tools/runtime-environment.html', import.meta.url), 'utf8');
  assert.match(template, /window\.BKBASE_V4_URL = '\$\{BKBASE_V4_URL\}'/);
  assert.match(template, /% if context\.get\("ESB_DISABLED"\):/);
  assert.match(template, /window\.ESB_DISABLED = true/);
});
