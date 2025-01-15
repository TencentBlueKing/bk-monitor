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
import Vue from 'vue';

import { getVariableValue } from 'monitor-api/modules/grafana';
import { noticeGroupList } from 'monitor-api/modules/notice_group';
import {
  getDimensionValues,
  getIndexSetList,
  getLogFields,
  getScenarioList,
  getStrategyV2,
  getTargetDetail,
  // renderNoticeTemplate,
  getUnitInfo,
  getUnitList,
  noticeVariableList,
  strategyConfig,
} from 'monitor-api/modules/strategies';

export const SET_LOADING = 'SET_LOADING';
export const SET_LOG_LOADING = 'SET_LOG_LOADING';
export const SET_GROUP_LIST = 'SET_GROUP_LIST';
export const SET_DIMENSION_VALUE_MAP = 'SET_DIMENSION_VALUE_MAP';
export const SET_STRATEGY_PARAMS = 'SET_STRATEGY_PARAMS';
export const SET_SCENARIO_LIST = 'SET_SCENARIO_LIST';
export const SET_EMPTY_DIMENSION = 'SET_EMPTY_DIMENSION';
export const SET_DIMENSIONS_OF_SERIES = 'SET_DIMENSIONS_OF_SERIES';

const state = {
  groupList: [],
  scenarioList: [],
  dimensionValueLoading: false,
  logDimensionLoading: false,
  dimensionsValueMap: {},
  strategyParams: null,
  algorithmOptionMap: {
    Threshold: '静态阈值',
    SimpleRingRatio: '环比（简易）',
    SimpleYearRound: '同比（简易）',
    AdvancedRingRatio: '环比（高级）',
    AdvancedYearRound: '同比（高级）',
    PartialNodes: '部分节点数',
    YearRoundAmplitude: '同比振幅',
    RingRatioAmplitude: '环比振幅',
    YearRoundRange: '同比区间',
    IntelligentDetect: '智能异常检测',
  },
  uptimeCheckMap: {
    available: 'Threshold',
    task_duration: 'Threshold',
    message: 'PartialNodes',
    response_code: 'PartialNodes',
  },
  /* 用于策略配置无数据告警的维度选择（promql模式） */
  dimensionsOfSeries: [],
};
const mutations = {
  SET_LOADING(state, v) {
    state.dimensionValueLoading = v;
  },
  SET_LOG_LOADING(state, v) {
    state.logDimensionLoading = v;
  },
  SET_GROUP_LIST(state, data) {
    state.groupList = data;
  },
  SET_DIMENSION_VALUE_MAP(state, { id, data }) {
    state.dimensionsValueMap[id] = data;
  },
  SET_STRATEGY_PARAMS(state, params) {
    state.strategyParams = Object.assign({}, params);
  },
  SET_SCENARIO_LIST(state, data = []) {
    state.scenarioList = data;
  },
  SET_EMPTY_DIMENSION(state) {
    state.dimensionsValueMap = {};
  },
  [SET_DIMENSIONS_OF_SERIES](state, v) {
    state.dimensionsOfSeries = v;
  },
};
const actions = {
  async getNoticeGroupList({ commit }) {
    await noticeGroupList().then(data => {
      const groupData = data.map(item => ({
        id: item.id,
        name: item.name,
        receiver: item.notice_receiver.map(rec => rec.display_name),
      }));
      commit(SET_GROUP_LIST, groupData);
    });
  },
  async getDimensionValueList({ commit }, params) {
    // commit(SET_LOADING, needLoading)
    await getDimensionValues(params, { needRes: true })
      .then(({ data, tips }) => {
        if (tips?.length) {
          Vue.prototype.$bkMessage({
            theme: 'warning',
            message: tips,
          });
        }
        commit(SET_DIMENSION_VALUE_MAP, {
          id: params.field,
          data: Array.isArray(data) ? data : [],
        });
      })
      .catch(() => []);
  },
  async getVariableValueList({ commit, rootGetters }, params) {
    if (params.params.data_source_label === 'custom' && params.params.data_type_label === 'event') {
      params.params.result_table_id = `${params.bk_biz_id || rootGetters.bizId}_bkmonitor_event_${
        params.params.result_table_id
      }`;
      params.params.metric_field = '_index';
    }

    await getVariableValue(params, { needRes: true })
      .then(({ data, tips }) => {
        if (tips?.length) {
          Vue.prototype.$bkMessage({
            theme: 'warning',
            message: tips,
          });
        }
        const result = Array.isArray(data) ? data.map(item => ({ name: item.label, id: item.value })) : [];
        const { field } = params.params;
        commit(SET_DIMENSION_VALUE_MAP, {
          id: field,
          data: result,
        });
      })
      .catch(() => []);
  },
  async addStrategyConfig(store, params) {
    await strategyConfig(params);
  },
  // 获取索引集数据
  async getIndexSetList(store, params) {
    const data = await getIndexSetList(params).catch(() => null);
    return data;
  },
  // 获取日志关键字维度
  async getLogFields({ commit }, params) {
    commit(SET_LOG_LOADING, true);
    const data = await getLogFields(params)
      .catch(() => ({
        dimension: [],
        condition: [],
      }))
      .finally(() => {
        commit(SET_LOG_LOADING, false);
      });
    return data;
  },
  // 获取策略模板变量列表
  async getNoticeVariableList({ rootGetters }) {
    const data = await noticeVariableList({ bk_biz_id: rootGetters.bizId }).catch(() => []);
    return data;
  },
  // 获取策略模板预览
  async getRenderNoticeTemplate() {
    // const data = await renderNoticeTemplate({
    //   ...params,
    //   bk_biz_id: rootGetters.bizId
    // }).catch(() => []);
    // return data;
    return undefined;
  },
  async getScenarioList({ commit }) {
    await getScenarioList().then(data => {
      commit(SET_SCENARIO_LIST, data);
    });
  },
  // 通过id获取单位信息
  async getUnitData({ rootGetters }, { unitId }) {
    const data = await getUnitInfo({
      unit_id: unitId,
      bk_biz_id: rootGetters.bizId,
    }).catch(() => ({}));
    return data;
  },
  async getUnitList(store, params) {
    const arr = await getUnitList(params).catch(() => []);
    return arr;
  },
  async getStrategyConfigDetail(store, params) {
    const [targetDetail, strategyDetail] = await Promise.all([
      getTargetDetail({ strategy_ids: [params.id] }).catch(() => ({})),
      getStrategyV2(params).catch(() => ({})),
    ]);
    const strategyTarget = targetDetail?.[params.id] || {};
    const filed = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.field || '';
    const targetType = strategyTarget.node_type || '';
    let targetList = strategyDetail?.items?.[0]?.target?.[0]?.[0]?.value || [];
    // 对旧版的策略target进行特殊处理
    if (targetType === 'INSTANCE' && filed === 'bk_target_ip') {
      targetList = targetList.map(item => ({ ...item, ip: item.bk_target_ip, bk_cloud_id: item.bk_target_cloud_id }));
    }
    targetList.length && (targetList[0].instances_count = strategyTarget.instance_count || 0);
    return {
      ...strategyDetail,
      targetDetail: { ...strategyTarget, detail: strategyTarget.target_detail, target_detail: targetList },
    };
  },
};
const getters = {
  groupList(state) {
    return state.groupList;
  },
  scenarioList(state) {
    return state.scenarioList;
  },
  dimensionValueLoading(state) {
    return state.dimensionValueLoading;
  },
  logDimensionLoading(state) {
    return state.logDimensionLoading;
  },
  dimensionsValueMap(state) {
    return state.dimensionsValueMap;
  },
  strategyParams(state) {
    return state.strategyParams;
  },
  algorithmOptionMap(state) {
    return state.algorithmOptionMap;
  },
  uptimeCheckMap(state) {
    return state.uptimeCheckMap;
  },
};
export default {
  namespaced: true,
  state,
  mutations,
  getters,
  actions,
};
