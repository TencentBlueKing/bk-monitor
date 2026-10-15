import type { CollectionHistoryFilters, CollectionResultSelection } from './collection-history';

export interface CollectionDraft {
  collectionType: CollectionType;
  collector: CollectorConfig;
  cron: string;
  endAt: null | number;
  executeAt: null | number;
  hosts: CollectionHost[];
  method: CollectionMethod;
  name: string;
  process: ProcessDraft;
  processMode: ProcessMode;
  resourceGuard: ResourceGuardConfig;
  scheduleType: ScheduleType;
  startAt: null | number;
  timezone: string;
}
export interface CollectionHost {
  [key: string]: unknown;
  alive?: number;
  cloud_area?: { id: number; name?: string };
  host_id: number;
  ip?: string;
  ipv6?: string;
  os_name?: string;
  os_type?: string;
}
export interface CollectionMeta {
  collection_methods: CollectionMethod[];
  collection_types_by_method: Record<CollectionMethod, CollectionType[]>;
  collector_config: Record<CollectionType, CollectorConfig>;
  enabled: boolean;
  execution_status_filters?: string[];
  process_selector_types: ProcessMode[];
  resource_guard_config: ResourceGuardConfig;
  schedule?: { cron?: { cron_expression: string } };
  schedule_types: ScheduleType[];
  stack_unwinds: string[];
}
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
export type CollectionMethod = 'golang' | 'java' | 'perf';

export interface CollectionPayload {
  bk_biz_id: number;
  collection_method: CollectionMethod;
  collection_type: CollectionType;
  collector_config: CollectorConfig;
  name: string;
  process_selector?: ProcessSelector;
  resource_guard_config: ResourceGuardConfig;
  schedule: CollectionSchedule;
  target_config: CollectionTarget;
}

export interface CollectionQueryState {
  history: CollectionHistoryFilters;
  historyTaskId: null | number;
  historyTaskName: string;
  keyword: string;
  result: CollectionResultSelection | null;
  scheduleTypes: ScheduleType[];
  sort: null | { descending: boolean; sortBy: string };
  statuses: string[];
  tab: 'history' | 'results' | 'tasks';
}

export type CollectionSchedule =
  | { cron_expression: string; effective_end_at: number; effective_start_at: number; timezone: string; type: 'cron' }
  | { execute_at: number; timezone: string; type: 'immediate' | 'once_at' };

export interface CollectionTarget {
  node_type: 'INSTANCE';
  nodes: { bk_host_id: number }[];
}

export interface CollectionTask extends Omit<CollectionPayload, 'bk_biz_id'> {
  creator: string;
  deployment_status: string;
  task_id: number;
  task_status: 'disabled' | 'enabled';
  updated_at: number;
}

export type CollectionType = 'go_cpu' | 'go_heap' | 'java_allocation' | 'java_cpu' | 'native_cpu';

export interface CollectorConfig {
  duration_sec?: number;
  frequency_hz?: number;
  ip_address?: string;
  port?: number;
  stack_unwind?: string;
}

export interface HostPid {
  bk_host_id: number;
  pid: number;
}

export type PreviewSelector =
  | { config: { exclude_pattern: string; match_pattern: string }; type: 'command' }
  | { config: { pid_path: string }; type: 'pid_file' }
  | { config: { pids: string }; type: 'pid' };

export interface ProcessDraft {
  dynamic: boolean;
  excludePattern: string;
  matchPattern: string;
  pidPath: string;
  pids: string;
  selected: ProcessRow[];
}

export type ProcessMode = 'command' | 'pid' | 'pid_file';

export interface ProcessPreview {
  columns: { field: string; name: string; type: string }[];
  data: ProcessRow[];
}

export interface ProcessRow {
  bk_host_id: number;
  command?: string;
  err_msg?: string;
  ip?: string;
  pid?: number;
  process_name?: string;
  started_at?: number;
}

export type ProcessSelector =
  | {
      config: {
        enable_dynamic_collection: boolean;
        exclude_pattern: string;
        host_pids?: HostPid[];
        match_pattern: string;
      };
      type: 'command';
    }
  | { config: { pid_path: string }; type: 'pid_file' }
  | { config: { pids: string }; type: 'pid' };

export interface ResourceGuardConfig {
  auto_stop_on_resource_pressure: boolean;
  max_disk_usage: number;
  min_mem_level: number;
}

export type ScheduleType = 'cron' | 'immediate' | 'once_at';
