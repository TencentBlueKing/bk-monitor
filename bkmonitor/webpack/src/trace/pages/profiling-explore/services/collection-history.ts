/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import {
  cancelExecution,
  collectionTopk,
  executionDetail,
  executionsRename,
  listExecutions,
} from 'monitor-api/modules/apm_profile_active_collection';

import { executionKey, historyFiltersPayload } from '../utils/collection-history';

import type { SelectionRange } from '../types';
import type {
  CollectionCandidate,
  CollectionCandidateField,
  CollectionExecution,
  CollectionExecutionDetail,
  CollectionExecutionKey,
  CollectionHistoryFilters,
  CollectionHistoryResult,
} from '../types/collection-history';

const options = (signal: AbortSignal) => ({ signal, needMessage: false });

// 历史列表分页大小，翻页判断需与请求 limit 保持一致
export const COLLECTION_HISTORY_PAGE_SIZE = 20;

export function getCollectionCandidates(
  bizId: number,
  range: SelectionRange,
  field: CollectionCandidateField,
  signal: AbortSignal
): Promise<CollectionCandidate[]> {
  return collectionTopk(
    { bk_biz_id: bizId, start_time: range[0], end_time: range[1], field, limit: 20 },
    options(signal)
  );
}

export function getCollectionExecution(
  bizId: number,
  key: CollectionExecutionKey,
  signal: AbortSignal
): Promise<CollectionExecutionDetail> {
  return executionDetail({ bk_biz_id: bizId, ...executionKey(key) }, options(signal));
}

export function getCollectionHistory(
  bizId: number,
  range: SelectionRange,
  filters: CollectionHistoryFilters,
  offset: number,
  signal: AbortSignal
): Promise<CollectionHistoryResult> {
  return listExecutions(
    {
      bk_biz_id: bizId,
      start_time: range[0],
      end_time: range[1],
      // 未按任务 ID 筛选时不传该字段，接口不接受 null
      filters: historyFiltersPayload(filters),
      offset,
      limit: COLLECTION_HISTORY_PAGE_SIZE,
    },
    options(signal)
  );
}

export function renameCollectionExecution(
  bizId: number,
  execution: CollectionExecutionKey,
  taskName: string,
  signal: AbortSignal
): Promise<void> {
  // 执行定位键与 detail/cancel 一致，立即执行不带 task_id
  return executionsRename({ bk_biz_id: bizId, ...executionKey(execution), task_name: taskName }, options(signal));
}

export function stopCollectionExecution(
  bizId: number,
  execution: CollectionExecution,
  signal: AbortSignal
): Promise<void> {
  return cancelExecution(
    {
      bk_biz_id: bizId,
      ...executionKey(execution),
      hosts: execution.hosts.map(({ bk_host_id, ip }) => ({ bk_host_id, ip })),
    },
    options(signal)
  );
}
