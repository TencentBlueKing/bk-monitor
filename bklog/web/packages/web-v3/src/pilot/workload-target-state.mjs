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

export function createWorkloadState(container = {}) {
  return {
    formData: {
      workload_type: '',
      workload_name: '',
      container_name: '',
      ...container,
    },
    nameList: [],
    nameCannotClick: false,
    nameRequestId: 0,
  };
}

export function changeWorkloadType(state, value, typeList) {
  state.formData.workload_type = value;
  state.nameRequestId += 1;
  state.nameList = [];
  state.nameCannotClick = false;
  const requestId = state.nameRequestId;
  const known = typeList.map(item => item.id).includes(value);
  if (value && known) {
    state.nameCannotClick = true;
    return { shouldRequest: true, requestId };
  }
  return { shouldRequest: false, requestId };
}

export function buildWorkloadQuery({ type, bkBizId, namespaceStr, namespacesExclude, bcsClusterId }) {
  const namespaceKey = namespacesExclude === '!=' ? 'namespaces_exclude' : 'namespace';
  const query = {
    type,
    bk_biz_id: bkBizId,
    bcs_cluster_id: bcsClusterId,
  };
  if (namespaceStr !== '*') query[namespaceKey] = namespaceStr;
  return query;
}

export function settleWorkloadResponse(state, requestId, res) {
  if (requestId === state.nameRequestId && res.code === 0) {
    state.nameList = res.data.map(item => ({ id: item, name: item }));
  }
  if (requestId === state.nameRequestId) state.nameCannotClick = false;
}

export function destroyWorkload(state) {
  state.nameRequestId += 1;
}
