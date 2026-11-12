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

import { defineStore, type Pinia } from 'pinia';
import { resolveApplicationPinia } from '../pinia';
import type { CollectionState } from '../collect';

export const createCollectionState = (): CollectionState => ({
  curCollect: {},
  curIndexSet: {},
  scenarioMap: null,
  exportCollectObj: { collectID: null, syncType: [], collect: {} },
});
const defineCollectionStore = defineStore('bklog.collect', {
  state: createCollectionState,
  actions: {
    setCurCollect(collect: CollectionState['curCollect']) {
      this.curCollect = collect;
    },
    updateCurCollect(collect: CollectionState['curCollect']) {
      for (const key in collect) this.curCollect[key] = collect[key];
    },
    updateCurIndexSet(payload: CollectionState['curIndexSet']) {
      this.curIndexSet = payload;
    },
    updateScenarioMap(payload: CollectionState['scenarioMap']) {
      this.scenarioMap = payload;
    },
    updateExportCollectObj(payload: CollectionState['exportCollectObj']) {
      this.exportCollectObj = payload;
    },
  },
});
/** Explicit instance keeps non-component callers on the same application state. */
export const useCollectionStore = (pinia?: Pinia) => defineCollectionStore(resolveApplicationPinia(pinia));

/** Temporary published envelope: all reads/writes still reach this single native store. */
