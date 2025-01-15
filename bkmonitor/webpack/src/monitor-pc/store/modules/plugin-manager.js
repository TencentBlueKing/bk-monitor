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
import { operatorSystemCollectorPlugin } from 'monitor-api/modules/model';
import { getReservedWord } from 'monitor-api/modules/plugin';

export const SET_PLUGIN_DATA = 'SET_PLUGIN_DATA';
export const SET_PLUGIN_ID = 'SET_PLUGIN_ID';
export const SET_OS_LIST = 'SET_OS_LIST';
export const SET_LABELS = 'SET_LABELS';
export const SET_RESERVED_WORD = 'SET_RESERVED_WORD';
export const SET_PLUGIN_CONFIG = 'SET_PLUGIN_CONFIG';

const state = {
  pluginData: {},
  pluginId: -1,
  osList: [],
  labels: [],
  reservedWords: [],
  // 单个插件文件缓存
  pluginConfigCache: null,
};

const mutations = {
  [SET_PLUGIN_DATA](state, data) {
    state.pluginData = data;
  },
  [SET_PLUGIN_ID](state, id) {
    state.pluginId = id;
  },
  [SET_OS_LIST](state, osList) {
    state.osList = osList;
  },
  [SET_LABELS](state, labels) {
    state.labels = labels;
  },
  [SET_RESERVED_WORD](state, words) {
    state.reservedWords = words;
  },
  [SET_PLUGIN_CONFIG](state, file) {
    state.pluginConfigCache = file;
  },
};
const actions = {
  async getOsList({ commit, state }) {
    try {
      const data = state.osList.length ? state.osList : await operatorSystemCollectorPlugin();
      commit('SET_OS_LIST', data);
      return Promise.resolve(data);
    } catch (error) {
      return Promise.reject(error);
    }
  },
  async getLabels({ commit, state }) {
    try {
      const data = state.labels.length ? state.labels : await getLabel({ include_admin_only: false });
      commit('SET_LABELS', data);
      return Promise.resolve(data);
    } catch (error) {
      return Promise.reject(error);
    }
  },
  async getReservedWords({ commit, state }) {
    try {
      const data = state.reservedWords.length ? state.reservedWords : await getReservedWord();
      commit('SET_RESERVED_WORD', data.RT_RESERVED_WORD_EXACT || data);
      return Promise.resolve(data.RT_RESERVED_WORD_EXACT || data);
    } catch (error) {
      return Promise.reject(error);
    }
  },
};
const getters = {
  pluginData(state) {
    return state.pluginData;
  },
  osList(state) {
    return state.osList;
  },
  labels(state) {
    return state.labels;
  },
  reservedWords(state) {
    return state.reservedWords;
  },
  pluginConfigCache(state) {
    return state.pluginConfigCache;
  },
};
export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
};
