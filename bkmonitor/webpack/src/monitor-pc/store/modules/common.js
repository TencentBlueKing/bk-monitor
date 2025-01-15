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
import { getLabel, getServiceCategory, getTopoTree } from 'monitor-api/modules/commons';

export const SET_TREE_DATA = 'SET_TREE_DATA';
export const SET_DATA_OBJECT = 'SET_DATA_OBJECT';
export const SET_SERVICE_CATEGORY = 'SET_SERVICE_CATEGORY';
const mutations = {
  SET_TREE_DATA(state, data) {
    state.treeData = data;
  },
  SET_DATA_OBJECT(state, data) {
    state.dataObject = data;
  },
  SET_SERVICE_CATEGORY(state, data) {
    state.serviceCategory = data;
  },
};
const state = {
  treeData: [],
  dataObject: [],
  serviceCategory: [],
};
const actions = {
  async getTopoTree({ commit }, params) {
    const arr = await getTopoTree(params).catch(() => []);
    commit(SET_TREE_DATA, arr);
    return arr;
  },
  async getDataObject({ commit }, params) {
    const arr = await getLabel(params).catch(() => []);
    commit(SET_DATA_OBJECT, arr);
    return arr;
  },
  async getServiceCategory({ commit }) {
    const arr = await getServiceCategory().catch(() => []);
    commit(SET_SERVICE_CATEGORY, arr);
    return arr;
  },
};
const getters = {
  treeData(state) {
    return state.treeData;
  },
  dataObject(state) {
    return state.dataObject;
  },
  serviceCategory(state) {
    return state.serviceCategory;
  },
};

export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions,
};
