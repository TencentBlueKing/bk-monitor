/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import Vue, { set } from 'vue';

import { setDefaultTableWidth } from '@/common/util';
import { retrieveFieldAliasCacheService, retrieveFieldCacheService, storeCacheService } from '@/storage';
import * as pinyin from 'tiny-pinyin';
import * as patcher56L from 'tiny-pinyin/dist/patchers/56l.js';

import { ConditionOperator } from '../condition-operator.ts';
import {
  BkLogGlobalStorageKey,
  IndexFieldInfo,
  IndexItem,
  IndexSetQueryResult,
  getDefaultRetrieveParams,
} from '../default-values.ts';
import { isAiAssistantActive } from '../helper.ts';
import { createStoreState } from '../state.js';
import {
  createIndexSetFieldConfig,
  createIndexSetOperatorConfig,
  createNotTextTypeFields,
  createOperatorDictionary,
  createRetrieveDropdownData,
  normalizeIndexFieldInfo,
  resolveVisibleFields,
} from '../services/field-metadata.service.js';
import { storeRuntimeCacheService } from '../services/runtime-cache.service.js';

if (pinyin.isSupported() && patcher56L.shouldPatch(pinyin.genToken)) {
  pinyin.patchDict(patcher56L);
}

const SET_APP_STATE = 'SET_APP_STATE';

const mutations = {

    [SET_APP_STATE](state, data) {
      for (const [key, value] of Object.entries(data)) {
        state[key] = value;
      }
    },

    updateAiMode(state, payload) {
      Object.keys(payload).forEach((key) => {
        set(state.aiMode, key, payload[key]);
      });
    },

    updateStorage(state, payload) {
      Object.keys(payload).forEach((key) => {
        set(state.storage, key, payload[key]);
      });
      localStorage.setItem(BkLogGlobalStorageKey, JSON.stringify(state.storage));
      storeCacheService.setLocalStorageMirror(BkLogGlobalStorageKey, state.storage).catch((error) => {
        console.warn('[store-cache] mirror global storage failed', error);
      });
    },

    updateApiError(state, { apiName, errorMessage }) {
      Vue.set(state.apiErrorInfo, apiName, errorMessage);
      storeCacheService.setApiCache('store/api-error-info', 'default', state.apiErrorInfo).catch((error) => {
        console.warn('[store-cache] cache api error info failed', error);
      });
    },
    deleteApiError(state, apiName) {
      Vue.delete(state.apiErrorInfo, apiName);
      storeCacheService.setApiCache('store/api-error-info', 'default', state.apiErrorInfo).catch((error) => {
        console.warn('[store-cache] cache api error info failed', error);
      });
    },
    updateFavoriteList(state, payload) {
      state.favoriteList.length = 0;
      state.favoriteList = [];
      state.favoriteList.push(...(payload ?? []));
      storeCacheService.setApiCache('store/favorite-list', state.spaceUid || 'default', state.favoriteList).catch((error) => {
        console.warn('[store-cache] cache favorite list failed', error);
      });
    },
    updateChartParams(state, params) {
      Object.keys(params).forEach((key) => {
        if (Array.isArray(state.indexItem.chart_params[key])) {
          state.indexItem.chart_params[key].splice(0, state.indexItem.chart_params[key].length, ...(params[key] ?? []));
        } else {
          set(state.indexItem.chart_params, key, params[key]);
        }
      });
    },
    updateIndexItem(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        if (['ids', 'items', 'catchUnionBeginList'].includes(key)) {
          if (Array.isArray(state.indexItem[key]) && Array.isArray(payload?.[key] ?? false)) {
            state.indexItem[key].splice(
              0,
              state.indexItem[key].length,
              ...(payload?.[key] ?? []).filter(v => v !== '' && v !== null && v !== undefined),
            );
          } else {
            if (Object.prototype.hasOwnProperty.call(state.indexItem, key)) {
              set(state.indexItem, key, payload[key]);
            }
          }
        } else {
          if (Object.prototype.hasOwnProperty.call(state.indexItem, key)) {
            set(state.indexItem, key, payload[key]);
          }
        }
      });
    },

    updateIndexSetOperatorConfig(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        set(state.indexSetOperatorConfig, key, payload[key]);
      });
      storeCacheService.setApiCache('store/index-set-operator-config', state.indexId || 'default', state.indexSetOperatorConfig).catch((error) => {
        console.warn('[store-cache] cache operator config failed', error);
      });
    },

    /**
     * 当切换索引集时，重置请求参数默认值
     * @param {*} state
     * @param {*} payload
     */
    resetIndexsetItemParams(state, payload) {
      /** 当前选中的时间范围 */
      const currentDatePickerValue = state.indexItem.datePickerValue;

      const defaultValue = {
        ...getDefaultRetrieveParams(),
        isUnionIndex: false,
        selectIsUnionSearch: false,
      };
      ['ids', 'items', 'catchUnionBeginList'].forEach((key) => {
        if (Array.isArray(state.indexItem[key])) {
          state.indexItem[key].splice(
            0,
            state.indexItem[key].length,
            ...(payload?.[key] ?? []).filter(v => v !== null && v !== undefined),
          );
        }
      });
      defaultValue.datePickerValue = currentDatePickerValue;

      state.indexItem.isUnionIndex = false;
      state.unionIndexList.splice(0, state.unionIndexList.length);
      state.indexItem.chart_params = structuredClone(IndexItem.chart_params);

      if (payload?.addition && payload.addition.length >= 0) {
        state.indexItem.addition.splice(
          0,
          state.indexItem.addition.length,
          ...payload.addition.map((item) => {
            const instance = new ConditionOperator(item);
            return { ...item, ...instance.getRequestParam() };
          }),
        );
      }

      const copyValue = Object.keys(payload ?? {}).reduce((result, key) => {
        if (!['ids', 'items', 'catchUnionBeginList', 'addition'].includes(key)) {
          Object.assign(result, { [key]: payload[key] });
        }

        return result;
      }, {});
      Object.assign(state.indexItem, defaultValue, copyValue);
    },

    updateIndexSetFieldConfig(state, payload) {
      const nextConfig = createIndexSetFieldConfig(payload);
      Object.keys(state.indexSetFieldConfig).forEach((key) => {
        Vue.delete(state.indexSetFieldConfig, key);
      });
      Object.keys(nextConfig).forEach((key) => {
        set(state.indexSetFieldConfig, key, nextConfig[key]);
      });
      storeCacheService.setApiCache('store/index-set-field-config', state.indexId || 'default', state.indexSetFieldConfig).catch((error) => {
        console.warn('[store-cache] cache field config failed', error);
      });
    },

    updateIndexSetCustomConfig(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        set(state.indexFieldInfo.custom_config, key, payload[key]);
      });
    },

    resetIndexSetQueryResult(state, payload) {
      Object.keys(IndexSetQueryResult).forEach((key) => {
        const value = payload && Object.prototype.hasOwnProperty.call(payload, key)
          ? payload[key]
          : IndexSetQueryResult[key];

        if (Array.isArray(value)) {
          set(state.indexSetQueryResult, key, [...value]);
        } else if (value && typeof value === 'object') {
          set(state.indexSetQueryResult, key, { ...value });
        } else {
          set(state.indexSetQueryResult, key, value);
        }
      });
    },

    updateIndexSetQueryResult(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        if (Array.isArray(payload[key]) && Array.isArray(state.indexSetQueryResult[key])) {
          if (Object.isFrozen(state.indexSetQueryResult[key])) {
            state.indexSetQueryResult[key] = undefined;
            set(state.indexSetQueryResult, key, payload[key]);
          } else {
            state.indexSetQueryResult[key].length = 0;
            state.indexSetQueryResult[key] = [];
            state.indexSetQueryResult[key].push(...(payload[key] ?? []).filter(v => v !== null && v !== undefined));
          }
        } else {
          set(state.indexSetQueryResult, key, payload[key]);
        }
      });
      if (['row_keys', 'row_query_key', 'cached_count', 'total', 'took', 'fields', 'aggs', 'aggregations'].some(key => key in (payload ?? {}))) {
        storeCacheService.setApiCache(
          'store/index-set-query-result',
          state.indexSetQueryResult.row_query_key || state.indexId || 'default',
          state.indexSetQueryResult,
        ).catch((error) => {
          console.warn('[store-cache] cache query result failed', error);
        });
      }
    },

    updateIndexItemParams(state, payload) {
      if (payload?.addition && payload.addition.length >= 0) {
        state.indexItem.addition.splice(
          0,
          state.indexItem.addition.length,
          ...payload.addition.map((item) => {
            const instance = new ConditionOperator(item);
            return { ...item, ...instance.getRequestParam() };
          }),
        );
      }

      const copyValue = Object.keys(payload ?? {}).reduce((result, key) => {
        if (!['addition'].includes(key)) {
          Object.assign(result, { [key]: payload[key] });
        }

        return result;
      }, {});

      Object.assign(state.indexItem, copyValue ?? {});
    },

    updateIndexSetFieldConfigList(state, payload) {
      if (payload.is_loading !== undefined) {
        state.indexSetFieldConfigList.is_loading = payload.is_loading;
      }

      if (payload.data) {
        state.indexSetFieldConfigList.data.length = 0;
        state.indexSetFieldConfigList.data.push(...(payload ?? []));
      }
    },

    updataOperatorDictionary(state, payload) {
      const dictionary = createOperatorDictionary(payload);
      storeRuntimeCacheService.setOperatorDictionary(state.indexId || 'default', dictionary);
      state.operatorDictionaryVersion += 1;
    },

    updateSpace(state, spaceUid) {
      if (typeof spaceUid === 'string') {
        state.space = state.mySpaceList.find(item => item.space_uid === spaceUid) || {};
      }

      if (typeof spaceUid === 'object') {
        state.space = spaceUid;
      }

      state.bkBizId = state.space?.bk_biz_id;
      state.spaceUid = state.space?.space_uid;
      state.isSetDefaultTableColumn = false;
      state.features.isAiAssistantActive = isAiAssistantActive([state.bkBizId, state.spaceUid]);
    },
    updateMySpaceList(state, spaceList) {
      state.mySpaceList = spaceList.map((item) => {
        const defaultTag = {
          id: item.space_type_id,
          name: item.space_type_name,
          type: item.space_type_id,
        };
        return {
          ...item,
          name: item.space_name.replace(/\[.*?\]/, ''),
          py_text: pinyin.convertToPinyin(item.space_name, true).replace(/true/g, ''),
          tags:
            item.space_type_id === 'bkci' && item.space_code
              ? [
                defaultTag,
                {
                  id: 'bcs',
                  name: window.mainComponent.$t('容器项目'),
                  type: 'bcs',
                },
              ]
              : [defaultTag],
        };
      });

      const demoId = String(window.DEMO_BIZ_ID);
      const demoProject = spaceList.find(item => `${item.bk_biz_id}` === demoId);
      state.demoUid = demoProject ? demoProject.space_uid : '';
    },
    updateUnionIndexList(state, unionIndexList) {
      const updateIndexItem = unionIndexList.updateIndexItem ?? true;
      const list = Array.isArray(unionIndexList) ? unionIndexList : unionIndexList.list;

      state.unionIndexList.splice(0, state.unionIndexList.length, ...list.filter(v => v !== null && v !== undefined));

      if (updateIndexItem) {
        state.indexItem.ids.splice(0, state.indexItem.ids.length, ...list.filter(v => v !== null && v !== undefined));
      }

      const unionIndexItemList = state.retrieve.flatIndexSetList.filter(item => list.includes(item.index_set_id));
      state.unionIndexItemList.splice(0, state.unionIndexItemList.length, ...unionIndexItemList);
    },
    updateGlobalsData(state, globalsData) {
      state.globalsData = globalsData;
      Vue.set(state, 'globalsData', globalsData);
      storeCacheService.setApiCache('store/globals-data', 'default', globalsData || {}).catch((error) => {
        console.warn('[store-cache] cache globals data failed', error);
      });
    },
    updateIframeQuery(state, iframeQuery) {
      Object.assign(state.iframeQuery, iframeQuery);
    },
    updateShowFieldsConfigPopoverNum(state, showFieldsConfigPopoverNum) {
      state.showFieldsConfigPopoverNum += showFieldsConfigPopoverNum;
    },
    updateChartSize(state) {
      state.chartSizeNum += 1;
    },
    updateVisibleFields(state, val) {
      state.visibleFields.splice(0, state.visibleFields.length, ...(val ?? []));
    },
    updateVisibleFieldMinWidth(state, tableList, fieldList) {
      const staticWidth = state.indexSetOperatorConfig?.bcsWebConsole?.is_active ? 84 : 58 + 50;
      setDefaultTableWidth(fieldList ?? state.visibleFields, tableList, null, staticWidth);
    },
    updateIndexFieldInfo(state, payload) {
      const hasFieldPayload = !!payload?.fields;
      const fieldScope = payload?.field_scope || state.indexFieldInfo.field_scope || state.indexId || 'default';
      if (hasFieldPayload) {
        retrieveFieldCacheService.setMeta(fieldScope, payload);
        // 独立别名配置：失败不得阻断字段信息主流程
        try {
          retrieveFieldAliasCacheService.setAliasConfig(fieldScope, payload);
        } catch (error) {
          console.warn('[retrieve-field-alias-cache] set alias config failed', error);
        }
      }
      const processedData = normalizeIndexFieldInfo(payload);
      const { fieldNameIndex, queryAliasIndex, aggs_items: aggsItems, ...stateData } = processedData ?? {};
      ['fields', 'raw_fields', 'raw_field_list', 'alias_field_list', 'field_tree', 'fieldNameIndex', 'queryAliasIndex', 'widthHints'].forEach((key) => {
        delete stateData[key];
      });
      if (fieldNameIndex || queryAliasIndex) {
        storeRuntimeCacheService.setFieldIndexes(fieldScope, { fieldNameIndex, queryAliasIndex });
        // 轻量 Vuex fallback，供展示 resolver 使用；不参与业务字段配置主链路
        set(state.indexFieldInfo, 'fieldNameIndex', fieldNameIndex ?? {});
        set(state.indexFieldInfo, 'queryAliasIndex', queryAliasIndex ?? {});
      }
      if (aggsItems) {
        storeRuntimeCacheService.setFieldAggsItems(fieldScope, aggsItems);
        state.fieldAggsItemsVersion += 1;
      }
      Object.keys(stateData ?? {}).forEach((key) => {
        set(state.indexFieldInfo, key, stateData[key]);
      });
      if (hasFieldPayload || payload?.field_scope) {
        set(state.indexFieldInfo, 'field_scope', fieldScope);
        state.fieldMetaVersion += 1;
        set(state.indexFieldInfo, 'field_meta_version', state.fieldMetaVersion);
      }
      storeCacheService.setApiCache('store/index-field-info', fieldScope, state.indexFieldInfo).catch((error) => {
        console.warn('[store-cache] cache index field info failed', error);
      });
    },
    updateIndexFieldEggsItems(state, payload) {
      const { start_time: startTime, end_time: endTime } = state.indexItem;
      const lastQueryTimerange = String(startTime) + '_' + String(endTime);
      storeRuntimeCacheService.patchFieldAggsItems(state.indexId || 'default', payload ?? {});
      state.fieldAggsItemsVersion += 1;
      state.indexFieldInfo.last_eggs_request_token = lastQueryTimerange;
    },
    resetIndexFieldInfo(state, payload) {
      const defValue = { ...IndexFieldInfo };
      const { aggs_items: aggsItems, fieldNameIndex, queryAliasIndex, ...stateData } = payload ?? {};
      if (payload === undefined || aggsItems) {
        storeRuntimeCacheService.setFieldAggsItems(state.indexId || 'default', aggsItems ?? {});
        state.fieldAggsItemsVersion += 1;
      }
      if (fieldNameIndex || queryAliasIndex || payload === undefined) {
        storeRuntimeCacheService.setFieldIndexes(state.indexFieldInfo.field_scope || state.indexId || 'default', {
          fieldNameIndex: fieldNameIndex ?? {},
          queryAliasIndex: queryAliasIndex ?? {},
        });
      }
      state.indexFieldInfo = Object.assign(defValue, stateData);
    },
    updateSqlQueryFieldList(state, payload) {
      const dropdownData = createRetrieveDropdownData(payload ?? [], state.notTextTypeFields);
      storeRuntimeCacheService.setRetrieveDropdownData(state.indexId || 'default', dropdownData);
      state.retrieveDropdownDataVersion += 1;
    },
    updateNotTextTypeFields(state, payload) {
      state.notTextTypeFields.splice(0, state.notTextTypeFields.length, ...createNotTextTypeFields(payload));
    },
    updateTableLineIsWrap(state, payload) {
      state.storage.tableLineIsWrap = payload;
    },
    updateState(state, payload) {
      if (typeof payload === 'object') {
        Object.keys(payload).forEach((key) => {
          if (state[key] !== undefined) {
            const value = payload[key];
            const currentValue = state[key];
            if (Array.isArray(currentValue) && Array.isArray(value)) {
              state[key].length = 0;
              state[key] = value;
            } else {
              set(state, key, value);
            }
          }
        });
      } else {
        console.error('Payload should be a non-null object');
      }
    },
    /** 初始化表格宽度 为false的时候会按照初始化的情况来更新宽度 */
    updateIsSetDefaultTableColumn(state, payload) {
      // 如果浏览器记录过当前索引集表格拖动过 则不需要重新计算
      if (!state.isSetDefaultTableColumn) {
        const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
        const catchFieldsWidthObj = {
          ...retrieveFieldCacheService.getUserWidthConfig(fieldScope),
          ...(state.retrieve.catchFieldCustomConfig.fieldsWidth ?? {}),
        };
        const staticWidth = state.indexSetOperatorConfig?.bcsWebConsole?.is_active ? 104 : 84;
        const widthSnapshot = setDefaultTableWidth(
          state.visibleFields,
          payload?.list ?? [],
          catchFieldsWidthObj,
          staticWidth + 60,
        );
        retrieveFieldCacheService.setComputedWidths(fieldScope, state.visibleFields);
        if (Object.keys(widthSnapshot).length) {
          state.fieldWidthVersion += 1;
        }
      }
      if (typeof payload === 'boolean') state.isSetDefaultTableColumn = payload;
    },
    /**
     * @desc: 用于更新可见field
     * 根据传入的 `payload` 参数更新当前可见的字段。`payload` 可以是一个字段名称的数组，
     * 或者是包含字段名称数组和版本信息的对象。
     *
     * @param {Array | Object} payload  - 可传入字段名称数组或包含字段数组以及版本信息的对象。
     *   - 当为数组时，表示字段名称列表。
     *   - 当为对象时，应包含以下属性：
     *     - {Array} displayFieldNames - 字段名称数组。
     *     - {string} version - 版本信息，包含 v2时，表示是新版本设计，目前包含了object字段层级展示的添加功能，后续如果需要区别于之前的逻辑处理，可以参照此逻辑处理(暂不生效)
     *
     */
    resetVisibleFields(state, payload) {
      const visibleFields = resolveVisibleFields({
        payload,
        catchDisplayFields: state.retrieve.catchFieldCustomConfig.displayFields,
        defaultDisplayFields: state.indexFieldInfo.display_fields,
        fieldScope: state.indexFieldInfo.field_scope || state.indexId || 'default',
      });
      state.visibleFields.splice(0, state.visibleFields.length, ...visibleFields);
      set(state, 'isNotVisibleFieldsShow', !visibleFields.length);
    },
    resetIndexSetOperatorConfig(state) {
      const nextConfig = createIndexSetOperatorConfig({
        indexSetFieldConfig: state.indexSetFieldConfig,
        indexItem: state.indexItem,
      });
      Object.keys(nextConfig).forEach((key) => {
        set(state.indexSetOperatorConfig, key, nextConfig[key]);
      });
      storeCacheService.setApiCache('store/index-set-operator-config', state.indexId || 'default', state.indexSetOperatorConfig).catch((error) => {
        console.warn('[store-cache] cache operator config failed', error);
      });
    },
    updateClearSearchValueNum(state, payload) {
      state.clearSearchValueNum = payload;
    },
    // 初始化监控默认数据
    initMonitorState(state, payload) {
      Object.assign(state, payload);
    },
    resetState(state) {
      Object.assign(state, createStoreState());
    },
};

export default mutations;
