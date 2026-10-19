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
  buildExecutionPayload,
  createHistoryFilters,
  executionKey,
  restoreExecutionSelection,
  restoreHistoryFilters,
} from './collection-history';
import { createViewState, restoreViewState } from './profile-view';

import type { CollectionExecutionDetail, CollectionResultSelection } from '../types/collection-history';
import type { CollectionHostResult, CollectionResultParams, CollectionResultsState } from '../types/collection-results';

export function createCollectionResultsState(): CollectionResultsState {
  return { filters: createHistoryFilters(), execution: null, dataType: '', view: createViewState() };
}

export function restoreCollectionResultsState(value?: Partial<CollectionResultsState>): CollectionResultsState {
  const execution = value?.execution
    ? restoreExecutionSelection({ ...value.execution, scope: 'execution', started_at: null, finished_at: null })
    : null;
  const view = restoreViewState(value?.view);
  const filters = restoreHistoryFilters(value?.filters);
  return {
    filters: { ...filters, status: filters.status === 'outdate' ? 'outdated' : filters.status },
    execution: execution ? executionKey(execution) : null,
    dataType: typeof value?.dataType === 'string' ? value.dataType : '',
    view: { ...view, graphMode: view.graphMode === 'callgraph' ? 'combined' : view.graphMode },
  };
}

export function resultExecutionKey(row: CollectionHostResult) {
  return executionKey({ ...row.task, scheduled_at: row.scheduled_at });
}

export function resultSelection(row: CollectionHostResult): CollectionResultSelection {
  return {
    ...resultExecutionKey(row),
    scope: 'host',
    bk_host_id: row.bk_host_id,
    started_at: row.started_at,
    finished_at: row.finished_at,
  };
}

export const resultRowKey = (row: CollectionHostResult) =>
  `${row.task.schedule_type}:${row.task.task_id || ''}:${row.scheduled_at}:${row.bk_host_id}`;

export const canViewHostResult = (row: CollectionHostResult) =>
  row.status === 'succeed' && row.started_at != null && row.finished_at != null;

export function buildHostCollectionPayload(
  detail: CollectionExecutionDetail,
  hostId: number,
  bizId: number,
  now = Date.now()
) {
  const host = detail.hosts.find(host => host.bk_host_id === hostId);
  if (!host || host.status === 'running') throw new Error('采集中或主机不存在，暂不能重新采集');
  const payload = buildExecutionPayload(detail, bizId, false, now);
  payload.target_config.nodes = payload.target_config.nodes.filter(node => node.bk_host_id === hostId);
  if (!payload.target_config.nodes.length) throw new Error('历史配置中没有当前主机');
  if (payload.process_selector?.type === 'command' && payload.process_selector.config.host_pids) {
    payload.process_selector.config.host_pids = payload.process_selector.config.host_pids.filter(
      item => item.bk_host_id === hostId
    );
  }
  return payload;
}

export function executionResultRows(detail: CollectionExecutionDetail): CollectionHostResult[] {
  return detail.hosts.map(host => ({
    ...host,
    scheduled_at: detail.scheduled_at,
    task: { ...executionKey(detail), name: detail.task_name },
    collection_method: detail.collection_method,
    collection_type: detail.collection_type,
  }));
}

export function resultParams(row: CollectionHostResult, bizId: number): CollectionResultParams {
  return {
    bk_biz_id: bizId,
    bk_host_id: row.bk_host_id,
    scheduled_at: row.scheduled_at,
    ...(row.task.schedule_type === 'immediate' ? {} : { task_id: row.task.task_id }),
    started_at: row.started_at,
    finished_at: row.finished_at,
  };
}

export function resultUnavailableReason(row: CollectionHostResult): string {
  if (row.status === 'running') return '采集中，暂时无法查看结果';
  if (['outdate', 'outdated'].includes(row.status)) return '已过期，无法查看结果';
  return '本次采集暂无可查看的结果';
}
