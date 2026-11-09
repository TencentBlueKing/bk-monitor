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
