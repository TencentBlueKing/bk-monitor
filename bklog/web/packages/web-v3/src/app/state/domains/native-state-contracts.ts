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

/** Public action names used only at the external compatibility and audit boundary. */
export const ROOT_COMMAND_NAMES = [
  'SET_APP_STATE',
  'updateAiMode',
  'updateStorage',
  'updateApiError',
  'deleteApiError',
  'updateFavoriteList',
  'updateChartParams',
  'updateIndexItem',
  'updateIndexSetOperatorConfig',
  'resetIndexsetItemParams',
  'updateIndexSetFieldConfig',
  'updateIndexSetCustomConfig',
  'resetIndexSetQueryResult',
  'updateIndexSetQueryResult',
  'updateIndexItemParams',
  'updateIndexSetFieldConfigList',
  'updataOperatorDictionary',
  'updateSpace',
  'updateMySpaceList',
  'patchMySpaceListItem',
  'updateUnionIndexList',
  'updateGlobalsData',
  'updateIframeQuery',
  'updateShowFieldsConfigPopoverNum',
  'updateChartSize',
  'updateVisibleFields',
  'updateVisibleFieldMinWidth',
  'updateIndexFieldInfo',
  'updateIndexFieldEggsItems',
  'resetIndexFieldInfo',
  'updateSqlQueryFieldList',
  'updateNotTextTypeFields',
  'updateTableLineIsWrap',
  'updateState',
  'updateIsSetDefaultTableColumn',
  'resetVisibleFields',
  'resetIndexSetOperatorConfig',
  'updateClearSearchValueNum',
  'initMonitorState',
  'resetState',
] as const;
export const ROOT_QUERY_NAMES = [
  'userInfo',
  'getMenuList',
  'requestMenuList',
  'getGlobalsData',
  'checkAllowed',
  'getApplyData',
  'checkAndGetData',
  'requestIndexSetFieldInfo',
  'requestIndexSetQuery',
  'requestIndexSetItemChanged',
  'requestIndexSetValueList',
  'requestFavoriteList',
  'setQueryCondition',
  'changeShowUnionSource',
  'requestSearchTotal',
  'handleTrendDataZoom',
  'userFieldConfigChange',
] as const;
export const ROOT_SELECTOR_NAMES = {
  runVersion: 'runVersion',
  user: 'user',
  space: 'space',
  spaceUid: 'spaceUid',
  indexId: 'indexId',
  unionIndexList: 'unionIndexList',
  unionIndexItemList: 'unionIndexItemList',
  bkBizId: 'bkBizId',
  defaultBizId: 'defaultBizId',
  mySpaceList: 'mySpaceList',
  pageLoading: 'pageLoading',
  globalsData: 'globalsData',
  iframeQuery: 'iframeQuery',
  demoUid: 'demoUid',
  spaceBgColor: 'spaceBgColor',
  isEnLanguage: 'isEnLanguage',
  chartSizeNum: 'chartSizeNum',
  isShowGlobalDialog: 'isShowGlobalDialog',
  globalActiveLabel: 'globalActiveLabel',
  globalSettingList: 'globalSettingList',
  maskingToggle: 'maskingToggle',
  isNotVisibleFieldsShow: 'isNotVisibleFieldsShow',
  storeIsShowClusterStep: 'storeIsShowClusterStep',
  visibleFields: 'resolvedVisibleFields',
  isSceneMode: 'isSceneMode',
  isSceneFilterEmpty: 'isSceneFilterEmpty',
  isUnionSearch: 'isUnionSearch',
  isShowMaskingTemplate: 'isShowMaskingTemplate',
  isLimitExpandView: 'isLimitExpandView',
  custom_sort_list: 'custom_sort_list',
  originAddition: 'originAddition',
  retrieveParams: 'retrieveParams',
  requestAddition: 'requestAddition',
  isNewRetrieveRoute: 'isNewRetrieveRoute',
  isAiAssistantActive: 'isAiAssistantActive',
  filteredFieldList: 'filteredFieldList',
  rawFieldList: 'rawFieldList',
  fieldTree: 'fieldTree',
  fieldAliasMap: 'fieldAliasMap',
  displayFieldAliasMap: 'displayFieldAliasMap',
} as const;
