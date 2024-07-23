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
  addMonitorTarget,
  exportPackage,
  historyDetail,
  historyList,
  importConfig,
} from 'monitor-api/modules/export_import';
import { transformDataKey } from 'monitor-common/utils/utils';

export const SET_CURRENT_HIS_REQ = 'SET_CURRENT_HIS_REQ';
const state = {
  cancelReq: null,
};
const getters = {
  cancelReq(state) {
    return state.cancelReq;
  },
};
const mutations = {
  [SET_CURRENT_HIS_REQ](state, req) {
    state.cancelReq = req;
  },
};
const actions = {
  /**
   * 历史列表页
   * @param {*} commit
   * @param {*} params
   */
  async getHistoryList() {
    const list = await historyList().catch(() => []);
    if (!list) {
      return [];
    }
    return transformDataKey(list);
  },
  /**
   * 开始导入
   * @param {*} commit
   * @param {*} params
   */
  async handleImportConfig(store, params) {
    const importParams = {
      uuid_list: params.uuids,
      is_overwrite_mode: params.isOverwriteMode,
    };
    // 历史ID存在就丢给后端
    if (params.historyId) {
      importParams.import_history_id = params.historyId;
    }
    const data = await importConfig(importParams).catch(() => null);
    if (!data) {
      return null;
    }
    return transformDataKey(data);
  },
  /**
   * 获取历史详情
   * @param {*} commit
   * @param {*} id
   */
  async getHistoryDetail({ commit }, id) {
    const cancelFn = c => {
      commit(SET_CURRENT_HIS_REQ, c);
    };
    const data = await historyDetail({ import_history_id: id }, { needCancel: true, cancelFn }).catch(() => ({
      configList: [],
    }));
    return transformDataKey(data);
  },
  /**
   * 统一添加监控目标
   * @param {*} commit
   * @param {*} params
   */
  async addMonitorTarget(store, params) {
    const data = await addMonitorTarget(params);
    return data;
  },
  /**
   * 上传文件
   * @param {*} commit
   * @param {*} params
   */
  async exportPackage(store, params) {
    const data = await exportPackage(params).catch(err => err);
    return transformDataKey(data);
  },
};
export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions,
};
