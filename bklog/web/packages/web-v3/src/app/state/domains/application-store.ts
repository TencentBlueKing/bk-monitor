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

import '../initialize-pinyin';
import { defineStore, type Pinia } from 'pinia';
import { createStoreState } from '../state';
import { applicationPinia, resolveApplicationPinia } from '../pinia';
import defaultRequestPool, { RequestPool } from '../request-pool';
import { useRetrieveStore } from './retrieve-store';
import { useCollectionStore } from './collection-store';
import { useGlobalsStore } from './globals-store';
import type { ApplicationState } from '../application-store.type';
import { storeCacheService } from '@/platform/persistence/index';
import { isFeatureToggleOn, isSceneFilterValuesEmpty, isSceneRetrieve } from '../helper.ts';
import { BK_LOG_STORAGE } from '../store.type.ts';
import {
  buildOriginAddition,
  buildRequestAddition,
  buildRetrieveParams,
  resolveDisplayFieldAliasMap,
  resolveFieldAliasMap,
  resolveFieldTree,
  resolveFilteredFieldList,
  resolveGetterVisibleFields,
  resolveRawFieldList,
} from '../services/retrieve-query.service.js';
import * as appQueries from '../actions/app-actions.js';
import * as miscQueries from '../actions/retrieve-misc-actions.js';
import * as queryQueries from '../actions/query-condition-actions.js';
import * as retrieveQueries from '../actions/retrieve-search-actions.js';
import * as stateOperations from '../mutations/index.js';
export interface RetrieveQueryPayload {
  isPagination?: boolean;
  cancelToken?: unknown;
  searchCount?: number;
  defaultSortList?: [string, string][];
  from?: string;
}
/** Explicit instance closure keeps cross-domain getters on the owning Pinia. */
function createNativeApplicationStore(pinia: Pinia) {
  const requestPool = pinia === applicationPinia ? defaultRequestPool : new RequestPool();
  return defineStore('bklog.application', {
    state: createStoreState,
    getters: {
      requestPool: () => requestPool,
      retrieve: () => useRetrieveStore(pinia),
      collect: () => useCollectionStore(pinia),
      globals: () => useGlobalsStore(pinia),
      sceneConfigList: () => useRetrieveStore(pinia).sceneConfigList,
      resolvedVisibleFields(): ReturnType<typeof resolveGetterVisibleFields> {
        return resolveGetterVisibleFields(this);
      },
      isSceneMode(): boolean {
        return isSceneRetrieve(this);
      },
      isSceneFilterEmpty(): boolean {
        if (!isSceneRetrieve(this)) return false;
        return isSceneFilterValuesEmpty(this.indexItem?.scene_filter_values);
      },
      isUnionSearch(): boolean {
        return !!this.indexItem.isUnionIndex;
      },
      isShowMaskingTemplate(): boolean {
        return isFeatureToggleOn('log_desensitize', this.bkBizId);
      },
      isLimitExpandView(): ReturnType<typeof createStoreState>['storage'][BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW] {
        return this.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW];
      },
      custom_sort_list(): ReturnType<typeof useRetrieveStore>['catchFieldCustomConfig']['sortList'] {
        return this.retrieve.catchFieldCustomConfig.sortList ?? [];
      },
      originAddition(): ReturnType<typeof buildOriginAddition> {
        return buildOriginAddition(this);
      },
      retrieveParams(): ReturnType<typeof buildRetrieveParams> {
        return buildRetrieveParams(this, this, this);
      },
      requestAddition(): ReturnType<typeof buildRequestAddition> {
        return buildRequestAddition(this, this);
      },
      isNewRetrieveRoute(): boolean {
        const v = localStorage.getItem('retrieve_version') ?? 'v2';
        storeCacheService.setLocalStorageMirror('retrieve_version', v).catch(() => {});
        return v === 'v2';
      },
      isAiAssistantActive(): boolean {
        return this.features.isAiAssistantActive;
      },
      filteredFieldList(): ReturnType<typeof resolveFilteredFieldList> {
        return resolveFilteredFieldList(this);
      },
      rawFieldList(): ReturnType<typeof resolveRawFieldList> {
        return resolveRawFieldList(this);
      },
      fieldTree(): ReturnType<typeof resolveFieldTree> {
        return resolveFieldTree(this);
      },
      fieldAliasMap(): ReturnType<typeof resolveFieldAliasMap> {
        return resolveFieldAliasMap(this);
      },
      displayFieldAliasMap(): ReturnType<typeof resolveDisplayFieldAliasMap> {
        return resolveDisplayFieldAliasMap(this);
      },
    },
    actions: {
      SET_APP_STATE(data?: Parameters<typeof stateOperations.applyApplicationState>[1]): void {
        stateOperations.applyApplicationState(this, data);
      },
      updateAiMode(payload?: Parameters<typeof stateOperations.updateAiMode>[1]): void {
        stateOperations.updateAiMode(this, payload);
      },
      updateStorage(payload?: Parameters<typeof stateOperations.updateStorage>[1]): void {
        stateOperations.updateStorage(this, payload);
      },
      updateApiError(payload: Parameters<typeof stateOperations.updateApiError>[1]): void {
        stateOperations.updateApiError(this, payload);
      },
      deleteApiError(apiName?: Parameters<typeof stateOperations.deleteApiError>[1]): void {
        stateOperations.deleteApiError(this, apiName);
      },
      updateFavoriteList(payload?: Parameters<typeof stateOperations.updateFavoriteList>[1]): void {
        stateOperations.updateFavoriteList(this, payload);
      },
      updateChartParams(params?: Parameters<typeof stateOperations.updateChartParams>[1]): void {
        stateOperations.updateChartParams(this, params);
      },
      updateIndexItem(payload?: Parameters<typeof stateOperations.updateIndexItem>[1]): void {
        stateOperations.updateIndexItem(this, payload);
      },
      updateIndexSetOperatorConfig(payload?: Parameters<typeof stateOperations.updateIndexSetOperatorConfig>[1]): void {
        stateOperations.updateIndexSetOperatorConfig(this, payload);
      },
      resetIndexsetItemParams(payload?: Parameters<typeof stateOperations.resetIndexsetItemParams>[1]): void {
        stateOperations.resetIndexsetItemParams(this, payload);
      },
      updateIndexSetFieldConfig(payload?: Parameters<typeof stateOperations.updateIndexSetFieldConfig>[1]): void {
        stateOperations.updateIndexSetFieldConfig(this, payload);
      },
      updateIndexSetCustomConfig(payload?: Parameters<typeof stateOperations.updateIndexSetCustomConfig>[1]): void {
        stateOperations.updateIndexSetCustomConfig(this, payload);
      },
      resetIndexSetQueryResult(payload?: Parameters<typeof stateOperations.resetIndexSetQueryResult>[1]): void {
        stateOperations.resetIndexSetQueryResult(this, payload);
      },
      updateIndexSetQueryResult(payload?: Parameters<typeof stateOperations.updateIndexSetQueryResult>[1]): void {
        stateOperations.updateIndexSetQueryResult(this, payload);
      },
      updateIndexItemParams(payload?: Parameters<typeof stateOperations.updateIndexItemParams>[1]): void {
        stateOperations.updateIndexItemParams(this, payload);
      },
      updateIndexSetFieldConfigList(
        payload?: Parameters<typeof stateOperations.updateIndexSetFieldConfigList>[1],
      ): void {
        stateOperations.updateIndexSetFieldConfigList(this, payload);
      },
      updataOperatorDictionary(payload?: Parameters<typeof stateOperations.updataOperatorDictionary>[1]): void {
        stateOperations.updataOperatorDictionary(this, payload);
      },
      updateSpace(spaceUid?: Parameters<typeof stateOperations.updateSpace>[1]): void {
        stateOperations.updateSpace(this, spaceUid);
      },
      updateMySpaceList(spaceList?: Parameters<typeof stateOperations.updateMySpaceList>[1]): void {
        stateOperations.updateMySpaceList(this, spaceList);
      },
      patchMySpaceListItem(payload?: Parameters<typeof stateOperations.patchMySpaceListItem>[1]): void {
        stateOperations.patchMySpaceListItem(this, payload);
      },
      updateUnionIndexList(unionIndexList?: Parameters<typeof stateOperations.updateUnionIndexList>[1]): void {
        stateOperations.updateUnionIndexList(this, unionIndexList);
      },
      updateGlobalsData(globalsData?: Parameters<typeof stateOperations.updateGlobalsData>[1]): void {
        stateOperations.updateGlobalsData(this, globalsData);
      },
      updateIframeQuery(iframeQuery?: Parameters<typeof stateOperations.updateIframeQuery>[1]): void {
        stateOperations.updateIframeQuery(this, iframeQuery);
      },
      updateShowFieldsConfigPopoverNum(
        showFieldsConfigPopoverNum?: Parameters<typeof stateOperations.updateShowFieldsConfigPopoverNum>[1],
      ): void {
        stateOperations.updateShowFieldsConfigPopoverNum(this, showFieldsConfigPopoverNum);
      },
      updateChartSize(): void {
        stateOperations.updateChartSize(this);
      },
      updateVisibleFields(val?: Parameters<typeof stateOperations.updateVisibleFields>[1]): void {
        stateOperations.updateVisibleFields(this, val);
      },
      updateVisibleFieldMinWidth(
        tableList?: Parameters<typeof stateOperations.updateVisibleFieldMinWidth>[1],
        fieldList?: Parameters<typeof stateOperations.updateVisibleFieldMinWidth>[2],
      ): void {
        stateOperations.updateVisibleFieldMinWidth(this, tableList, fieldList);
      },
      updateIndexFieldInfo(payload?: Parameters<typeof stateOperations.updateIndexFieldInfo>[1]): void {
        stateOperations.updateIndexFieldInfo(this, payload);
      },
      updateIndexFieldEggsItems(payload?: Parameters<typeof stateOperations.updateIndexFieldEggsItems>[1]): void {
        stateOperations.updateIndexFieldEggsItems(this, payload);
      },
      resetIndexFieldInfo(payload?: Parameters<typeof stateOperations.resetIndexFieldInfo>[1]): void {
        stateOperations.resetIndexFieldInfo(this, payload);
      },
      updateSqlQueryFieldList(payload?: Parameters<typeof stateOperations.updateSqlQueryFieldList>[1]): void {
        stateOperations.updateSqlQueryFieldList(this, payload);
      },
      updateNotTextTypeFields(payload?: Parameters<typeof stateOperations.updateNotTextTypeFields>[1]): void {
        stateOperations.updateNotTextTypeFields(this, payload);
      },
      updateTableLineIsWrap(payload?: Parameters<typeof stateOperations.updateTableLineIsWrap>[1]): void {
        stateOperations.updateTableLineIsWrap(this, payload);
      },
      updateState(payload?: Parameters<typeof stateOperations.updateState>[1]): void {
        stateOperations.updateState(this, payload);
      },
      updateIsSetDefaultTableColumn(
        payload?: Parameters<typeof stateOperations.updateIsSetDefaultTableColumn>[1],
      ): void {
        stateOperations.updateIsSetDefaultTableColumn(this, payload);
      },
      resetVisibleFields(payload?: Parameters<typeof stateOperations.resetVisibleFields>[1]): void {
        stateOperations.resetVisibleFields(this, payload);
      },
      resetIndexSetOperatorConfig(): void {
        stateOperations.resetIndexSetOperatorConfig(this);
      },
      updateClearSearchValueNum(payload?: Parameters<typeof stateOperations.updateClearSearchValueNum>[1]): void {
        stateOperations.updateClearSearchValueNum(this, payload);
      },
      initMonitorState(payload?: Parameters<typeof stateOperations.initMonitorState>[1]): void {
        stateOperations.initMonitorState(this, payload);
      },
      resetState(): void {
        stateOperations.resetState(this);
      },
      userInfo(
        params?: Parameters<typeof appQueries.userInfoAction>[1],
        config?: Parameters<typeof appQueries.userInfoAction>[2],
      ): Promise<Awaited<ReturnType<typeof appQueries.userInfoAction>>> {
        return Promise.resolve(appQueries.userInfoAction(this, params, config));
      },
      getMenuList(
        spaceUid?: Parameters<typeof appQueries.getMenuListAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.getMenuListAction>>> {
        return Promise.resolve(appQueries.getMenuListAction(this, spaceUid));
      },
      requestMenuList(
        spaceUid?: Parameters<typeof appQueries.requestMenuListAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.requestMenuListAction>>> {
        return Promise.resolve(appQueries.requestMenuListAction(this, spaceUid));
      },
      getGlobalsData(): Promise<Awaited<ReturnType<typeof appQueries.getGlobalsDataAction>>> {
        return Promise.resolve(appQueries.getGlobalsDataAction(this));
      },
      checkAllowed(
        paramData?: Parameters<typeof appQueries.checkAllowedAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.checkAllowedAction>>> {
        return Promise.resolve(appQueries.checkAllowedAction(this, paramData));
      },
      getApplyData(
        paramData?: Parameters<typeof appQueries.getApplyDataAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.getApplyDataAction>>> {
        return Promise.resolve(appQueries.getApplyDataAction(this, paramData));
      },
      checkAndGetData(
        paramData?: Parameters<typeof appQueries.checkAndGetDataAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.checkAndGetDataAction>>> {
        return Promise.resolve(appQueries.checkAndGetDataAction(this, paramData));
      },
      requestIndexSetFieldInfo(): Promise<Awaited<ReturnType<typeof retrieveQueries.requestIndexSetFieldInfoAction>>> {
        return Promise.resolve(retrieveQueries.requestIndexSetFieldInfoAction(this));
      },
      requestIndexSetQuery(
        payload?: RetrieveQueryPayload,
      ): Promise<Awaited<ReturnType<typeof retrieveQueries.requestIndexSetQueryAction>>> {
        return Promise.resolve(retrieveQueries.requestIndexSetQueryAction(this, payload));
      },
      requestIndexSetItemChanged(
        payload: Partial<ApplicationState['indexItem']> & { ids: (string | number)[] },
      ): Promise<unknown> {
        this.updateIndexItem(payload);
        this.resetIndexSetQueryResult({ search_count: 0, is_loading: true });
        if (!payload.isUnionIndex) this.updateState({ indexId: payload.ids[0] });
        return this.requestIndexSetFieldInfo();
      },
      requestIndexSetValueList(
        payload?: Parameters<typeof miscQueries.requestIndexSetValueListAction>[1],
      ): Promise<Awaited<ReturnType<typeof miscQueries.requestIndexSetValueListAction>>> {
        return Promise.resolve(miscQueries.requestIndexSetValueListAction(this, payload));
      },
      requestFavoriteList(
        payload?: Parameters<typeof appQueries.requestFavoriteListAction>[1],
      ): Promise<Awaited<ReturnType<typeof appQueries.requestFavoriteListAction>>> {
        return Promise.resolve(appQueries.requestFavoriteListAction(this, payload));
      },
      setQueryCondition(
        payload?: Parameters<typeof queryQueries.setQueryConditionAction>[1],
      ): Promise<Awaited<ReturnType<typeof queryQueries.setQueryConditionAction>>> {
        return Promise.resolve(queryQueries.setQueryConditionAction(this, payload));
      },
      changeShowUnionSource(): Promise<void> {
        this.updateIndexSetOperatorConfig({ isShowSourceField: !this.indexSetOperatorConfig.isShowSourceField });
        return Promise.resolve();
      },
      requestSearchTotal(): Promise<Awaited<ReturnType<typeof miscQueries.requestSearchTotalAction>>> {
        return Promise.resolve(miscQueries.requestSearchTotalAction(this));
      },
      handleTrendDataZoom(
        payload?: Parameters<typeof miscQueries.handleTrendDataZoomAction>[1],
      ): Promise<Awaited<ReturnType<typeof miscQueries.handleTrendDataZoomAction>>> {
        return Promise.resolve(miscQueries.handleTrendDataZoomAction(this, payload));
      },
      userFieldConfigChange(
        userConfig?: Parameters<typeof miscQueries.userFieldConfigChangeAction>[1],
      ): Promise<Awaited<ReturnType<typeof miscQueries.userFieldConfigChangeAction>>> {
        return Promise.resolve(miscQueries.userFieldConfigChangeAction(this, userConfig));
      },
    },
  });
}
export type NativeApplicationStore = ReturnType<ReturnType<typeof createNativeApplicationStore>>;
const stores = new WeakMap<Pinia, ReturnType<typeof createNativeApplicationStore>>();
export function useApplicationStore(pinia?: Pinia): NativeApplicationStore {
  pinia = resolveApplicationPinia(pinia);
  let store = stores.get(pinia);
  if (!store) {
    store = createNativeApplicationStore(pinia);
    stores.set(pinia, store);
  }
  return store(pinia);
}
