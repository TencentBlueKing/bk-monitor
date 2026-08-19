/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent. All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { IHostMetricInfo } from './host';

export const HOST_METRIC_SNAPSHOT_SECTIONS = [
  'agent_status',
  'performance_data',
  'process_status',
  'alarm_count',
] as const;

export type HostMetricProgressiveState = 'DEGRADED' | 'EXPIRED' | 'FAILED' | 'READY' | 'RUNNING' | 'UNAVAILABLE';
export type HostMetricSnapshotSectionName = (typeof HOST_METRIC_SNAPSHOT_SECTIONS)[number];

export interface IHostMetricSnapshotPollQuery extends IHostMetricSnapshotQuery {
  sinceRevision: number;
  snapshotId: string;
}

export interface IHostMetricSnapshotQuery {
  bkBizId: number | string;
  bkHostId?: number;
  bkInstId?: number;
  bkObjId?: string;
  endTime: number;
  startTime: number;
}

export interface IHostMetricSnapshotResult {
  canonicalEndTime: number;
  canonicalStartTime: number;
  expired: boolean;
  failedSections: HostMetricSnapshotSectionName[];
  hostCount: number;
  hostIdsHash: string;
  partialSections: HostMetricSnapshotSectionName[];
  retryAfterMs?: number;
  revision: number;
  sections: IHostMetricSnapshotSection[];
  snapshotId?: string;
  status: HostMetricProgressiveState;
}

export interface IHostMetricSnapshotSection {
  data: Record<string, Partial<IHostMetricInfo>>;
  name: HostMetricSnapshotSectionName;
}

/**
 * 主机指标快照的前端领域契约。具体 HTTP 路由和响应字段只允许在 service adapter 中转换，
 * Controller 与组件不依赖后端传输格式。
 */
export interface IHostMetricSnapshotService {
  create: (params: IHostMetricSnapshotQuery) => Promise<IHostMetricSnapshotResult>;
  hashHostIds: (hostIds: number[]) => Promise<string>;
  poll: (params: IHostMetricSnapshotPollQuery) => Promise<IHostMetricSnapshotResult>;
}
