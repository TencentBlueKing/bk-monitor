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
import { getDefaultDashboard, setDefaultDashboard } from 'monitor-api/modules/grafana';

const state = {
  dashboardId: '',
  defaultDashboardId: -1,
  dashboardCheck: '',
  manageAuth: false,
};
const getters = {
  curDashboardId(state) {
    return state.dashboardId;
  },
  setDashboardButtonStatus(state) {
    if (state.dashboardId) {
      return state.defaultDashboardId !== state.dashboardId ? 1 : 2;
    }
    return 0;
  },
  dashboardCheck(state) {
    return state.dashboardCheck;
  },
  hasManageAuth(state) {
    return state.manageAuth;
  },
};

const mutations = {
  setDashboardId(state, id) {
    state.dashboardId = id;
  },
  setDefaultDashboardId(state, id) {
    state.defaultDashboardId = id;
  },
  setDashboardCheck(state, payload) {
    state.dashboardCheck = payload;
  },
  setHasManageAuth(state, payload) {
    state.manageAuth = payload;
  },
};

const actions = {
  async setDefaultDashboard({ commit, state, rootState }) {
    const data = await setDefaultDashboard({
      dashboard_uid: state.dashboardId,
      bk_biz_id: rootState.app.bizId,
    }).catch(() => false);
    commit('setDefaultDashboardId', data ? state.dashboardId : -1);
    return !!data;
  },
  async getDefaultDashboard({ commit, state, rootState }) {
    const data = await getDefaultDashboard({
      bk_biz_id: rootState.app.bizId,
    }).catch(() => false);
    commit('setDefaultDashboardId', data ? data.uid : state.defaultDashboardId);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions,
};
