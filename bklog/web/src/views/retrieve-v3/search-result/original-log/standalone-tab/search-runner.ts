import { axiosInstance } from '@/api';
import { readBlobRespToJson } from '@/common/util';

export interface StandaloneSearchPayload {
  indexSetId: number;
  query: Record<string, any>;
  routeQuery: Record<string, any>;
}

export interface StandaloneSearchResult {
  payload: StandaloneSearchPayload;
  data: Record<string, any>;
  rowIndex: number;
  rowData: Record<string, any>;
  retrieveParams: Record<string, any>;
}

const tryParseJSON = (value: any, fallback: any) => {
  if (value === undefined || value === null || value === '') return fallback;
  if (Array.isArray(value) || typeof value === 'object') return value;
  try {
    return JSON.parse(String(value));
  } catch {
    return fallback;
  }
};

const toNumber = (value: any, fallback = 0) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
};

export const buildStandaloneSearchPayload = (routeQuery: Record<string, any>): StandaloneSearchPayload => {
  const indexSetId = toNumber(routeQuery.indexId || routeQuery.index_set_id, 0);
  const size = toNumber(routeQuery.size, 50);
  const begin = toNumber(routeQuery.begin, 0);
  const startTime = toNumber(routeQuery.start_time, 0);
  const endTime = toNumber(routeQuery.end_time, 0);
  const bkBizId = toNumber(routeQuery.bizId || routeQuery.bk_biz_id, 0);

  const query: Record<string, any> = {
    bk_biz_id: bkBizId,
    size,
    begin,
    start_time: startTime,
    end_time: endTime,
    addition: tryParseJSON(routeQuery.addition, []),
    keyword: routeQuery.keyword === undefined ? '*' : String(routeQuery.keyword || '*'),
    search_mode: String(routeQuery.search_mode || 'ui'),
    sort_list: tryParseJSON(routeQuery.sort_list, []),
    ip_chooser: tryParseJSON(routeQuery.ip_chooser, {}),
    host_scopes: tryParseJSON(routeQuery.host_scopes, {}),
    interval: String(routeQuery.interval || 'auto'),
  };

  if (routeQuery.time_zone) query.time_zone = routeQuery.time_zone;
  if (routeQuery.spaceUid || routeQuery.space_uid) query.space_uid = routeQuery.spaceUid || routeQuery.space_uid;
  if (routeQuery.language) query.language = routeQuery.language;

  return {
    indexSetId,
    query,
    routeQuery,
  };
};

export const requestStandaloneSearch = async (payload: StandaloneSearchPayload) => {
  const baseURL = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
  const response = await axiosInstance({
    method: 'post',
    url: `/search/index_set/${payload.indexSetId}/search/`,
    baseURL,
    withCredentials: true,
    responseType: 'blob',
    data: payload.query,
    headers: payload.routeQuery.spaceUid || payload.routeQuery.space_uid
      ? { 'X-Bk-Space-Uid': payload.routeQuery.spaceUid || payload.routeQuery.space_uid }
      : undefined,
  });

  const body = await readBlobRespToJson(response.data);
  if (!body?.result) {
    throw new Error(body?.message || 'search failed');
  }

  return body.data;
};


const parseRowIndex = (value: any) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue >= 0 ? numberValue : 0;
};

export const createStandaloneRetrieveParams = (payload: StandaloneSearchPayload) => ({
  ...payload.query,
  format: 'json',
});

export const runStandaloneRelatedSearch = async (routeQuery: Record<string, any>): Promise<StandaloneSearchResult> => {
  const payload = buildStandaloneSearchPayload(routeQuery);
  if (!payload.indexSetId) {
    throw new Error('missing index set id');
  }

  const data = await requestStandaloneSearch(payload);
  const originList = data?.origin_log_list;
  if (!Array.isArray(originList)) {
    throw new Error('missing origin_log_list');
  }

  const rowIndex = parseRowIndex(routeQuery.rowIndex);
  const rowData = originList[rowIndex];
  if (!rowData) {
    throw new Error('row not found');
  }

  return {
    payload,
    data,
    rowIndex,
    rowData,
    retrieveParams: createStandaloneRetrieveParams(payload),
  };
};
