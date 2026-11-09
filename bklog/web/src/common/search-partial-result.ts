/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */

export const isPartialSearchResult = (
  data:
    | {
        is_partial?: boolean;
        status?: { code?: string };
      }
    | null
    | undefined,
): boolean =>
  data?.is_partial === true || data?.status?.code === 'QUERY_RAW_PARTIAL' || data?.status?.code === 'QUERY_TS_PARTIAL';

/** Only the standalone single-index results page consumes partial responses. */
export const partialPageParams = (isScene: boolean, isUnion: boolean) =>
  isScene || isUnion || window.__IS_MONITOR_COMPONENT__ || window.__IS_MONITOR_TRACE__ || window.__IS_MONITOR_APM__
    ? {}
    : { allow_partial_es_results: true };
