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

import { createPinia, defineStore } from 'pinia';
import { loadTypeScript } from './load-typescript.mjs';
const effects = [];
const cache = {
  setLocalStorageMirror: async (...args) => effects.push(['mirror', ...args]),
  setApiCache: async (...args) => effects.push(['cache', ...args]),
};
const createState = () => ({
  aiMode: {},
  storage: {},
  apiErrorInfo: {},
  user: {},
  indexItem: { ids: ['900101'], addition: [], chart_params: {} },
  indexId: '900101',
  visibleFields: [],
  unionIndexList: [],
  spaceUid: 'bkcc__900001',
  bkBizId: '900001',
  indexFieldInfo: { is_loading: false, display_fields: [] },
  indexSetOperatorConfig: { isShowSourceField: false },
  features: { isAiAssistantActive: false },
  favoriteList: [],
  mySpaceList: [],
  isSetDefaultTableColumn: false,
});
const operations = loadTypeScript(new URL('../../src/app/state/mutations/index.js', import.meta.url), {
  '@/shared/lib/util': {},
  '@/platform/persistence/index': { storeCacheService: cache },
  '../condition-operator.ts': {},
  '../default-values.ts': { BkLogGlobalStorageKey: 'GLOBAL' },
  '../helper.ts': {},
  '../state.ts': { createStoreState: createState },
  '../services/field-metadata.service.js': {},
  '../services/runtime-cache.service.js': {},
  '../services/space-list.service.ts': {},
});
const appQueries = loadTypeScript(new URL('../../src/app/state/actions/app-actions.js', import.meta.url), {
  '@/platform/services': {
    ServicesInstance: {
      userInfo: {
        getUserInfo: async (options) => {
          effects.push(['userRequest', options]);
          return { data: { username: 'fixture' } };
        },
      },
    },
  },
  '@/platform/persistence/index': { storeCacheService: cache },
  '@/shared/global/utils/time': {},
  '../helper.ts': {},
  '../menu-config.ts': {},
});
const useRetrieve = defineStore('fixture.retrieve', {
  state: () => ({ flatIndexSetList: [], catchFieldCustomConfig: { sortList: [] }, sceneConfigs: [] }),
  getters: { sceneConfigList: (state) => state.sceneConfigs },
  actions: {
    updateIndexSetList(items) {
      this.flatIndexSetList = items;
    },
    async requestSceneConfigs(payload, config) {
      await native.useApplicationStore(this._p).userInfo(payload, config);
      this.sceneConfigs = payload.items;
      return this.sceneConfigs;
    },
  },
});
const { useCollectionStore: useCollect } = loadTypeScript(
    new URL('../../src/app/state/domains/collection-store.ts', import.meta.url),
    { '../pinia': { resolveApplicationPinia: (p) => p } },
  ),
  useGlobals = defineStore('fixture.globals', { state: () => ({ globalsData: {} }) });
class Pool {
  cancelStore = new Map();
}
const native = loadTypeScript(new URL('../../src/app/state/domains/application-store.ts', import.meta.url), {
  '../initialize-pinyin': {},
  '../state': { createStoreState: createState },
  '../pinia': { applicationPinia: createPinia(), resolveApplicationPinia: (p) => p },
  '../request-pool': { default: new Pool(), RequestPool: Pool },
  './retrieve-store': { useRetrieveStore: useRetrieve },
  './collection-store': { useCollectionStore: useCollect },
  './globals-store': { useGlobalsStore: useGlobals },
  '@/platform/persistence/index': { storeCacheService: cache },
  '../helper.ts': {
    isSceneRetrieve: () => false,
    isSceneFilterValuesEmpty: () => true,
    isFeatureToggleOn: () => false,
  },
  '../store.type.ts': { BK_LOG_STORAGE: {} },
  '../services/retrieve-query.service.js': {
    resolveGetterVisibleFields: (state) => state.visibleFields.filter((item) => !item.hidden),
  },
  '../actions/app-actions.js': appQueries,
  '../actions/retrieve-misc-actions.js': {},
  '../actions/query-condition-actions.js': {},
  '../actions/retrieve-search-actions.js': {},
  '../mutations/index.js': operations,
});

export { native, effects, useRetrieve, useCollect, useGlobals };
