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

export function createLabelTargetState() {
  return {
    filterStr: '',
    treeList: [],
    defaultExpandList: [],
    matchCheckedList: [],
    matchCheckedItemList: [],
    matchSelectList: [],
    matchSelectItemList: [],
    treeLoading: false,
    labelLoading: false,
    treeRequestId: 0,
    labelRequestId: 0,
    treeIsEmpty: false,
    cacheRequestParams: {
      bk_biz_id: null,
      bcs_cluster_id: null,
      type: null,
      namespace: null,
    },
  };
}

export function isHaveSelectItem(state) {
  return !!(state.matchSelectList.length + state.matchCheckedList.length);
}

export function filterTreeNode(keyword, node) {
  return node.data.name.includes(keyword);
}

export function resetSelect(state) {
  state.treeRequestId += 1;
  state.labelRequestId += 1;
  state.treeLoading = false;
  state.labelLoading = false;
  state.matchSelectList = [];
  state.matchSelectItemList = [];
  state.matchCheckedList = [];
  state.matchCheckedItemList = [];
}

export function confirmLabel(state) {
  const allCheckedKey = [...state.matchSelectList, ...state.matchCheckedList];
  const allCheckedValue = [...state.matchSelectItemList, ...state.matchCheckedItemList].map(item => ({
    ...item,
    type: item.operator === '=' ? 'match_labels' : 'match_expressions',
  }));
  const matchLabels = allCheckedValue.filter(item => allCheckedKey.includes(item.id));
  const labelObj = { labelSelector: [...matchLabels] };
  resetSelect(state);
  return labelObj;
}

export function cancelDialog(state) {
  resetSelect(state);
}

export function onDialogHide(state) {
  resetSelect(state);
  state.filterStr = '';
}

export function onDialogShow(state, labelParams, idFactory) {
  const { bk_biz_id, bcs_cluster_id, type, namespaceStr, namespacesExclude } = labelParams;
  const namespaceKey = namespacesExclude === '!=' ? 'namespaces_exclude' : 'namespace';
  const requestParams = {
    bk_biz_id,
    bcs_cluster_id,
    type,
    ...(type === 'node' ? {} : { [namespaceKey]: namespaceStr === '*' ? undefined : namespaceStr }),
  };
  state.treeList = [];
  state.defaultExpandList = [];
  state.cacheRequestParams = requestParams;
  if (labelParams.labelSelector.length) {
    state.matchCheckedItemList = labelParams.labelSelector.map(item => ({
      ...item,
      id: idFactory(),
    }));
    state.matchCheckedList = state.matchCheckedItemList.map(item => item.id);
  }
  return requestParams;
}

export function catchCheckedItemList(state) {
  if (!state.matchSelectList.length) return;
  const checkedItemList = state.matchSelectItemList.filter(item => {
    if (state.matchSelectList.includes(item.id)) {
      return !state.matchCheckedItemList.some(
        mItem => item.key === mItem.key && item.value === mItem.value && item.operator === mItem.operator,
      );
    }
    return false;
  });
  state.matchCheckedItemList = [...state.matchCheckedItemList, ...checkedItemList];
  state.matchCheckedList = [...state.matchSelectList, ...state.matchCheckedList];
  state.matchSelectList = [];
}

export function selectTreeItem(state, treeItem) {
  state.labelRequestId += 1;
  const requestId = state.labelRequestId;
  catchCheckedItemList(state);
  state.matchSelectList = [];
  state.matchSelectItemList = [];
  state.labelLoading = false;
  const shouldRequest = ['pod', 'node'].includes(treeItem.data.type);
  if (shouldRequest) state.labelLoading = true;
  return { shouldRequest, requestId };
}

export function buildNodeLabelQuery({ nameSpaceStr, nameStr, bkBizId, bcsClusterId, type }) {
  const query = {
    namespace: nameSpaceStr,
    bcs_cluster_id: bcsClusterId,
    type,
    bk_biz_id: bkBizId,
    name: nameStr,
  };
  if (type === 'node') delete query.namespace;
  return query;
}

export function applyLabelResponse(state, requestId, res, labelSelector, idFactory) {
  if (requestId !== state.labelRequestId || res.code !== 0) return false;
  const allCheckedItemList = [...state.matchCheckedItemList, ...labelSelector];
  state.matchSelectItemList = res.data
    .filter(item => {
      if (!allCheckedItemList.length) return true;
      return !allCheckedItemList.some(
        mItem => item.key === mItem.key && item.value === mItem.value && mItem.operator === '=',
      );
    })
    .map(item => ({ ...item, operator: '=', id: idFactory() }));
  return true;
}

export function finishLabelRequest(state, requestId) {
  if (requestId === state.labelRequestId) state.labelLoading = false;
}
