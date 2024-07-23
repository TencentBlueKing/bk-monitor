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
import { listUptimeCheckTask } from 'monitor-api/modules/model';

export const SET_TABLE_STORE = 'SET_TABLE_STORE';
export const SET_KEY_WORD = 'SET_KEY_WORD';
export const SET_ALL_DATA = 'SET_ALL_DATA';
export const SET_TASK_LIST = 'SET_TASK_LIST';
export const SET_UNGROUP_TASK_LIST = 'SET_UNGROUP_TASK_LIST';
export const SET_TOTAL = 'SET_TOTAL';
export const SET_PAGE = 'SET_PAGE';
export const SET_PAGE_SIZE = 'SET_PAGE_SIZE';
export const SET_SEARCH_DATA = 'SET_SEARCH_DATA';
export const SET_CUR_GROUP_ID = 'SET_CUR_GROUP_ID';
export const SET_TABLE_DATA = 'SET_TABLE_DATA';
export const SET_GROUP_TASK_LIST = 'SET_GROUP_TASK_LIST';
const state = {
  tableStore: null,
  keyword: '',
  allData: [],
  taskList: [],
  unGroupTaskList: [],
  total: 0,
  searchData: [],
  curGroupId: -1,
  page: 1,
  pageSize: +localStorage.getItem('__common_page_size__') || 10,
  pageList: [10, 20, 50, 100],
  tableData: [],
  groupTaskList: [],
};

const getters = {
  tableData(state) {
    return state.tableData;
  },
  pagination({ page, pageSize, pageList, total }) {
    return {
      limit: pageSize,
      count: total,
      current: page,
      'pagination-list': pageList,
    };
  },
  groupTaskList(state) {
    return state.groupTaskList;
  },
  keyword(state) {
    return state.keyword;
  },
  taskList(state) {
    return state.taskList;
  },
  allData(state) {
    return state.allData;
  },
  searchData(state) {
    return state.searchData;
  },
};

const mutations = {
  SET_TABLE_STORE(state, data) {
    state.tableStore = data;
  },
  SET_KEY_WORD(state, keyword) {
    state.keyword = keyword;
  },
  SET_ALL_DATA(state, data) {
    state.allData = data;
  },
  SET_UNGROUP_TASK_LIST(state, data) {
    state.unGroupTaskList = data;
  },
  SET_TASK_LIST(state, data) {
    state.taskList = data;
  },
  SET_TOTAL(state, total) {
    state.total = total;
  },
  SET_PAGE(state, page) {
    state.page = page;
  },
  SET_PAGE_SIZE(state, pageSize) {
    localStorage.setItem('__common_page_size__', pageSize);
    state.pageSize = pageSize;
  },
  SET_SEARCH_DATA(state, data) {
    state.searchData = data;
  },
  SET_CUR_GROUP_ID(state, id) {
    state.curGroupId = id;
  },
  SET_TABLE_DATA(state, data = []) {
    state.tableData = data;
  },
  SET_GROUP_TASK_LIST(state, data = []) {
    state.groupTaskList = data;
  },
};
const actions = {
  async getUptimeCheckTask({ commit, dispatch }) {
    const { task_data, has_node, group_data } = await listUptimeCheckTask({
      get_available: true,
      get_task_duration: true,
      get_groups: true,
      ordering: '-id',
    }).catch(() => ({
      task_data: [],
      has_node: false,
      group_data: [],
    }));
    let i = 0;
    const len = task_data.length;
    const taskList = [];
    const unGroupTaskList = [];
    while (i < len) {
      const item = task_data[i];
      if (item.config?.length) {
        item.configData = item.config;
      }
      if (item.nodes?.length) {
        item.nodes.forEach(set => {
          set.locationData = set.location;
        });
      }
      unGroupTaskList.push(item);
      taskList.push({
        name: item.name,
        id: item.id,
        bk_biz_id: item.bk_biz_id,
      });
      item.switch = ['running', 'stop_failed'].includes(item.status);
      i += 1;
    }
    commit(SET_ALL_DATA, task_data);
    commit(SET_UNGROUP_TASK_LIST, unGroupTaskList);
    commit(SET_TASK_LIST, taskList);
    commit(SET_TOTAL, task_data.length);
    commit(SET_SEARCH_DATA, task_data);
    commit(SET_CUR_GROUP_ID, -1);
    dispatch('setTabelData');
    await dispatch('setKeyword', state.keyword);
    return { task_data, has_node, group_data };
  },
  setTabelData({ commit, state }, search = false) {
    search && commit(SET_PAGE, 1);
    if (state.keyword.includes('节点:')) {
      const [, keyword] = state.keyword.trim().split('节点:');
      const nodes = [];
      state.unGroupTaskList.forEach(item => {
        const node = item.nodes.find(node => node.name === keyword);
        node && nodes.push(item);
      });
      commit(SET_SEARCH_DATA, nodes);
    } else {
      const searchData = !state.keyword
        ? state.allData
        : state.allData.filter(item => ~item.name.indexOf(state.keyword));
      commit(SET_SEARCH_DATA, searchData);
    }
    commit(SET_TOTAL, state.searchData.length);
    commit(SET_TABLE_DATA, state.searchData.slice(state.pageSize * (state.page - 1), state.pageSize * state.page));
  },
  async getTaskList({ commit, dispatch }, { groupDetail, tasks }) {
    if (groupDetail) {
      let data = await dispatch('getGroupDetailData', tasks);
      data = !state.keyword ? data : data.filter(item => ~item.name.indexOf(state.keyword));
      commit(SET_GROUP_TASK_LIST, data);
    } else {
      const data = await dispatch('getUngroupSearchData');
      commit(SET_GROUP_TASK_LIST, data);
    }
  },

  async getUngroupSearchData({ state, commit }) {
    let searchData = [];
    if (state.keyword.includes('节点:')) {
      const [, keyword] = state.keyword.trim().split('节点:');
      state.allData.forEach(item => {
        const node = item.nodes.find(node => node.name === keyword);
        node && searchData.push(item);
      });
    } else {
      searchData = !state.keyword ? state.allData : state.allData.filter(item => ~item.name.indexOf(state.keyword));
    }
    commit(SET_SEARCH_DATA, searchData);
    if (state.keyword.includes('节点:')) {
      const [, keyword] = state.keyword.trim().split('节点:');
      const nodes = [];
      state.unGroupTaskList.forEach(item => {
        const node = item.nodes.find(node => node.name === keyword);
        node && nodes.push(item);
      });
      return nodes;
    }
    return !state.keyword
      ? state.unGroupTaskList
      : state.unGroupTaskList.filter(item => ~item.name.indexOf(state.keyword));
  },
  async getGroupDetailData({ state }, tasks = []) {
    return state.allData.filter(item => tasks.includes(item.id));
  },
  async setKeyword({ commit, dispatch }, params) {
    if (typeof params === 'string') {
      commit(SET_KEY_WORD, params);
      await dispatch('getTaskList', { groupDetail: false });
    } else {
      commit(SET_KEY_WORD, params.keyword);
      const { groupDetail, tasks } = params;
      await dispatch('getTaskList', { groupDetail, tasks });
    }
  },
};
export default {
  namespaced: true,
  state,
  mutations,
  getters,
  actions,
};
