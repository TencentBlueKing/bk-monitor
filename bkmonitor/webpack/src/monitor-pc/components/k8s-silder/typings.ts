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

import type { IWhere } from '../../pages/monitor-k8s/typings';
import type { K8sNewTabEnum, SceneEnum } from '../../pages/monitor-k8s/typings/k8s-new';
import type { EMode } from '../retrieval-filter/utils';
import type { TimeRangeType } from '../time-range/time-range';

export interface IBcsClusterItem {
  event_table_id?: string;
  id: string;
  name: string;
}

/** 容器监控视图的初始状态，由调用方（路由页 / 侧滑）解析 URL 后传入 */
export interface K8sMonitorInitialParams {
  activeTab?: K8sNewTabEnum;
  cluster?: string;
  filterBy?: Record<string, string[]>;
  /** 事件场景：UI 模式 / 语句模式 */
  filterMode?: EMode;
  groupBy?: string[];
  /** 事件场景：语句模式检索语句 */
  queryString?: string;
  refreshInterval?: number;
  scene?: SceneEnum;
  timeRange?: TimeRangeType;
  /** 事件场景：UI 模式检索条件 */
  where?: IWhere[];
}

/** 容器监控视图对外抛出的完整状态快照，调用方据此回写 URL */
export type K8sMonitorState = Required<K8sMonitorInitialParams>;

/** 状态变更事件载荷，extra 透传表格排序等不属于视图状态的附加 query */
export interface K8sMonitorStateChangeEvent {
  extra: Record<string, any>;
  state: K8sMonitorState;
}

/** parseK8sMonitorUrl 的解析结果 */
export interface K8sMonitorUrlParseResult {
  /** URL 中携带的业务 id，仅作信息透出，不参与是否侧滑的判断 */
  bizId: string;
  /** 链接是否指向容器监控 */
  isK8sMonitor: boolean;
  params: K8sMonitorInitialParams;
}
