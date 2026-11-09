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



export interface CollectionState {
  curCollect: Record<string, unknown>;
  curIndexSet: Record<string, unknown>;
  scenarioMap: Record<string, unknown> | null;
  exportCollectObj: {
    collectID: string | number | null;
    syncType: string[];
    collect: Record<string, unknown>;
  };
}

const state: CollectionState = {
    curCollect: {},
    curIndexSet: {},
    scenarioMap: null,
    exportCollectObj: {
      collectID: null,
      syncType: [],
      collect: {},
    },
  };

export default {
  namespaced: true,
  state,
  getters: {
    curCollect: (state: CollectionState) => state.curCollect,
    exportCollectObj: (state: CollectionState) => state.exportCollectObj,
  },
  mutations: {
    setCurCollect(state: CollectionState, collect: CollectionState['curCollect']) {
      (state)['curCollect'] = collect;
    },
    updateCurCollect(state: CollectionState, collect: CollectionState['curCollect']) {
      for (const key in collect) {
        if (Object.prototype.hasOwnProperty.call(state.curCollect, key)) {
          state.curCollect[key] = collect[key];
        } else {
          (state.curCollect)[key] = collect[key];
        }
      }
    },
    updateCurIndexSet(state: CollectionState, payload: CollectionState['curIndexSet']) {
      state.curIndexSet = payload;
    },
    updateScenarioMap(state: CollectionState, payload: CollectionState['scenarioMap']) {
      state.scenarioMap = payload;
    },
    updateExportCollectObj(state: CollectionState, payload: CollectionState['exportCollectObj']) {
      state.exportCollectObj = payload;
    },
  },
  actions: {},
};
