/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import axios from 'axios';

import http from '@/api';
import { parseBigNumberList } from '@/common/util';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import {
  retrieveFieldCacheService,
  retrieveRowCacheService,
  retrieveSearchWorkerService,
  storageHealthService,
  storeCacheService,
} from '@/storage';
// import { logRetrieveSearchIngest } from '@/storage/utils/retrieve-search-ingest.logger';
import { normalizeRetrieveFields } from '@/storage/utils/retrieve-field-meta';
import { normalizeSearchTotal } from '@/storage/utils/normalize-search-total';

import { formatAdditionalFields, getCommonFilterAdditionWithValues, isSceneRetrieve } from '../helper.ts';
import { reportRouteLog } from '../modules/report-helper.ts';
import RequestPool from '../request-pool.ts';

let dateFieldSortList = [];
let currentRetrieveRowQueryKey = '';

const getCookie = name => {
  const matched = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return matched ? decodeURIComponent(matched[1]) : '';
};

const buildSearchRequestHeaders = state => {
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  };
  const csrfToken = getCookie('bklog_csrftoken');
  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }
  if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL) && state.spaceUid) {
    headers['X-Bk-Space-Uid'] = state.spaceUid;
  }
  if (state.indexItem?.timezone) {
    headers['X-BKLOG-TIMEZONE'] = state.indexItem.timezone;
  }
  return headers;
};

const isSearchRequestCanceled = error =>
  error?.code === 'ERR_CANCELED'
  || error?.name === 'AbortError'
  || error?.message === 'Search request canceled';

// 乐观更新：仅在拿到有效正数时更新总数（meta 阶段 / 分页），不会把已知总数清零
const applyOptimisticTotal = (state, total) => {
  const normalizedTotal = normalizeSearchTotal(total);
  if (normalizedTotal > 0) {
    state.searchTotal = normalizedTotal;
  }
  return normalizedTotal;
};

// 权威更新：非分页检索的最终结果，如实反映（包含 0 结果）
const applyAuthoritativeTotal = (state, total) => {
  const normalizedTotal = normalizeSearchTotal(total);
  state.searchTotal = normalizedTotal;
  return normalizedTotal;
};

// 展示用总数：优先本次有效值，否则回退到已知总数，避免中间态（分页/meta 缺失）把总数显示成 0
const resolveDisplayTotal = (state, total) => {
  const normalizedTotal = normalizeSearchTotal(total);
  if (normalizedTotal > 0) return normalizedTotal;
  return normalizeSearchTotal(state.searchTotal) || normalizeSearchTotal(state.indexSetQueryResult.total);
};

const applySearchStreamProgress = ({
  commit,
  payload,
  progress,
  requestCurrentRowKeys,
  requestRowQueryKey,
  state,
}) => {
  if (progress.stage === 'meta' && progress.meta) {
    const meta = { ...progress.meta };
    applyOptimisticTotal(state, meta.total);
    meta.total = resolveDisplayTotal(state, meta.total);
    storageHealthService.markActiveQuery(requestRowQueryKey);
    commit('updateIndexSetQueryResult', {
      ...meta,
      row_keys: Object.freeze([...requestCurrentRowKeys]),
      row_query_key: requestRowQueryKey,
      cached_count: requestCurrentRowKeys.length,
      is_error: false,
      exception_msg: '',
      is_loading: true,
      is_pagination_loading: !!payload?.isPagination,
    });
    return;
  }

  if (progress.stage === 'row' && progress.rowKeys?.length) {
    if (!payload?.isPagination && progress.rowCount === 1) {
      retrieveRowCacheService.getRows(progress.rowKeys.slice(0, 1)).then(layoutRows => {
        commit('updateIsSetDefaultTableColumn', { list: layoutRows });
      });
    }
  }
};

const getProjectionFieldNames = state => {
  const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
  const cachedFields = retrieveFieldCacheService.getFieldList(fieldScope, false);
  const fields = [
    ...(state.visibleFields || []),
    ...cachedFields.filter(field => field?.is_time_field || field?.field_name === state.indexFieldInfo?.time_field),
  ];

  return Array.from(
    new Set(
      fields
        .flatMap(field => {
          if (!field) return [];
          return [field.field_name, field.alias_mapping_field?.field_name, ...(field.source_field_names || [])];
        })
        .filter(Boolean),
    ),
  );
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
    const retrieveParams = getters.retrieveParams;
    const tableIdConditions = retrieveParams.table_id_conditions;
    if (getters.isSceneFilterEmpty || !tableIdConditions?.length) {
      commit('resetIndexFieldInfo');
      return Promise.resolve({ result: false, ignored: true, reason: 'empty-scene-filter' });
    }
    Object.assign(queryData, {
      space_uid: retrieveParams.space_uid,
      table_id_conditions: tableIdConditions,
      scene_filter_values: retrieveParams.scene_filter_values,
    });
  } else if (isUnionIndex) {
    Object.assign(queryData, {
      index_set_ids: ids,
    });
  }
  const fieldScope = JSON.stringify({
    urlStr,
    ids,
    isScene,
    isUnionIndex: !!isUnionIndex,
    start_time,
    end_time,
    scene: isScene
      ? {
          space_uid: queryData.space_uid,
          table_id_conditions: queryData.table_id_conditions,
          scene_filter_values: queryData.scene_filter_values,
        }
      : undefined,
  });

  dateFieldSortList = undefined;
  return http
    .request(
      urlStr,
      {
        params: isScene ? {} : { index_set_id: ids[0] },
        query: !isScene && !isUnionIndex ? queryData : undefined,
        data: isScene || isUnionIndex ? queryData : undefined,
      },
      isUnionIndex
        ? { cancelToken: requestCancelToken }
        : { catchIsShowMessage: false, cancelToken: requestCancelToken },
    )
    .then(res => {
      const normalizedFields = normalizeRetrieveFields(res.data ?? {});
      if (res.data) {
        res.data.fields = normalizedFields;
      }
      const { default_sort_list: defaultSortListData = [], sort_list: sortListData = [] } = res.data ?? {};
      const defaultSortList = (((defaultSortListData?.length ?? 0) > 0 ? defaultSortListData : sortListData) ?? []).map(
        ([fieldName]) => [fieldName, undefined],
      );

      normalizedFields.forEach(field => {
        if (!field || typeof field !== 'object') return;
        Object.assign(field, {
          filterVisible: field.filterVisible ?? true,
          has_repeat_alias_field: false,
          alias_mapping_field: null,
          is_virtual_alias_field: false,
        });
      });

      commit(
        'updateIndexFieldInfo',
        Object.assign({}, res.data ?? {}, {
          field_scope: fieldScope,
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
      storeCacheService
        .setApiCache(urlStr, `${ids.join(',')}:${start_time}:${end_time}`, res.data || {})
        .catch(error => {
          console.warn('[store-cache] cache field info failed', error);
        });
      return res;
    })
    .catch(err => {
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
    // 不在此处将 searchTotal 清零：保留上一次总数直到新结果（meta/最终）返回，避免因请求耗时/竞态导致标题闪成 0
    commit('updateIndexSetQueryResult', {
      row_keys: [],
      row_query_key: '',
      cached_count: 0,
      total: 0,
    });
  }

  if (
    (!state.indexItem.isUnionIndex && !state.indexId) ||
    (state.indexItem.isUnionIndex && !state.unionIndexList.length)
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

  const retrieveParams = getters.retrieveParams;
  const shouldSkipEmptySceneSearch = isSceneRetrieve(state)
    && (getters.isSceneFilterEmpty || !retrieveParams.table_id_conditions?.length);
  if (shouldSkipEmptySceneSearch) {
    commit('updateIndexSetQueryResult', {
      is_error: false,
      exception_msg: '',
      is_loading: false,
      is_pagination_loading: false,
    });
    return Promise.resolve({ result: false, ignored: true, reason: 'empty-scene-filter' });
  }

  let begin = state.indexItem.begin;
  const { size, format, ...otherParams } = retrieveParams;
  const requestAddition = getters.requestAddition;

  // 首屏流式检索未完成时，row_keys 只是部分缓存结果；此时分页请求会先取消当前 active search，
  // 导致 replace 流被 append 误杀，最终表现为只解析了部分行但页面无结果。
  if (
    payload?.isPagination
    && state.indexSetQueryResult.is_loading
    && !state.indexSetQueryResult.is_pagination_loading
  ) {
    return Promise.resolve({ result: false, ignored: true, reason: 'initial-search-loading' });
  }

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
  RequestPool.setCancelToken(cancelTokenKey, () => {
    retrieveSearchWorkerService.cancelActiveSearch();
  });

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
      retrieveRowCacheService.clearQuery(previousRowQueryKey).catch(error => {
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

  if (payload.isPagination) {
    begin += size;
  }
  const queryBegin = payload.isPagination ? begin : 0;
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

  const requestRowQueryKey = payload.isPagination
    ? state.indexSetQueryResult.row_query_key || currentRetrieveRowQueryKey
    : currentRetrieveRowQueryKey;
  const requestCurrentRowKeys = payload.isPagination ? state.indexSetQueryResult.row_keys || [] : [];
  const requestStartSeq = payload.isPagination ? requestCurrentRowKeys.length : 0;
  let isStaleSearchResponse = false;
  const isCurrentSearchRequest = () =>
    payload.isPagination
      ? requestRowQueryKey === state.indexSetQueryResult.row_query_key &&
        requestStartSeq === ((state.indexSetQueryResult.row_keys || []).length)
      : requestRowQueryKey === currentRetrieveRowQueryKey;

  const searchHeaders = buildSearchRequestHeaders(state);

  return retrieveSearchWorkerService
    .searchStream({
      baseURL: baseUrl,
      body: queryData,
      fieldNames: getProjectionFieldNames(state),
      headers: searchHeaders,
      onProgress: progress => {
        if (!isCurrentSearchRequest()) return;
        applySearchStreamProgress({
          commit,
          payload,
          progress,
          requestCurrentRowKeys,
          requestRowQueryKey,
          state,
        });
      },
      queryKey: requestRowQueryKey,
      searchPath: searchUrl,
      startSeq: requestStartSeq,
      writeMode: payload.isPagination ? 'append' : 'replace',
    })
    .then(async workerResult => {
      const { code, data, result, message, permission, rowKeys, size, source } = workerResult;
      if (!isCurrentSearchRequest()) {
        isStaleSearchResponse = true;
        if (!payload.isPagination || requestRowQueryKey !== state.indexSetQueryResult.row_query_key) {
          retrieveRowCacheService.clearQuery(requestRowQueryKey).catch(error => {
            console.warn('[retrieve-search] clear stale query rows failed', error);
          });
        }
        return { result: false, ignored: true };
      }

      const rsolvedData = data;
      const currentRowKeys = payload.isPagination
        ? state.indexSetQueryResult.row_keys || requestCurrentRowKeys
        : requestCurrentRowKeys;

      if (result) {
        if (payload.isPagination) {
          // 分页请求：仅在有效正数时更新总数，否则沿用已知总数，避免覆盖为 0
          applyOptimisticTotal(state, rsolvedData.total);
          rsolvedData.total = resolveDisplayTotal(state, rsolvedData.total);
        } else {
          // 首屏检索：以最终结果为权威值（含 0 结果）
          rsolvedData.total = applyAuthoritativeTotal(state, rsolvedData.total);
        }
        rsolvedData.row_keys = Object.freeze(Array.from(new Set(currentRowKeys.concat(rowKeys))));
        rsolvedData.row_query_key = requestRowQueryKey;
        rsolvedData.cached_count = rsolvedData.row_keys.length;
        rsolvedData.ingest_source = source;
        storageHealthService.markActiveQuery(requestRowQueryKey);

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
        storeCacheService
          .setApiCache('retrieve/search-result-meta', requestRowQueryKey, {
            ...rsolvedData,
            row_keys: rsolvedData.row_keys,
            row_query_key: requestRowQueryKey,
            cached_count: rsolvedData.cached_count,
          })
          .catch(error => {
            console.warn('[store-cache] cache search meta failed', error);
          });
        retrieveRowCacheService
          .gc({
            excludeQueryKeys: Array.from(new Set([requestRowQueryKey, ...storageHealthService.getActiveQueryKeys()])),
          })
          .catch(error => {
            console.warn('[retrieve-search] gc rows failed', error);
          });

        // logRetrieveSearchIngest('info', 'search stream result applied on main thread', {
        //   queryKey: requestRowQueryKey,
        //   rowCount: size,
        //   source,
        //   stage: 'complete',
        // });

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

      // 明确的失败/无权限：权威清零总数
      state.searchTotal = 0;
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
    })
    .catch(e => {
      if (!isCurrentSearchRequest()) {
        isStaleSearchResponse = true;
        return;
      }

      state.searchTotal = 0;
      retrieveRowCacheService.clearMemory();
      commit('updateSqlQueryFieldList', []);
      if (!isSearchRequestCanceled(e)) {
        commit('updateIndexSetQueryResult', {
          is_error: true,
          exception_msg: e?.message ?? e?.toString(),
          total: 0,
        });
      }

      if (isSearchRequestCanceled(e)) {
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
