/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storeCacheService } from '@/storage';

import { isFeatureToggleOn, isSceneFilterValuesEmpty, isSceneRetrieve } from '../helper.ts';
import { BK_LOG_STORAGE } from '../store.type.ts';
import {
  buildOriginAddition,
  buildRequestAddition,
  buildRetrieveParams,
  resolveFieldAliasMap,
  resolveFieldTree,
  resolveFilteredFieldList,
  resolveGetterVisibleFields,
  resolveRawFieldList,
} from '../services/retrieve-query.service.js';

const getters = {

    runVersion: state => state.runVersion,
    user: state => state.user,
    space: state => state.space,
    spaceUid: state => state.spaceUid,
    indexId: state => state.indexId,
    visibleFields: state => resolveGetterVisibleFields(state),
    /** 是否为场景化检索模式 */
    isSceneMode: state => isSceneRetrieve(state),
    /** 场景化检索模式下，过滤条件是否全部为空 */
    isSceneFilterEmpty: (state) => {
      if (!isSceneRetrieve(state)) return false;
      return isSceneFilterValuesEmpty(state.indexItem?.scene_filter_values);
    },
    /** 是否是联合查询 */
    isUnionSearch: state => !!state.indexItem.isUnionIndex,
    /** 联合查询索引集ID数组 */
    unionIndexList: state => state.unionIndexList,
    unionIndexItemList: state => state.unionIndexItemList,
    bkBizId: state => state.bkBizId,
    defaultBizId: state => state.defaultBizId,
    mySpaceList: state => state.mySpaceList,
    pageLoading: state => state.pageLoading,
    globalsData: state => state.globalsData,
    iframeQuery: state => state.iframeQuery,
    demoUid: state => state.demoUid,
    spaceBgColor: state => state.spaceBgColor,
    isEnLanguage: state => state.isEnLanguage,
    chartSizeNum: state => state.chartSizeNum,
    isShowGlobalDialog: state => state.isShowGlobalDialog,
    globalActiveLabel: state => state.globalActiveLabel,
    globalSettingList: state => state.globalSettingList,
    maskingToggle: state => state.maskingToggle,
    isNotVisibleFieldsShow: state => state.isNotVisibleFieldsShow,
    /** 脱敏灰度判断 */
    isShowMaskingTemplate: state => isFeatureToggleOn('log_desensitize', state.bkBizId),
    isLimitExpandView: state => state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW],
    custom_sort_list: state => state.retrieve.catchFieldCustomConfig.sortList ?? [],

    originAddition: state => buildOriginAddition(state),

    // @ts-ignore
    retrieveParams: (state, getters, _, rootGetters) => buildRetrieveParams(state, getters, rootGetters),
    /**
     * API 请求参数 addition 格式化
     * 这里会过滤掉隐藏的查询条件
     * @param {*} state
     * @param {*} getters
     * @returns
     */
    requestAddition: (state, getters) => buildRequestAddition(state, getters),
    isNewRetrieveRoute: () => {
      const v = localStorage.getItem('retrieve_version') ?? 'v2';
      storeCacheService.setLocalStorageMirror('retrieve_version', v).catch(() => {});
      return v === 'v2';
    },
    storeIsShowClusterStep: state => state.storeIsShowClusterStep,
    isAiAssistantActive: state => state.features.isAiAssistantActive,
    filteredFieldList: state => resolveFilteredFieldList(state),
    rawFieldList: state => resolveRawFieldList(state),
    fieldTree: state => resolveFieldTree(state),
    fieldAliasMap: state => resolveFieldAliasMap(state),

};

export default getters;
