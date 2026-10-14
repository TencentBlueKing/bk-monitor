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
import dayjs from 'dayjs';

import type {
  CollectionDraft,
  CollectionHost,
  CollectionMeta,
  CollectionPayload,
  CollectionQueryState,
  CollectionTask,
  HostPids,
  PreviewSelector,
  ProcessRow,
  ProcessSelector,
} from '../types/collection';

export const collectionMethodLabels = { perf: 'Perf', golang: 'Go', java: 'Java' };
export const collectionTypeLabels = {
  native_cpu: 'Native CPU',
  go_cpu: 'Go CPU',
  go_heap: 'Go Heap',
  java_cpu: 'Java CPU',
  java_allocation: 'Java Allocation',
};
export const scheduleLabels = { immediate: '立即执行', once_at: '指定时间', cron: '周期执行' };
export const processLabels = { command: '命令行匹配', pid_file: 'PID 文件匹配', pid: '搜索 PID' };

export function createCollectionDraft(meta: CollectionMeta, timezone: string, task?: CollectionTask): CollectionDraft {
  const method =
    task?.collection_method || (meta.collection_methods.includes('java') ? 'java' : meta.collection_methods[0]);
  const collectionType = task?.collection_type || meta.collection_types_by_method[method]?.[0];
  const selector = task?.process_selector;
  const schedule = task?.schedule;
  const draft: CollectionDraft = {
    name: task?.name || '',
    hosts: task?.target_config.nodes.map(node => ({ host_id: node.bk_host_id })) || [],
    method,
    collectionType,
    collector: { ...meta.collector_config[collectionType], ...task?.collector_config },
    resourceGuard: { ...meta.resource_guard_config, ...task?.resource_guard_config },
    processMode: selector?.type || meta.process_selector_types[0],
    process: {
      matchPattern: '',
      excludePattern: '',
      dynamic: false,
      pidPath: '',
      pids: '',
      selected: { command: [], pid_file: [], pid: [] },
    },
    scheduleType: schedule?.type || meta.schedule_types[0],
    executeAt: schedule && schedule.type !== 'cron' ? schedule.execute_at : null,
    startAt: schedule?.type === 'cron' ? schedule.effective_start_at : null,
    endAt: schedule?.type === 'cron' ? schedule.effective_end_at : null,
    cron: schedule?.type === 'cron' ? schedule.cron_expression : '',
    timezone: schedule?.timezone || timezone,
  };
  if (selector) {
    if (selector.type === 'command') {
      draft.process.matchPattern = selector.config.match_pattern;
      draft.process.excludePattern = selector.config.exclude_pattern;
      draft.process.dynamic = selector.config.enable_dynamic_collection;
    }
    if (selector.type === 'pid_file') draft.process.pidPath = selector.config.pid_path;
    draft.process.selected[selector.type] = (selector.config.host_pids || []).flatMap(host =>
      host.pids.map(pid => ({ bk_host_id: host.bk_host_id, pid }))
    );
    if (selector.type === 'pid')
      draft.process.pids = [...new Set(draft.process.selected.pid.map(row => row.pid))].join(', ');
  }
  return draft;
}

export function createCollectionQueryState(): CollectionQueryState {
  return {
    tab: 'tasks',
    keyword: '',
    scheduleTypes: [],
    statuses: [],
    sort: null,
    historyTaskId: null,
    historyTaskName: '',
  };
}

export function restoreCollectionQuery(value?: Partial<CollectionQueryState>): CollectionQueryState {
  const defaults = createCollectionQueryState();
  if (!value) return defaults;
  return {
    ...defaults,
    tab: ['tasks', 'history', 'results'].includes(value.tab) ? value.tab : defaults.tab,
    keyword: typeof value.keyword === 'string' ? value.keyword : '',
    scheduleTypes: Array.isArray(value.scheduleTypes)
      ? value.scheduleTypes.filter(type => ['once_at', 'cron'].includes(type))
      : [],
    statuses: Array.isArray(value.statuses)
      ? value.statuses.filter(status => ['enabled', 'disabled'].includes(status))
      : [],
    sort: ['name', 'updated_at', 'schedule'].includes(value.sort?.sortBy)
      ? { sortBy: value.sort.sortBy, descending: value.sort.descending === true }
      : null,
    historyTaskId: Number.isInteger(value.historyTaskId) && value.historyTaskId > 0 ? value.historyTaskId : null,
    historyTaskName: typeof value.historyTaskName === 'string' ? value.historyTaskName : '',
  };
}

export const processKey = (row: ProcessRow) => `${row.bk_host_id}:${row.pid ?? 'error'}`;
export const collectionTarget = (hosts: CollectionHost[]) => ({
  node_type: 'INSTANCE' as const,
  nodes: hosts.map(host => ({ bk_host_id: host.host_id })),
});

export function buildCollectionPayload(draft: CollectionDraft, bizId: number, now = Date.now()): CollectionPayload {
  if (!draft.name.trim()) throw new Error('请输入任务名称');
  if (!draft.hosts.length) throw new Error('请选择目标主机');
  if (!draft.method || !draft.collectionType) throw new Error('请选择采集方式和类型');
  const collector = draft.collector;
  const positive = (value: number) => Number.isFinite(value) && value > 0;
  if (draft.collectionType !== 'go_heap' && (!positive(collector.duration_sec) || collector.duration_sec > 300))
    throw new Error('采集时长须大于 0 且不超过 300 秒');
  if (draft.method === 'perf' && (!positive(collector.frequency_hz) || !collector.stack_unwind))
    throw new Error('请填写有效的采样频率和栈展开方式');
  if (draft.method === 'golang' && (!collector.ip_address?.trim() || !positive(collector.port)))
    throw new Error('请填写有效的采集地址和端口');
  let hosts = draft.hosts;
  let selector: ProcessSelector;
  if (draft.method !== 'golang') {
    const hostIds = new Set(hosts.map(host => host.host_id));
    const hostPids = groupProcessPids(
      draft.process.selected[draft.processMode].filter(row => hostIds.has(row.bk_host_id))
    );
    if (draft.processMode === 'pid') selector = { type: 'pid', config: { host_pids: hostPids } };
    else {
      const preview = buildPreviewSelector(draft);
      if (preview.type === 'pid_file')
        selector = {
          type: 'pid_file',
          config: { ...preview.config, ...(hostPids.length ? { host_pids: hostPids } : {}) },
        };
      if (preview.type === 'command')
        selector = {
          type: 'command',
          config: {
            ...preview.config,
            enable_dynamic_collection: draft.process.dynamic,
            ...(!draft.process.dynamic ? { host_pids: hostPids } : {}),
          },
        };
    }
    if (selector.type === 'pid' || (selector.type === 'command' && !selector.config.enable_dynamic_collection)) {
      if (!hostPids.length) throw new Error('请选择目标进程');
      const selectedHosts = new Set(hostPids.map(host => host.bk_host_id));
      hosts = hosts.filter(host => selectedHosts.has(host.host_id));
    }
  }
  if (draft.scheduleType === 'once_at' && (!draft.executeAt || draft.executeAt <= now))
    throw new Error('指定执行时间须晚于当前时间');
  if (
    draft.scheduleType === 'cron' &&
    (!draft.startAt || !draft.endAt || draft.endAt <= draft.startAt || draft.endAt <= now)
  )
    throw new Error('请选择有效的周期任务起止时间');
  if (draft.scheduleType === 'cron' && draft.cron.trim().split(/\s+/).length !== 5)
    throw new Error('请填写有效的五段式 Cron 表达式');
  return {
    bk_biz_id: bizId,
    name: draft.name.trim(),
    collection_method: draft.method,
    collection_type: draft.collectionType,
    target_config: collectionTarget(hosts),
    ...(selector ? { process_selector: selector } : {}),
    collector_config: { ...collector },
    resource_guard_config: { ...draft.resourceGuard },
    schedule:
      draft.scheduleType === 'cron'
        ? {
            type: 'cron',
            cron_expression: draft.cron.trim(),
            effective_start_at: draft.startAt,
            effective_end_at: draft.endAt,
            timezone: draft.timezone,
          }
        : {
            type: draft.scheduleType,
            execute_at: draft.scheduleType === 'immediate' ? now : draft.executeAt,
            timezone: draft.timezone,
          },
  };
}

export function buildPreviewSelector(draft: CollectionDraft): PreviewSelector {
  const process = draft.process;
  if (draft.processMode === 'command') {
    if (!process.matchPattern.trim()) throw new Error('请输入命令行匹配条件');
    return {
      type: 'command',
      config: { match_pattern: process.matchPattern.trim(), exclude_pattern: process.excludePattern.trim() },
    };
  }
  if (draft.processMode === 'pid_file') {
    if (!process.pidPath.trim().startsWith('/')) throw new Error('请输入 PID 文件的绝对路径');
    return { type: 'pid_file', config: { pid_path: process.pidPath.trim() } };
  }
  const values = process.pids.trim().split(/[,;\s，；]+/);
  if (
    !values.length ||
    values.some(value => !/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0)
  )
    throw new Error('请输入有效的 PID，多个 PID 用逗号分隔');
  return { type: 'pid', config: { pids: [...new Set(values.map(Number))] } };
}

export function filterCollectionTasks(tasks: CollectionTask[], query: CollectionQueryState) {
  const keyword = query.keyword.trim().toLocaleLowerCase();
  const filtered = tasks.filter(
    task =>
      (!keyword || task.name.toLocaleLowerCase().includes(keyword)) &&
      (!query.scheduleTypes.length || query.scheduleTypes.includes(task.schedule.type)) &&
      (!query.statuses.length || query.statuses.includes(task.task_status))
  );
  if (query.sort) {
    const { sortBy, descending } = query.sort;
    const value = (task: CollectionTask) =>
      sortBy === 'schedule'
        ? task.schedule.type === 'cron'
          ? task.schedule.effective_start_at
          : task.schedule.execute_at
        : task[sortBy];
    filtered.sort(
      (a, b) =>
        (typeof value(a) === 'number' ? value(a) - value(b) : String(value(a)).localeCompare(String(value(b)))) *
        (descending ? -1 : 1)
    );
  }
  return filtered;
}

export function formatCollectionTime(value: number, timezone: string) {
  return value ? dayjs(value).tz(timezone).format('YYYY-MM-DD HH:mm:ss') : '--';
}

export function groupProcessPids(rows: ProcessRow[]): HostPids[] {
  const grouped = new Map<number, Set<number>>();
  for (const row of rows) {
    if (!Number.isInteger(row.pid) || row.pid <= 0 || row.err_msg) continue;
    if (!grouped.has(row.bk_host_id)) grouped.set(row.bk_host_id, new Set());
    grouped.get(row.bk_host_id).add(row.pid);
  }
  return [...grouped].map(([bk_host_id, pids]) => ({ bk_host_id, pids: [...pids] }));
}

export function immediateCollectionPayload(task: CollectionTask, bizId: number, now = Date.now()): CollectionPayload {
  const {
    name,
    collection_method,
    collection_type,
    target_config,
    process_selector,
    collector_config,
    resource_guard_config,
  } = task;
  return {
    bk_biz_id: bizId,
    name,
    collection_method,
    collection_type,
    target_config,
    ...(process_selector ? { process_selector } : {}),
    collector_config,
    resource_guard_config,
    schedule: { type: 'immediate', execute_at: now, timezone: task.schedule.timezone },
  };
}
