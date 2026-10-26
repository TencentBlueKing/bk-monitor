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
import { formatUnitValue } from '../../rum-explore/utils';

import type { CollectionPayload } from '../types/collection';
import type {
  CollectionCandidate,
  CollectionCandidateField,
  CollectionExecution,
  CollectionExecutionColumn,
  CollectionExecutionDetail,
  CollectionExecutionHost,
  CollectionExecutionKey,
  CollectionHistoryFilters,
  CollectionResultSelection,
  CollectionTaskColumn,
} from '../types/collection-history';

export const executionStatusLabels = {
  running: '采集中',
  succeed: '成功',
  partial_succeed: '部分成功',
  failed: '失败',
  timeout: '超时',
  cancelled: '已取消',
  unknown: '未知',
  outdated: '已过期',
  outdate: '已过期',
};

const hostStatusRanks: Record<string, number> = {
  failed: 0,
  timeout: 1,
  running: 2,
  partial_succeed: 3,
  succeed: 4,
  cancelled: 5,
  outdated: 6,
  outdate: 6,
  unknown: 7,
};

type ProcessFilters = Pick<CollectionHistoryFilters, 'process_names' | 'process_pids'>;

export function compareExecutionHostStatus(left: CollectionExecutionHost, right: CollectionExecutionHost): number {
  return (
    (hostStatusRanks[left.status] ?? hostStatusRanks.unknown) -
    (hostStatusRanks[right.status] ?? hostStatusRanks.unknown)
  );
}

export function createHistoryFilters(): CollectionHistoryFilters {
  return { ips: [], task_name: '', process_names: [], process_pids: [], schedule_types: [], status: '' };
}

export function executionKey(value: CollectionExecutionKey): CollectionExecutionKey {
  return {
    schedule_type: value.schedule_type,
    scheduled_at: value.scheduled_at,
    ...(value.schedule_type === 'immediate' ? {} : { task_id: value.task_id }),
  };
}

export function parseProcessSelection(values: string[]): ProcessFilters {
  const result: ProcessFilters = { process_names: [], process_pids: [] };
  for (const id of values) {
    const [field, value] = processOption(id);
    if (!result[field].includes(value)) result[field].push(value);
  }
  return result;
}

export function processCandidateOptions(
  candidates: Partial<Record<CollectionCandidateField, CollectionCandidate[]>>,
  selected: string[]
) {
  const options = new Map<string, { id: string; name: string }>();
  for (const field of ['process_names', 'process_pids'] as const) {
    for (const item of candidates[field] || []) {
      const value = String(item.value);
      const restoredId = JSON.stringify([field, value]);
      const id =
        selected.includes(restoredId) && !options.has(restoredId)
          ? restoredId
          : JSON.stringify([field, value, item.alias]);
      options.set(id, { id, name: `${field === 'process_pids' ? 'PID: ' : ''}${item.alias || value}` });
    }
  }
  for (const id of selected) {
    if (!options.has(id)) {
      const [field, value] = processOption(id);
      options.set(id, { id, name: `${field === 'process_pids' ? 'PID: ' : ''}${value}` });
    }
  }
  return [...options.values()];
}

export function restoreHistoryFilters(value?: Partial<CollectionHistoryFilters>): CollectionHistoryFilters {
  const strings = (items: unknown) => (Array.isArray(items) ? items.filter(item => typeof item === 'string') : []);
  return {
    ips: strings(value?.ips),
    task_name: typeof value?.task_name === 'string' ? value.task_name : '',
    process_names: strings(value?.process_names),
    process_pids: strings(value?.process_pids),
    // 仅保留后端支持的执行方式，过滤掉历史数据或异常取值
    schedule_types: strings(value?.schedule_types).filter(type => ['immediate', 'once_at', 'cron'].includes(type)),
    status: Object.hasOwn(executionStatusLabels, value?.status || '') ? value.status : '',
  };
}

export function restoreProcessSelection(filters: ProcessFilters, selected: string[]): string[] {
  const result = selected.filter(id => {
    const [field, value] = processOption(id);
    return filters[field].includes(value);
  });
  for (const field of ['process_names', 'process_pids'] as const) {
    for (const value of filters[field]) {
      if (
        !result.some(id => {
          const entry = processOption(id);
          return entry[0] === field && entry[1] === value;
        })
      )
        result.push(JSON.stringify([field, value]));
    }
  }
  return result;
}

function processOption(value: string): [keyof ProcessFilters, string] {
  try {
    const entry = JSON.parse(value);
    if (Array.isArray(entry) && ['process_names', 'process_pids'].includes(entry[0]) && typeof entry[1] === 'string')
      return [entry[0], entry[1]];
  } catch {
    /* 自定义输入不是候选编码 */
  }
  return [/^\d+$/.test(value) ? 'process_pids' : 'process_names', value];
}

export const executionRowKey = (value: CollectionExecutionKey) =>
  `${value.schedule_type}:${value.scheduled_at}:${value.schedule_type === 'immediate' ? '' : value.task_id}`;

export function executionSelection(
  value: CollectionExecution,
  host?: CollectionExecutionHost
): CollectionResultSelection {
  return {
    ...executionKey(value),
    scope: host ? 'host' : 'execution',
    ...(host ? { bk_host_id: host.bk_host_id } : {}),
    started_at: (host || value).started_at,
    finished_at: (host || value).finished_at,
  };
}

export function restoreExecutionSelection(value?: CollectionResultSelection): CollectionResultSelection | null {
  const positive = (n: unknown) => typeof n === 'number' && Number.isFinite(n) && n > 0;
  if (
    !value ||
    !['immediate', 'once_at', 'cron'].includes(value.schedule_type) ||
    !positive(value.scheduled_at) ||
    (value.schedule_type !== 'immediate' && (!Number.isSafeInteger(value.task_id) || !positive(value.task_id))) ||
    !['execution', 'host'].includes(value.scope) ||
    (value.scope === 'host' && (!Number.isSafeInteger(value.bk_host_id) || !positive(value.bk_host_id)))
  )
    return null;
  const start = positive(value.started_at) ? value.started_at : null;
  const end = positive(value.finished_at) ? value.finished_at : null;
  if (start !== null && end !== null && end < start) return null;
  return {
    ...executionKey(value),
    scope: value.scope,
    ...(value.scope === 'host' ? { bk_host_id: value.bk_host_id } : {}),
    started_at: start,
    finished_at: end,
  };
}

// 后端只下发列类型，最小宽度按类型兜底，避免动态列被内容挤压
export const hostColumnMinWidths: Record<CollectionExecutionColumn['type'], number> = {
  datetime: 180,
  duration: 100,
  process_list: 200,
  status: 120,
  text: 160,
};

// 任务历史列同样只由后端声明类型，最小宽度按类型兜底；用 Map 避免后端字段命中原型属性
const taskColumnMinWidths = new Map<string, number>([
  ['datetime', 180],
  ['duration', 100],
  ['number', 100],
  ['status', 140],
  ['text', 160],
]);

// 已知业务字段沿用原表格列宽，避免动态列改变既有布局
const taskFieldMinWidths = new Map<string, number>([
  ['collection_type', 160],
  ['duration_ms', 100],
  ['execution_status', 140],
  ['hosts', 130],
  ['schedule_type', 140],
  ['started_at', 200],
  ['target_count', 100],
  ['task_name', 220],
]);

export const taskColumnMinWidth = (column: CollectionTaskColumn) =>
  taskFieldMinWidths.get(column.field) ?? taskColumnMinWidths.get(column.type) ?? 160;

export const canViewExecution = (value: CollectionExecution) =>
  ['succeed', 'partial_succeed'].includes(value.execution_status);
export const canRetryExecution = (value: CollectionExecutionDetail) =>
  value.execution_status !== 'running' && value.hosts.some(host => ['failed', 'timeout'].includes(host.status));
// 耗时按 ms 自适应换算单位，避免长数值撑破列宽
export const formatExecutionDuration = (value: null | number) => (value == null ? '--' : formatUnitValue(value, 'ms'));

export function buildExecutionPayload(
  detail: CollectionExecutionDetail,
  bizId: number,
  failedOnly: boolean,
  now = Date.now()
): CollectionPayload {
  const config = structuredClone(detail.config);
  if (failedOnly) {
    if (detail.execution_status === 'running') throw new Error('采集中，暂不能重试失败项');
    const hosts = new Set(
      detail.hosts.filter(host => ['failed', 'timeout'].includes(host.status)).map(host => host.bk_host_id)
    );
    config.target_config.nodes = config.target_config.nodes.filter(host => hosts.has(host.bk_host_id));
    if (!config.target_config.nodes.length) throw new Error('没有可重试的失败主机');
    if (config.process_selector?.type === 'command' && config.process_selector.config.host_pids) {
      config.process_selector.config.host_pids = config.process_selector.config.host_pids.filter(host =>
        hosts.has(host.bk_host_id)
      );
    }
  }
  return {
    ...config,
    bk_biz_id: bizId,
    name: detail.task_name,
    collection_method: detail.collection_method,
    collection_type: detail.collection_type,
    schedule: { type: 'immediate', execute_at: now, timezone: config.schedule.timezone },
  };
}

export function executionConfiguration(detail: CollectionExecutionDetail): Omit<CollectionPayload, 'bk_biz_id'> {
  return {
    ...detail.config,
    name: detail.task_name,
    collection_method: detail.collection_method,
    collection_type: detail.collection_type,
  };
}
