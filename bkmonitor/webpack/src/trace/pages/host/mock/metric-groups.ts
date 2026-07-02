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
import { type MetricGroupModel, type MetricItemModel, UNGROUP_ID } from '../types/metric-group';

/** 指标分组（mock） */
export const MOCK_METRIC_GROUPS: MetricGroupModel[] = [
  { id: 'cpu', title: 'CPU' },
  { id: 'network', title: '网络' },
  { id: 'disk', title: '磁盘' },
  { id: 'process', title: '系统进程' },
];

/** 指标列表（mock）。order 即数组顺序，hidden 表示显示开关关闭。 */
export const MOCK_METRICS: MetricItemModel[] = [
  { groupId: 'cpu', hidden: false, id: 'mem_free', title: '物理内存空闲量' },
  { groupId: 'network', hidden: false, id: 'swap_used', title: 'SWAP 已用量' },
  { groupId: 'cpu', hidden: false, id: 'mem_usage', title: '物理内存已用占比' },
  { groupId: 'cpu', hidden: false, id: 'mem_used', title: '物理内存已用量' },
  { groupId: 'network', hidden: false, id: 'app_mem_used', title: '应用程序内存使用量' },
  { groupId: 'cpu', hidden: false, id: 'swap_usage', title: 'SWAP 已用占比' },
  { groupId: 'network', hidden: true, id: 'mem_cached', title: '内存 cached 大小' },
  { groupId: 'cpu', hidden: true, id: 'app_mem_free', title: '应用程序内存可用率' },
  { groupId: 'network', hidden: true, id: 'shared_mem_used', title: '共享内存使用量' },
  { groupId: 'network', hidden: true, id: 'mem_total', title: '物理内存总大小' },
  { groupId: 'disk', hidden: false, id: 'disk_usage', title: '磁盘空间使用率' },
  { groupId: 'disk', hidden: false, id: 'disk_io_util', title: '磁盘 IO 使用率' },
  { groupId: 'disk', hidden: true, id: 'disk_read_bytes', title: '磁盘读速率' },
  { groupId: 'process', hidden: false, id: 'process_count', title: '进程数' },
  { groupId: 'process', hidden: true, id: 'process_cpu', title: '进程 CPU 使用率' },
  { groupId: UNGROUP_ID, hidden: false, id: 'cpu_usage', title: 'CPU 使用率' },
  { groupId: UNGROUP_ID, hidden: false, id: 'load5', title: '5 分钟平均负载' },
  { groupId: UNGROUP_ID, hidden: true, id: 'load15', title: '15 分钟平均负载' },
];
