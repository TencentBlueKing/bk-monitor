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
import {
  detailAlertNotice,
  // detailEvent,
  listAlertNotice,
  listConvergeLog,
  listEvent,
  listEventLog,
  listSearchItem,
  stackedChart,
} from 'monitor-api/modules/alert_events';
import { transformDataKey } from 'monitor-common/utils/utils';

export const SET_SEARCH_LIST = 'SET_SEARCH_LIST';
const state = {
  searchList: [],
};
const mutations = {
  [SET_SEARCH_LIST](state, data) {
    state.searchList = data;
  },
};

const actions = {
  async getSearchList({ commit }, params) {
    const data = await listSearchItem(params).catch(() => []);
    const list = data.map(item => ({ ...item, multiable: true }));
    // list.unshift({
    //     id: 'bk_biz_id',
    //     name: '业务名',
    //     multiable: true,
    //     children: rootGetters.bizList.map(set => ({ id: set.id, name: set.text }))
    // })
    commit(SET_SEARCH_LIST, list);
  },
  async getEventList({ rootGetters }, params) {
    const list = await listEvent(params).catch(() => ({
      event_list: [],
      statistics_data: {},
    }));
    if (params.export) return list;
    const tagData = {
      anomalyCount: list.statistics_data?.abnormal_count || 0,
      shieldAnomalyCount: list.statistics_data?.shield_abnormal_count || 0,
      total: list.statistics_data?.total || 0,
      allCount: list.statistics_data?.all_count || 0,
    };
    const eventList = list.event_list?.map(item => {
      const bizItem = rootGetters.bizList.find(set => `${set.id}` === `${item.bk_biz_id}`) || {};
      return {
        id: item.id,
        bizId: bizItem.id,
        bizName: bizItem.text || '',
        anomalyCount: item.anomaly_count,
        duration: item.duration,
        beginTime: item.begin_time,
        children: item.children,
        strategyName: item.strategy_name,
        isAck: item.is_ack,
        ackMessage: item.ack_message,
        eventMessage: item.event_message,
        eventStatus: item.event_status,
        alertStatus: item.alert_status,
        level: item.level,
        collapse: false,
        isShielded: item.is_shielded,
        shieldType: item.shield_type,
      };
    });
    return {
      tagData,
      eventList,
    };
  },
  // async getEventDetailData(store, params) {
  //   const data = await detailEvent(params).catch(() => null);
  //   if (!data) {
  //     return data;
  //   }
  //   return transformDataKey(data);
  // },
  async getNoticeDetail(store, params) {
    const list = await listAlertNotice(params).catch(() => []);
    return list.map(item => transformDataKey(item));
  },
  async getNoticeTableDetail(store, params) {
    const data = await detailAlertNotice(params).catch(() => ({}));
    return transformDataKey(data);
  },
  async getListEventLog(store, params) {
    const data = await listEventLog(params);
    for (const item of data) {
      item.logIcon = `icon-mc-alarm-${item.operate.toLocaleLowerCase()}`;
      if (item.operate === 'RECOVER') {
        item.logIcon += 'ed';
      }

      if (item.operate === 'ANOMALY_NOTICE') {
        item.logIcon = 'icon-mc-alarm-notice';
      }

      if (item.operate === 'CLOSE') {
        item.logIcon = 'icon-mc-alarm-closed';
      }

      if (item.is_multiple) {
        item.collapse = true;
        item.expandTime = `${item.begin_time} 至 ${item.time}`;
        item.expand = false;
      } else {
        item.collapse = false;
        item.expand = true;
      }
      item.border = false;
      item.show = true;
      item.expandDate = '';
    }
    return transformDataKey(data);
  },
  // 获取变化趋势图数据
  async getChartData(store, params) {
    const data = await stackedChart(params).catch(() => ({}));
    return transformDataKey(data);
  },
  async getListConvergeLog(store, params) {
    const data = await listConvergeLog(params).catch(() => []);
    for (const item of data) {
      if (item.operate === 'ANOMALY_NOTICE') {
        item.logIcon = 'icon-mc-alarm-notice';
      } else {
        item.logIcon = `icon-mc-alarm-${item.operate.toLocaleLowerCase()}`;
      }
      if (item.operate === 'RECOVER') {
        item.logIcon += 'ed';
      }
      item.collapse = false;
      item.expand = true;
      item.border = false;
      item.show = true;
      item.expandTime = '';
    }
    return transformDataKey(data);
  },
};

const getters = {
  searchList(state) {
    return state.searchList;
  },
};

export default {
  namespaced: true,
  state,
  actions,
  mutations,
  getters,
};
