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

import { createHistoryFilters, restoreExecutionSelection, restoreHistoryFilters } from './collection-history';
import { createCollectionResultsState, restoreCollectionResultsState } from './collection-results';

import type {
  CollectionDraft,
  CollectionFieldError,
  CollectionFieldKey,
  CollectionHost,
  CollectionMeta,
  CollectionPayload,
  CollectionQueryState,
  CollectionTask,
  HostPid,
  PreviewSelector,
  ProcessRow,
  ProcessSelector,
} from '../types/collection';

/** 采集方式对应的展示名 */
export const collectionMethodLabels = { perf: 'Perf', golang: 'Go', java: 'Java' };
/** 采集类型对应的展示名 */
export const collectionTypeLabels = {
  native_cpu: 'Native CPU',
  go_cpu: 'Go CPU',
  go_heap: 'Go Heap',
  java_cpu: 'Java CPU',
  java_allocation: 'Java Allocation',
};
/** 调度方式对应的展示名 */
export const scheduleLabels = { immediate: '立即执行', once_at: '指定时间', cron: '周期执行' };
/** 进程匹配方式对应的展示名 */
export const processLabels = { command: '命令行匹配', pid_file: 'PID 文件匹配', pid: '搜索 PID' };

/**
 * @description 构造带字段归属的提交校验错误，交由表单在对应 form item 下展示
 * @param field 出错的表单字段
 * @param message 未翻译的错误文案，由调用方 t() 处理
 * @returns 附带 field 的错误对象
 */
export const collectionFieldError = (field: CollectionFieldKey, message: string): CollectionFieldError =>
  Object.assign(new Error(message), { field });

/**
 * @description 按采集元信息构建表单草稿，传入 task 时回填为编辑态
 * @param meta 采集能力元信息，提供可选方式、类型及默认配置
 * @param timezone 默认时区，任务未指定时区时兜底
 * @param task 待编辑的采集任务，缺省表示新建
 * @returns 采集表单草稿
 */
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
      dynamic: true,
      pidPath: '',
      pids: '',
      selected: [],
    },
    scheduleType: schedule?.type || meta.schedule_types[0],
    executeAt: schedule && schedule.type !== 'cron' ? schedule.execute_at : null,
    startAt: schedule?.type === 'cron' ? schedule.effective_start_at : null,
    endAt: schedule?.type === 'cron' ? schedule.effective_end_at : null,
    cron: schedule?.type === 'cron' ? schedule.cron_expression : (meta.schedule?.cron?.cron_expression ?? ''),
    timezone: schedule?.timezone || timezone,
  };
  if (selector) {
    if (selector.type === 'command') {
      draft.process.matchPattern = selector.config.match_pattern;
      draft.process.excludePattern = selector.config.exclude_pattern;
      draft.process.dynamic = selector.config.enable_dynamic_collection;
      draft.process.selected = (selector.config.host_pids || []).map(row => ({ ...row }));
    }
    if (selector.type === 'pid_file') draft.process.pidPath = selector.config.pid_path;
    if (selector.type === 'pid') draft.process.pids = selector.config.pids;
  }
  return draft;
}

/**
 * @description 构建采集页查询状态的默认值
 * @returns 默认查询状态
 */
export function createCollectionQueryState(): CollectionQueryState {
  return {
    tab: 'tasks',
    history: createHistoryFilters(),
    result: null,
    results: createCollectionResultsState(),
    keyword: '',
    scheduleTypes: [],
    statuses: [],
    sort: null,
    historyTaskId: null,
    historyTaskName: '',
  };
}

/**
 * @description 从序列化的查询状态恢复，逐字段做类型与取值兜底，非法值回落到默认值
 * @param value 序列化的查询状态，缺省时返回默认值
 * @returns 可直接使用的查询状态
 */
export function restoreCollectionQuery(value?: Partial<CollectionQueryState>): CollectionQueryState {
  const defaults = createCollectionQueryState();
  if (!value) return defaults;
  return {
    ...defaults,
    history: restoreHistoryFilters(value.history || { task_name: value.historyTaskName }),
    result: restoreExecutionSelection(value.result),
    results: restoreCollectionResultsState(value.results || (value.result ? { execution: value.result } : undefined)),
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

/**
 * @description 生成进程行的唯一 key，pid 缺失（预览失败）时以 error 占位
 * @param row 进程预览行
 * @returns 进程行唯一 key
 */
export const processKey = (row: ProcessRow) => `${row.bk_host_id}:${row.pid ?? 'error'}`;

/**
 * @description 组装按主机实例采集的目标配置
 * @param hosts 已选主机列表
 * @returns 采集目标配置
 */
export const collectionTarget = (hosts: CollectionHost[]) => ({
  node_type: 'INSTANCE' as const,
  nodes: hosts.map(host => ({ bk_host_id: host.host_id })),
});

/** 表单项改动后，哪些字段的旧错误提示应随之清除 */
export const ERROR_FIELDS_BY_DRAFT_KEY: Partial<Record<keyof CollectionDraft, CollectionFieldKey[]>> = {
  collectionType: ['method', 'duration_sec'],
  collector: ['duration_sec', 'frequency_hz', 'stack_unwind', 'ip_address', 'port'],
  cron: ['cron'],
  endAt: ['endAt'],
  executeAt: ['executeAt'],
  hosts: ['hosts'],
  method: ['method'],
  name: ['name'],
  process: ['process'],
  processMode: ['process'],
  scheduleType: ['scheduleType', 'executeAt', 'startAt', 'endAt', 'cron'],
  startAt: ['startAt'],
};

/** 切换类表单项（改选项而非填内容）：改动时只清除旧提示，等提交时再校验，避免切换瞬间报红 */
export const SWITCH_DRAFT_KEYS: Array<keyof CollectionDraft> = [
  'collectionType',
  'method',
  'processMode',
  'scheduleType',
];

/**
 * @description 将表单草稿转换为创建/编辑采集任务的提交载荷
 * @param draft 采集表单草稿
 * @param bizId 业务 ID
 * @param now 立即执行时的执行时间戳，默认取当前时间
 * @returns 采集任务提交载荷
 */
export function buildCollectionPayload(draft: CollectionDraft, bizId: number, now = Date.now()): CollectionPayload {
  const collector = draft.collector;
  let selector: ProcessSelector;
  if (draft.method !== 'golang') {
    const preview = buildPreviewSelector(draft);
    if (preview.type === 'command') {
      const hostIds = new Set(draft.hosts.map(host => host.host_id));
      const hostPids = collectHostPids(draft.process.selected.filter(row => hostIds.has(row.bk_host_id)));
      selector = {
        type: 'command',
        config: {
          ...preview.config,
          enable_dynamic_collection: draft.process.dynamic,
          ...(!draft.process.dynamic ? { host_pids: hostPids } : {}),
        },
      };
    } else {
      selector = preview;
    }
  }
  return {
    bk_biz_id: bizId,
    name: draft.name.trim(),
    collection_method: draft.method,
    collection_type: draft.collectionType,
    target_config: collectionTarget(draft.hosts),
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

/**
 * @description 构建进程预览用的匹配配置，命令行方式下同时作为提交时 process_selector 的基础
 * @param draft 采集表单草稿
 * @returns 进程选择配置
 * @throws {CollectionFieldError} 进程匹配条件不合法时抛出，field 固定为 process
 */
export function buildPreviewSelector(draft: CollectionDraft): PreviewSelector {
  const message = processFieldError(draft);
  if (message) throw collectionFieldError('process', message);
  const process = draft.process;
  if (draft.processMode === 'command')
    return {
      type: 'command',
      config: { match_pattern: process.matchPattern.trim(), exclude_pattern: process.excludePattern.trim() },
    };
  if (draft.processMode === 'pid_file')
    return {
      type: 'pid_file',
      config: {
        pid_path: process.pidPath
          .split(';')
          .map(value => value.trim())
          .join(';'),
      },
    };
  return {
    type: 'pid',
    config: {
      pids: process.pids
        .split(';')
        .map(value => value.trim())
        .join(';'),
    },
  };
}

/**
 * @description 从进程预览行提取可提交的主机 + PID，按主机 + PID 去重并剔除无效或预览失败的行
 * @param rows 进程预览行
 * @returns 去重后的主机 PID 列表
 */
export function collectHostPids(rows: ProcessRow[]): HostPid[] {
  const processes = new Map<string, HostPid>();
  for (const row of rows) {
    if (!Number.isInteger(row.pid) || row.pid <= 0 || row.err_msg) continue;
    processes.set(processKey(row), { bk_host_id: row.bk_host_id, pid: row.pid });
  }
  return [...processes.values()];
}

/**
 * @description 一次跑完全部提交校验，返回各字段的首条错误（文案未翻译，由调用方 t()）
 * @param draft 采集表单草稿
 * @param editing 是否为编辑态，编辑态不允许把调度方式改为立即执行
 * @param now 当前时间戳，用于校验指定执行时间
 * @returns 字段到错误文案的映射，全部合法时为空对象
 */
export function collectionFieldErrors(
  draft: CollectionDraft,
  editing: boolean,
  now = Date.now()
): Partial<Record<CollectionFieldKey, string>> {
  const errors: Partial<Record<CollectionFieldKey, string>> = {};
  const add = (field: CollectionFieldKey, message: string) => {
    errors[field] ??= message;
  };
  if (!draft.name.trim()) add('name', '请输入任务名称');
  if (!draft.hosts.length) add('hosts', '请选择目标主机');
  if (!draft.method || !draft.collectionType) add('method', '请选择采集方式和类型');
  const collector = draft.collector;
  const positive = (value: number) => Number.isFinite(value) && value > 0;
  if (draft.collectionType !== 'go_heap' && (!positive(collector.duration_sec) || collector.duration_sec > 300))
    add('duration_sec', '采集时长须大于 0 且不超过 300 秒');
  if (draft.method === 'perf') {
    if (!positive(collector.frequency_hz)) add('frequency_hz', '请输入有效的采样频率');
    if (!collector.stack_unwind) add('stack_unwind', '请选择栈展开方式');
  }
  if (draft.method === 'golang') {
    if (!collector.ip_address?.trim()) add('ip_address', '请输入采集地址');
    if (!positive(collector.port)) add('port', '请输入有效的端口');
  }
  if (draft.method !== 'golang') {
    const message = processFieldError(draft);
    if (message) add('process', message);
    else if (draft.processMode === 'command' && !draft.process.dynamic) {
      const hostIds = new Set(draft.hosts.map(host => host.host_id));
      const hostPids = collectHostPids(draft.process.selected.filter(row => hostIds.has(row.bk_host_id)));
      if (!hostPids.length) add('process', '请选择目标进程');
      else if (hostPids.length > 500) add('process', '最多选择 500 个进程');
    }
  }
  if (editing && draft.scheduleType === 'immediate') add('scheduleType', '计划任务不支持改为立即执行');
  if (draft.scheduleType === 'once_at' && (!draft.executeAt || draft.executeAt <= now))
    add('executeAt', '指定执行时间须晚于当前时间');
  if (draft.scheduleType === 'cron') {
    if (!draft.startAt) add('startAt', '请选择开始时间');
    if (!draft.endAt) add('endAt', '请选择结束时间');
    else if (draft.endAt <= now) add('endAt', '结束时间须晚于当前时间');
    else if (draft.endAt <= (draft.startAt ?? 0)) add('endAt', '结束时间须晚于开始时间');
  }
  if (draft.scheduleType === 'cron' && draft.cron.trim().split(/\s+/).length !== 5)
    add('cron', '请填写有效的五段式 Cron 表达式');
  return errors;
}

/**
 * @description 按关键字、调度方式、状态过滤采集任务，并按当前排序规则排序
 * @param tasks 采集任务列表
 * @param query 查询状态
 * @returns 过滤并排序后的任务列表
 */
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

/**
 * @description 按指定时区格式化时间戳
 * @param value 毫秒时间戳
 * @param timezone 时区
 * @returns 格式化后的时间字符串，无值时返回 --
 */
export function formatCollectionTime(value: number, timezone: string) {
  return value ? dayjs(value).tz(timezone).format('YYYY-MM-DD HH:mm:ss') : '--';
}

/**
 * @description 复用已有任务配置，生成一次立即执行的提交载荷
 * @param task 采集任务
 * @param bizId 业务 ID
 * @param now 立即执行的执行时间戳，默认取当前时间
 * @returns 采集任务提交载荷
 */
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

/**
 * @description 按当前进程匹配方式校验匹配条件，返回首条错误文案
 * @param draft 采集表单草稿
 * @returns 未翻译的错误文案，合法时为 undefined
 */
function processFieldError(draft: CollectionDraft): string | undefined {
  const process = draft.process;
  if (draft.processMode === 'command') {
    if (!process.matchPattern.trim()) return '请输入命令行匹配条件';
    return undefined;
  }
  if (draft.processMode === 'pid_file') {
    const paths = process.pidPath.split(';').map(value => value.trim());
    if (paths.some(value => !value.startsWith('/'))) return '请输入 PID 文件的绝对路径，多个路径用分号分隔';
    if (paths.length > 20) return '最多输入 20 个 PID 文件路径';
    if (paths.join(';').length > 4096) return 'PID 文件路径总长度不能超过 4096 个字符';
    return undefined;
  }
  const values = process.pids.split(';').map(value => value.trim());
  if (
    !values.length ||
    values.some(value => !/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0)
  )
    return '请输入有效的 PID，多个 PID 用分号分隔';
  if (values.length > 1000) return '最多输入 1000 个 PID';
  return undefined;
}
