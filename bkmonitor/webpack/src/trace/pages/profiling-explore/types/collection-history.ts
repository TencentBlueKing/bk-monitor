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
import type { CollectionMethod, CollectionPayload, CollectionType, ScheduleType } from './collection';

export interface CollectionCandidate {
  alias: string;
  count: number;
  value: number | string;
}

export type CollectionCandidateField = 'process_names' | 'process_pids' | 'target' | 'task_name';

export interface CollectionExecution extends CollectionExecutionKey {
  collection_method: CollectionMethod;
  collection_type: CollectionType;
  creator: string;
  duration_ms: null | number;
  execution_status: string;
  finished_at: null | number;
  hosts: { bk_host_id: number; ip: string }[];
  started_at: null | number;
  status_summary: Record<string, number>;
  target_count?: number;
  task_name: string;
}

export type CollectionExecutionAction = 'cancel' | 'rerun' | 'retry';

export interface CollectionExecutionDetail extends CollectionExecution {
  config: Omit<CollectionPayload, 'bk_biz_id' | 'collection_method' | 'collection_type' | 'name'>;
  hosts: CollectionExecutionHost[];
  total_hosts: number;
}

export interface CollectionExecutionHost {
  bk_host_id: number;
  duration_ms: null | number;
  finished_at: null | number;
  ip: string;
  message: string;
  processes: { pid: number; process_name: string }[];
  started_at: null | number;
  status: string;
}

export interface CollectionExecutionKey {
  schedule_type: ScheduleType;
  scheduled_at: number;
  task_id?: number;
}

export interface CollectionHistoryFilters {
  ips: string[];
  process_names: string[];
  process_pids: string[];
  status: string;
  task_name: string;
}
export interface CollectionResultSelection extends CollectionExecutionKey {
  bk_host_id?: number;
  finished_at: null | number;
  scope: 'execution' | 'host';
  started_at: null | number;
}
