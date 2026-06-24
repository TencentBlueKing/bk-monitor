/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import axios from 'axios';

import http, { axiosInstance } from '@/api';
import {
  parseBigNumberList,
  readBlobRespToJson,
} from '@/common/util';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { retrieveRowCacheService, retrieveSearchWorkerIngestService, storageHealthService, storeCacheService } from '@/storage';
import { createRetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';

import { formatAdditionalFields, getCommonFilterAdditionWithValues, isSceneRetrieve } from '../helper.ts';
import { reportRouteLog } from '../modules/report-helper.ts';
import RequestPool from '../request-pool.ts';

let dateFieldSortList = [];
let currentRetrieveRowQueryKey = '';

const ingestSearchResponseOnMainThread = async (blob, {
  fieldNames,
  isPagination,
  rowQueryKey,
  startSeq,
}) => {
  const { code, data, result, message, permission } = await readBlobRespToJson(blob);
  const rsolvedData = data;
  if (result) {
    const renderList = rsolvedData.list;
    const originLogList = rsolvedData.origin_log_list;

    if (!Array.isArray(renderList) || !Array.isArray(originLogList)) {
      throw new Error('Invalid search response: list and origin_log_list are required');
    }

    if (renderList.length !== originLogList.length) {
      throw new Error('Invalid search response: list length ' + renderList.length + ' !== origin_log_list length ' + originLogList.length);
    }

    const renderMetas = originLogList.map((row, index) => createRetrieveRowRenderMeta(row, renderList[index]));
    const rowKeys = isPagination
      ? await retrieveRowCacheService.appendRows(rowQueryKey, originLogList, startSeq, { fieldNames, renderRows: renderList, renderMetas })
      : await retrieveRowCacheService.replaceRows(rowQueryKey, originLogList, { fieldNames, renderRows: renderList, renderMetas });
    delete rsolvedData.list;
    delete rsolvedData.origin_log_list;
    return {
      code,
      data: rsolvedData,
      length: originLogList.length,
      message,
      permission,
      result,
      rowKeys,
      size: originLogList.length,
      source: 'main-thread',
    };
  }

  return {
    code,
    data: rsolvedData,
    length: 0,
    message,
    permission,
    result,
    rowKeys: [],
    size: 0,
    source: 'main-thread',
  };
};

const ingestSearchResponse = async (blob, options) => {
  try {
    const workerResult = await retrieveSearchWorkerIngestService.ingestBlob(blob, {
      fieldNames: options.fieldNames,
      queryKey: options.rowQueryKey,
      startSeq: options.startSeq,
      writeMode: options.isPagination ? 'append' : 'replace',
    });
    return {
      ...workerResult,
      source: 'worker',
    };
  } catch (error) {
    console.warn('[retrieve-search] WebWorker ingest failed, fallback to main thread', error);
    storageHealthService.notifyWorkerFallback();
    return ingestSearchResponseOnMainThread(blob, options);
  }
};

const getProjectionFieldNames = (state) => {
  const fields = [
    ...(state.visibleFields || []),
    ...(state.indexFieldInfo?.fields || []).filter(field => field?.is_time_field || field?.field_name === state.indexFieldInfo?.time_field),
  ];

  return Array.from(new Set(fields.flatMap((field) => {
    if (!field) return [];
    return [field.field_name, field.alias_mapping_field?.field_name, ...(field.source_field_names || [])];
  }).filter(Boolean)));
};

export function requestIndexSetFieldInfoAction({ commit, state, getters }) {
  const { ids = [], start_time = '', end_time = '', isUnionIndex } = state.indexItem;
  commit('resetIndexFieldInfo');
  commit('updataOperatorDictionary', {});
  commit('updateNotTextTypeFields', {});
  commit('updateIndexSetFieldConfig', {});
  commit('updateVisibleFields', []);

  const cancelTokenKey = 'requestIndexSetFieldInfoCancelToken';
  RequestPool.execCanceToken(cancelTokenKey);
  const requestCancelToken = RequestPool.getCancelToken(cancelTokenKey);

  if (!ids.length) {
    return;
  }

  commit('resetIndexFieldInfo', { is_loading: true });
  const isScene = isSceneRetrieve(state);
  const urlStr = isScene
    ? 'retrieve/getSceneFields'
    : isUnionIndex
      ? 'unionSearch/unionMapping'
      : 'retrieve/getLogTableHead';
  !isUnionIndex && commit('deleteApiError', urlStr);
  const queryData = {
    start_time,
    end_time,
    is_realtime: 'True',
  };
  if (isScene) {
    const { space_uid, table_id_conditions, scene_filter_values } = getters.retrieveParams;
    Object.assign(queryData, { space_uid, table_id_conditions, scene_filter_values });
  } else if (isUnionIndex) {
    Object.assign(queryData, {
      index_set_ids: ids,
    });
  }

  dateFieldSortList = undefined;
  return http
    .request(
      urlStr,
      {
        params: isScene ? {} : { index_set_id: ids[0] },
        query: (!isScene && !isUnionIndex) ? queryData : undefined,
        data: (isScene || isUnionIndex) ? queryData : undefined,
      },
      isUnionIndex
        ? { cancelToken: requestCancelToken } : { catchIsShowMessage: false, cancelToken: requestCancelToken },
    )
    .then((res) => {
      const { default_sort_list: defaultSortListData = [], sort_list: sortListData = [] } = res.data ?? {};
      const defaultSortList = (
        ((defaultSortListData?.length ?? 0) > 0 ? defaultSortListData : sortListData) ?? []
      ).map(([fieldName]) => [fieldName, undefined]);

      res.data.fields.forEach((field) => {
        Object.assign(field, {
          has_repeat_alias_field: false,
          alias_mapping_field: null,
          is_virtual_alias_field: false,
        });
      });

      commit(
        'updateIndexFieldInfo',
        Object.assign({}, res.data ?? {}, {
          default_sort_list: defaultSortList,
        }),
      );
      commit('updataOperatorDictionary', res.data ?? {});
      commit('updateNotTextTypeFields', res.data ?? {});
      commit('updateIndexSetFieldConfig', res.data ?? {});
      commit('retrieve/updateFiledSettingConfigID', res.data?.config_id ?? -1);
      commit('retrieve/updateCatchFieldCustomConfig', res.data.user_custom_config);
      commit('resetVisibleFields');
      commit('resetIndexSetOperatorConfig');
      commit('updateIsSetDefaultTableColumn');
      storeCacheService.setApiCache(urlStr, `${ids.join(',')}:${start_time}:${end_time}`, res.data || {}).catch((error) => {
        console.warn('[store-cache] cache field info failed', error);
      });
      return res;
    })
    .catch((err) => {
      if (axios.isCancel(err)) return;
      !isUnionIndex && commit('updateApiError', { apiName: urlStr, errorMessage: err });
      commit('updateIndexFieldInfo', { is_loading: false });
    })
    .finally(() => {
      commit('updateIndexFieldInfo', { is_loading: false });
    });
}

export function requestIndexSetQueryAction(
  { commit, state, getters },
  payload = {
    isPagination: false,
    cancelToken: null,
    searchCount: undefined,
    defaultSortList: undefined,
    from: undefined,
  },
) {
  let cachedQueryResult = {
    row_keys: state.indexSetQueryResult.row_keys || [],
    row_query_key: state.indexSetQueryResult.row_query_key || '',
    cached_count: state.indexSetQueryResult.cached_count || 0,
    total: state.indexSetQueryResult.total || 0,
    took: state.indexSetQueryResult.took || 0,
    search_count: state.indexSetQueryResult.search_count || 0,
    is_error: state.indexSetQueryResult.is_error || false,
    exception_msg: state.indexSetQueryResult.exception_msg || '',
  };

  if (!payload?.isPagination) {
    commit('updateIndexSetQueryResult', {
      row_keys: [],
      row_query_key: '',
      cached_count: 0,
      total: 0,
    });
  }

  if (
    (!state.indexItem.isUnionIndex && !state.indexId)
    || (state.indexItem.isUnionIndex && !state.indexItem.ids.length)
  ) {
    state.searchTotal = 0;
    commit('updateSqlQueryFieldList', []);
    commit('updateIndexSetQueryResult', {
      is_error: false,
      exception_msg: '',
      total: 0,
    });
    return;
  }

  let begin = state.indexItem.begin;
  const { size, format, ...otherParams } = getters.retrieveParams;
  const requestAddition = getters.requestAddition;

  if (!payload?.isPagination) {
    if (payload?.defaultSortList) {
      dateFieldSortList = payload?.defaultSortList?.filter(([fieldName, sort]) => fieldName && sort);
    }

    const { datePickerValue } = state.indexItem;
    const letterRegex = /[a-zA-Z]/;
    const needTransform = datePickerValue.every(d => letterRegex.test(d));

    const [startTime, endTime] = needTransform
      ? handleTransformToTimestamp(datePickerValue, format)
      : [state.indexItem.start_time, state.indexItem.end_time];

    if (needTransform) {
      commit('updateIndexItem', { start_time: startTime, end_time: endTime });
    }
  }

  const searchCount = payload.searchCount ?? state.indexSetQueryResult.search_count + 1;
  commit(payload.isPagination ? 'updateIndexSetQueryResult' : 'resetIndexSetQueryResult', {
    is_loading: true,
    is_pagination_loading: !!payload?.isPagination,
    search_count: searchCount,
  });

  const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
  const cancelTokenKey = 'requestIndexSetQueryCancelToken';
  RequestPool.execCanceToken(cancelTokenKey);
  const requestCancelToken = payload.cancelToken ?? RequestPool.getCancelToken(cancelTokenKey);

  const searchUrl = isSceneRetrieve(state)
    ? '/search/scene/search/'
    : !state.indexItem.isUnionIndex
      ? `/search/index_set/${state.indexId}/search/`
      : '/search/index_set/union_search/';

  if (!payload?.isPagination) {
    const previousRowQueryKey = currentRetrieveRowQueryKey;
    currentRetrieveRowQueryKey = retrieveRowCacheService.createQueryKey({
      searchUrl,
      searchCount,
      indexId: state.indexId,
      ids: state.indexItem.ids,
      start_time: state.indexItem.start_time,
      end_time: state.indexItem.end_time,
      keyword: state.indexItem.keyword,
      addition: state.indexItem.addition,
    });
    if (previousRowQueryKey) {
      storageHealthService.clearActiveQuery(previousRowQueryKey);
      retrieveRowCacheService.releaseQuery(previousRowQueryKey);
      retrieveRowCacheService.clearQuery(previousRowQueryKey).catch((error) => {
        console.warn('[retrieve-search] clear previous query rows failed', error);
      });
    }
  }

  const { start_time, end_time } = state.indexItem;
  const baseData = {
    bk_biz_id: state.bkBizId,
    size,
    ...otherParams,
    start_time,
    end_time,
    addition: formatAdditionalFields(state, [...requestAddition, ...getCommonFilterAdditionWithValues(state)]),
  };

  const unionConfigs = state.unionIndexList.map(item => ({
    begin: payload?.isPagination
      ? (state.indexItem.catchUnionBeginList.find(cItem => String(cItem?.index_set_id) === item)?.begin ?? 0)
      : 0,
    index_set_id: item,
  }));

  const queryBegin = payload.isPagination ? (begin += size) : 0;
  const queryData = Object.assign(
    baseData,
    !state.indexItem.isUnionIndex
      ? {
        begin: queryBegin,
      }
      : {
        union_configs: unionConfigs,
      },
  );
  const params = {
    method: 'post',
    url: searchUrl,
    cancelToken: requestCancelToken,
    withCredentials: true,
    baseURL: baseUrl,
    responseType: 'blob',
    data: queryData,
  };
  if (state.isExternal) {
    params.headers = {
      'X-Bk-Space-Uid': state.spaceUid,
    };
  }

  const requestRowQueryKey = payload.isPagination
    ? (state.indexSetQueryResult.row_query_key || currentRetrieveRowQueryKey)
    : currentRetrieveRowQueryKey;
  const requestStartSeq = payload.isPagination ? (state.indexSetQueryResult.cached_count || 0) : 0;
  const requestCurrentRowKeys = payload.isPagination ? (state.indexSetQueryResult.row_keys || []) : [];
  let isStaleSearchResponse = false;
  const isCurrentSearchRequest = () => (payload.isPagination
    ? requestRowQueryKey === state.indexSetQueryResult.row_query_key
      && requestStartSeq === (state.indexSetQueryResult.cached_count || 0)
    : requestRowQueryKey === currentRetrieveRowQueryKey);

  return axiosInstance(params)
    .then(async (resp) => {
      if (resp.data && !resp.message) {
        const projectionFieldNames = getProjectionFieldNames(state);
        const rowQueryKey = requestRowQueryKey;
        const startSeq = requestStartSeq;
        const currentRowKeys = requestCurrentRowKeys;
        const {
          code,
          data,
          result,
          message,
          permission,
          rowKeys,
          size,
          source,
        } = await ingestSearchResponse(resp.data, {
          fieldNames: projectionFieldNames,
          isPagination: payload.isPagination,
          rowQueryKey,
          startSeq,
        });
        const rsolvedData = data;

        if (!isCurrentSearchRequest()) {
          isStaleSearchResponse = true;
          if (!payload.isPagination || rowQueryKey !== state.indexSetQueryResult.row_query_key) {
            retrieveRowCacheService.clearQuery(rowQueryKey).catch((error) => {
              console.warn('[retrieve-search] clear stale query rows failed', error);
            });
          }
          return { result: false, ignored: true };
        }

        if (result) {
          rsolvedData.total = rsolvedData.total?.toNumber ? rsolvedData.total.toNumber() : Number(rsolvedData.total || 0);
          rsolvedData.row_keys = Object.freeze(currentRowKeys.concat(rowKeys));
          rsolvedData.row_query_key = rowQueryKey;
          rsolvedData.cached_count = rsolvedData.row_keys.length;
          rsolvedData.ingest_source = source;
          storageHealthService.markActiveQuery(rowQueryKey);

          const catchUnionBeginList = parseBigNumberList(rsolvedData?.union_configs || []);
          state.tookTime = payload.isPagination
            ? state.tookTime + Number(rsolvedData?.took || 0)
            : Number(rsolvedData?.took || 0);

          if (!payload?.isPagination) {
            const layoutRows = await retrieveRowCacheService.getRows(rowKeys.slice(0, Math.min(rowKeys.length, 10)));
            commit('updateIsSetDefaultTableColumn', { list: layoutRows });
          }
          commit('updateSqlQueryFieldList', []);
          commit('updateIndexItem', {
            catchUnionBeginList,
            begin: payload.isPagination ? begin : 0,
          });
          commit('updateIndexSetQueryResult', rsolvedData);
          storeCacheService.setApiCache('retrieve/search-result-meta', rowQueryKey, {
            ...rsolvedData,
            row_keys: rsolvedData.row_keys,
            row_query_key: rowQueryKey,
            cached_count: rsolvedData.cached_count,
          }).catch((error) => {
            console.warn('[store-cache] cache search meta failed', error);
          });
          retrieveRowCacheService.gc({
            excludeQueryKeys: Array.from(new Set([rowQueryKey, ...storageHealthService.getActiveQueryKeys()])),
          }).catch((error) => {
            console.warn('[retrieve-search] gc rows failed', error);
          });

          return {
            data: rsolvedData,
            message,
            code,
            result,
            length: size,
            size,
          };
        }

        if (code === '9900403') {
          commit('updateState', {
            authDialogData: {
              apply_url: data.apply_url,
              apply_data: permission,
            },
          });
        }

        commit('updateIndexSetQueryResult', {
          exception_msg: message,
          is_error: !result,
          total: 0,
        });

        return {
          data,
          message,
          code,
          result,
          length: 0,
          size: 0,
        };
      }

      return { result: false };
    })
    .catch((e) => {
      if (!isCurrentSearchRequest()) {
        isStaleSearchResponse = true;
        return;
      }

      state.searchTotal = 0;
      retrieveRowCacheService.clearMemory();
      commit('updateSqlQueryFieldList', []);
      if (e.code !== 'ERR_CANCELED') {
        commit('updateIndexSetQueryResult', {
          is_error: true,
          exception_msg: e?.message ?? e?.toString(),
          total: 0,
        });
      }

      if (e.code === 'ERR_CANCELED') {
        cachedQueryResult.is_loading = false;
        cachedQueryResult.is_pagination_loading = false;
        commit('updateIndexSetQueryResult', cachedQueryResult);
      }
    })
    .finally(() => {
      if (!isStaleSearchResponse && isCurrentSearchRequest()) {
        commit('updateIndexSetQueryResult', {
          is_loading: false,
          is_pagination_loading: false,
        });
      }
      cachedQueryResult = null;

      if (isStaleSearchResponse) return;

      if (payload?.from !== 'auto_refresh') {
        const result = {
          is_error: state.indexSetQueryResult.is_error,
          exception_msg: state.indexSetQueryResult.exception_msg,
          first_page: queryData.begin === 0 ? 1 : 0,
          action: 'request',
          trigger_source: 'retrieve_query',
        };

        reportRouteLog(
          {
            ...result,
          },
          state,
        );
      }
    });
}
