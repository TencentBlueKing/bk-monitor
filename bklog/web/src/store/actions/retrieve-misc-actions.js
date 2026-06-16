/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import axios from 'axios';
import { set } from 'vue';

import http from '@/api';
import { formatDate } from '@/common/util';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { storeCacheService } from '@/storage';

import { formatAdditionalFields, getCommonFilterAdditionWithValues, isSceneRetrieve } from '../helper.ts';
import RequestPool from '../request-pool.ts';
import { storeRuntimeCacheService } from '../services/runtime-cache.service.js';

const cacheApi = (name, scope, data, meta = {}) => {
  storeCacheService.setApiCache(name, scope || 'default', data, meta).catch((error) => {
    console.warn('[store-cache] cache api failed', name, error);
  });
};

export function requestIndexSetValueListAction({ commit, state, getters }, payload) {
  const { start_time: startTime, end_time: endTime } = state.indexItem;
  const lastQueryTimerange = `${startTime}_${endTime}`;

  const cancelTokenKey = 'requestIndexSetValueListCancelToken';
  RequestPool.execCanceToken(cancelTokenKey);
  const requestCancelToken = payload.cancelToken ? RequestPool.getCancelToken(cancelTokenKey) : null;

  if (state.indexFieldInfo.last_eggs_request_token !== lastQueryTimerange) {
    storeRuntimeCacheService.clearFieldAggsItems(state.indexId || 'default');
    state.fieldAggsItemsVersion += 1;
  }

  if (payload.force) {
    const emptyAggsItems = {};
    (payload?.fields ?? []).forEach((field) => {
      emptyAggsItems[field.field_name] = [];
    });
    storeRuntimeCacheService.patchFieldAggsItems(state.indexId || 'default', emptyAggsItems);
    state.fieldAggsItemsVersion += 1;
  }

  const isDefaultQuery = !(payload?.fields?.length ?? false);
  const filterBuildIn = field => (isDefaultQuery ? !field.is_built_in : true);

  const cachedAggsItems = storeRuntimeCacheService.getFieldAggsItems(state.indexId || 'default');
  const filterFn = field => !cachedAggsItems[field.field_name]?.length
    && field.es_doc_values
    && filterBuildIn(field)
    && ['keyword'].includes(field.field_type)
    && !/^__dist_/.test(field.field_name);

  const fields = (payload?.fields?.length ? payload.fields : state.indexFieldInfo.fields)
    .filter(filterFn)
    .map(field => field.field_name);

  if (!fields.length) return Promise.resolve(true);

  const isScene = isSceneRetrieve(state);
  let urlStr;
  if (isScene) {
    urlStr = 'retrieve/getSceneAggsTerms';
  } else if (state.indexItem.isUnionIndex) {
    urlStr = 'unionSearch/unionTerms';
  } else {
    urlStr = 'retrieve/getAggsTerms';
  }

  const baseQueryData = {
    keyword: '*',
    addition: formatAdditionalFields(state, payload?.addition ?? []),
    start_time: formatDate(startTime),
    end_time: formatDate(endTime),
    size: payload?.size ?? 100,
    bk_biz_id: state.bkBizId,
  };

  let queryData;
  if (isScene) {
    const { space_uid, table_id_conditions, scene_filter_values } = getters.retrieveParams;
    queryData = {
      ...baseQueryData,
      space_uid,
      table_id_conditions,
      scene_filter_values,
      fields,
    };
  } else {
    queryData = {
      ...baseQueryData,
      fields,
      ...(state.indexItem.isUnionIndex && { index_set_ids: state.unionIndexList }),
    };
  }

  const body = isScene
    ? { data: queryData }
    : { params: { index_set_id: state.indexId }, data: queryData };

  return http
    .request(urlStr, body, {
      cancelToken: requestCancelToken,
    })
    .then((resp) => {
      if (payload?.commit !== false) {
        commit('updateIndexFieldEggsItems', resp.data.aggs_items ?? {});
      }
      cacheApi(urlStr, `${state.indexId}:${lastQueryTimerange}:${fields.join(',')}`, resp.data || {});
      return resp;
    });
}

export function requestSearchTotalAction({ state, getters }) {
  state.searchTotal = 0;
  const startTime = Math.floor(getters.retrieveParams.start_time);
  const endTime = Math.ceil(getters.retrieveParams.end_time);
  const isScene = isSceneRetrieve(state);
  const urlStr = isScene ? 'retrieve/getSceneFieldStatisticsTotal' : 'retrieve/fieldStatisticsTotal';

  const cancelTokenKey = 'requestSearchTotalCancelToken';
  RequestPool.execCanceToken(cancelTokenKey);
  const requestCancelToken = RequestPool.getCancelToken(cancelTokenKey);

  const data = {
    ...getters.retrieveParams,
    bk_biz_id: state.bkBizId,
    ...(isScene ? {} : { index_set_ids: state.indexItem.ids }),
    start_time: startTime,
    end_time: endTime,
    addition: formatAdditionalFields(state, [
      ...getters.requestAddition,
      ...getCommonFilterAdditionWithValues(state),
    ]),
  };

  return http
    .request(
      urlStr,
      { data },
      {
        catchIsShowMessage: false,
        cancelToken: requestCancelToken,
      },
    )
    .then((res) => {
      const { data } = res;
      if (res.result === true) state.searchTotal = data.total_count ?? data.total;
      cacheApi(urlStr, `${state.indexId}:${startTime}:${endTime}`, data || {});
      return res;
    })
    .catch((err) => {
      if (axios.isCancel(err)) return;
      console.error(err);
      return Promise.reject(err);
    });
}

export function handleTrendDataZoomAction({ commit, getters }, payload) {
  const { start_time: startTime, end_time: endTime, format } = payload;
  const formatStr = getters.retrieveParams.format;

  const [startTimeStamp, endTimeStamp] = format
    ? handleTransformToTimestamp([startTime, endTime], formatStr)
    : [startTime, endTime];

  commit('updateIndexItem', {
    start_time: startTimeStamp,
    end_time: endTimeStamp,
    datePickerValue: [startTime, endTime],
  });

  return Promise.resolve(true);
}

export function userFieldConfigChangeAction({ state, getters, commit }, userConfig) {
  const indexSetConfig = {
    ...state.retrieve.catchFieldCustomConfig,
    ...userConfig,
  };
  delete indexSetConfig.isUpdate;

  let requestName;
  let queryParams;
  if (getters.isSceneMode) {
    requestName = 'retrieve/sceneFieldsConfig';
    queryParams = {
      bk_biz_id: state.bkBizId,
      scene_id: state.indexItem.scene_active,
      scene_config: indexSetConfig,
    };
  } else {
    requestName = 'retrieve/updateUserFiledTableConfig';
    queryParams = {
      index_set_id: state.indexId,
      index_set_type: getters.isUnionSearch ? 'union' : 'single',
      index_set_config: indexSetConfig,
    };
    if (getters.isUnionSearch) {
      delete queryParams.index_set_id;
      queryParams.index_set_ids = state.unionIndexList;
    }
  }

  return http
    .request(requestName, { data: queryParams })
    .then((res) => {
      if (res.code === 0 && !userConfig.isUpdate) {
        const updatedUserConfig = getters.isSceneMode ? res.data : res.data.index_set_config;
        commit('retrieve/updateCatchFieldCustomConfig', updatedUserConfig);
        cacheApi(requestName, `${state.indexId || state.indexItem.scene_active}:field-config`, updatedUserConfig || {});
      }
      return res;
    })
    .catch(err => Promise.reject(err));
}
