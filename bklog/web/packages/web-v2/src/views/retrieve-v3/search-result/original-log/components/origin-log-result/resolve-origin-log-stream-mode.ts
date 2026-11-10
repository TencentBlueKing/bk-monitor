/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

export type OriginLogStreamUiMode = 'replace' | 'append';
export type OriginLogStreamWriteMode = 'replace' | 'append';

/**
 * 解析上下文本地 Stream 的 UI / 落盘模式。
 * - 主检索种子后的首次加载更多：新建独立 queryKey（write replace），UI 追加
 * - 已有 localQueryKey 的分页：storage append
 * - 手动重搜且 begin=0：UI + storage 均为 replace
 */
export const resolveOriginLogStreamMode = (params: {
  begin: number;
  hasLocalQueryKey: boolean;
  isManualSearch: boolean;
}) => {
  const isStorageAppend = params.begin > 0 && !params.isManualSearch && params.hasLocalQueryKey;
  const uiMode: OriginLogStreamUiMode = params.isManualSearch && params.begin === 0 ? 'replace' : 'append';
  const writeMode: OriginLogStreamWriteMode = isStorageAppend ? 'append' : 'replace';
  // writer 全量 keys 用 replace 语义增量；storage append 用本页增量 keys
  const syncMode: OriginLogStreamWriteMode = isStorageAppend ? 'append' : 'replace';

  return {
    isStorageAppend,
    syncMode,
    uiMode,
    writeMode,
  };
};

/** 本页完成后校准 localStoredRowCount（不含主检索种子行） */
export const resolveLocalStoredRowCountAfterResult = (params: {
  isStorageAppend: boolean;
  requestStartSeq: number;
  rowKeysLength: number;
}) => {
  if (!params.isStorageAppend) {
    return params.rowKeysLength;
  }
  return params.requestStartSeq + params.rowKeysLength;
};

/** 本地 queryKey 种子参数，保证与主检索隔离 */
export const buildOriginLogLocalQuerySeed = (params: {
  addition?: unknown;
  indexSetId: number | string;
  keyword?: unknown;
  searchMode?: unknown;
  seq: number;
}) => ({
  addition: params.addition,
  begin: 0,
  indexSetId: params.indexSetId,
  keyword: params.keyword,
  searchMode: params.searchMode,
  seq: params.seq,
  standalone: 'origin-log-result' as const,
});
