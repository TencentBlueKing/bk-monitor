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

import * as authorityMap from '@/common/authority-map';
import { random } from '@/components/monitor-echarts/utils';

import http from '@/api';

export default {
  namespaced: true,
  state: {
    chartKey: random(10), // 复用监控的图表，改变key重新请求图表
    cacheDatePickerValue: [],
    cacheTimeRange: '',
    filedSettingConfigID: 1,
    indexSetList: [],
    isIndexSetLoading: false,
    isTrendDataLoading: false,
  },
  mutations: {
    updateTrendDataLoading(state, payload) {
      state.isTrendDataLoading = payload;
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
    },
    updateIndexSetLoading(state, payload) {
      state.isIndexSetLoading = payload;
    },
  },
  actions: {
    getIndexSetList(ctx, payload) {
      const { spaceUid, isLoading = true } = payload;
      if (isLoading) ctx.commit('updateIndexSetLoading', true);
      return http
        .request('retrieve/getIndexSetList', {
          query: {
            space_uid: spaceUid,
          },
        })
        .then(res => {
          let indexSetList = [];
          if (res.data.length) {
            // 有索引集
            // 根据权限排序
            const s1 = [];
            const s2 = [];
            for (const item of res.data) {
              if (item.permission?.[authorityMap.SEARCH_LOG_AUTH]) {
                s1.push(item);
              } else {
                s2.push(item);
              }
            }

            indexSetList = s1.concat(s2);
            // 索引集数据加工
            indexSetList.forEach(item => {
              item.index_set_id = `${item.index_set_id}`;
              item.indexName = item.index_set_name;
              item.lightenName = ` (${item.indices.map(item => item.result_table_id).join(';')})`;
            });
            ctx.commit('updateIndexSetList', indexSetList);
          }
          return [res, indexSetList];
        })
        .finally(() => {
          ctx.commit('updateIndexSetLoading', false);
        });
    },
  },
};
