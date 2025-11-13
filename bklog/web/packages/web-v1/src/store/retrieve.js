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

import { random } from '@/components/monitor-echarts/utils';

import http from '@/api';

/**
 * 索引集列表初始化
 * @param {*} indexSetList 索引集列表
 * @param {*} pid 父节点id
 */
const resolveIndexItemAttr = (indexSetList = [], parent_node = null) => {
  const s1 = [];
  const s2 = [];
  indexSetList?.forEach(item => {
    const copyItem = structuredClone(item);
    Object.assign(copyItem, {
      index_set_id: `${item.index_set_id}`,
      indexName: item.index_set_name,
      lightenName: ` (${item.indices.map(item => item.result_table_id).join(';')})`,
      unique_id: `${parent_node?.index_set_id ?? '#'}_${item.index_set_id}`,
      is_child_node: parent_node !== null,
      parent_node,
    });

    // 这里只有两层，数据结构固定为 parent_id#child_id
    // 如果是跟节点 数据结构为 #_child_id
    copyItem.children = resolveIndexItemAttr(item.children ?? [], copyItem);

    if (copyItem.auth_wieght === 1) {
      s1.push(copyItem);
    } else {
      s2.push(copyItem);
    }
  });

  return s1.concat(s2);
};

export default {
  namespaced: true,
  state: {
    chartKey: random(10), // 复用监控的图表，改变key重新请求图表
    cacheDatePickerValue: [],
    cacheTimeRange: '',
    filedSettingConfigID: 1,
    indexSetList: [],
    flatIndexSetList: [],
    isIndexSetLoading: false,
    isTrendDataLoading: false,
    trendDataCount: 0,
    catchFieldCustomConfig: {
      fieldsWidth: {},
      displayFields: [],
      filterSetting: [],
      filterAddition: [],
      fixedFilterAddition: false,
      sortList: [],
    },
    activeVersion: 'v2',
  },
  mutations: {
    updateActiveVersion(state, version) {
      state.activeVersion = version ?? 'v2';
    },
    updateTrendDataLoading(state, payload) {
      state.isTrendDataLoading = payload;
    },
    updateTrendDataCount(state, payload) {
      state.trendDataCount = payload;
    },
    updateChartKey(state, payload) {
      state.chartKey = (payload?.prefix ?? '') + random(10);
    },
    updateCachePickerValue(state, payload) {
      state.cacheDatePickerValue = payload;
    },
    updateCacheTimeRange(state, payload) {
      state.cacheTimeRange = payload;
    },
    updateFiledSettingConfigID(state, payload) {
      state.filedSettingConfigID = payload;
    },
    updateIndexSetList(state, payload) {
      state.indexSetList.length = 0;
      state.indexSetList = [];
      state.indexSetList.push(...payload);

      state.flatIndexSetList.length = 0;
      state.flatIndexSetList = (payload ?? []).map(item => [item, item.children ?? []]).flat(2);
    },

    updateIndexSetLoading(state, payload) {
      state.isIndexSetLoading = payload;
    },
    updateCatchFieldCustomConfig(state, payload) {
      Object.assign(
        state.catchFieldCustomConfig,
        {
          fieldsWidth: {},
          displayFields: [],
          filterSetting: [],
          filterAddition: [],
          sortList: [],
        },
        payload ?? {},
      );
    },

    updateCatchFilterAddition(state, { addition }) {
      if (addition?.length) {
        state.catchFieldCustomConfig.filterAddition.length = 0;
        state.catchFieldCustomConfig.filterAddition = [];
        state.catchFieldCustomConfig.filterAddition.push(...addition);
      }
    },
  },
  actions: {
    getIndexSetList(ctx, payload) {
      const { spaceUid, isLoading = true, is_group } = payload;
      if (isLoading) ctx.commit('updateIndexSetLoading', true);

      ctx.commit('updateIndexSetList', []);
      return http
        .request('retrieve/getIndexSetList', {
          query: {
            space_uid: spaceUid,
            is_group,
          },
        })
        .then(res => {
          let processedIndexSetList = [];
          if (res.data.length) {
            // 索引集数据加工
            processedIndexSetList = resolveIndexItemAttr(res.data);
            ctx.commit('updateIndexSetList', processedIndexSetList);
          }
          return [res, processedIndexSetList];
        })
        .finally(() => {
          ctx.commit('updateIndexSetLoading', false);
        });
    },
  },
};
