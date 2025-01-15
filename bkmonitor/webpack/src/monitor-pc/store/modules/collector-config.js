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
import { getLabel } from 'monitor-api/modules/commons';

export const SET_ADD_MODE = 'SET_ADD_MODE';
export const SET_ADD_DATA = 'SET_ADD_DATA';
export const SET_OBJECT_TYPE = 'SET_OBJECT_TYPE';
export const SET_INFO_DATA = 'SET_INFO_DATA';

const state = {
  addMode: 'add',
  addData: {},
  objectType: '', // 采集对象类型 SERVICE 为 服务类
  infoData: null, // 缓存config-set组件的info
};

const mutations = {
  [SET_ADD_MODE](state, mode) {
    state.addMode = mode;
  },
  [SET_ADD_DATA](state, data) {
    state.addData = Object.assign({}, data);
  },
  [SET_OBJECT_TYPE](state, data) {
    state.objectType = data;
  },
  [SET_INFO_DATA](state, data) {
    state.infoData = data;
  },
};
const getters = {
  addParams(state) {
    return {
      mode: state.addMode,
      data: JSON.parse(JSON.stringify(state.addData)),
    };
  },
  getObjectType(state) {
    return state.objectType;
  },
  infoData(state) {
    return state.infoData;
  },
};
const actions = {
  getCollectorObject() {
    return getLabel({ include_admin_only: false });
  },
};
export default {
  namespaced: true,
  state,
  actions,
  mutations,
  getters,
};
