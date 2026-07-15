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

import { cloneDeep } from 'lodash';

import { UNGROUP_ID } from '../types/metric-group';
import { HostViewsPanelType } from '../types/panels';
import { MOCK_METRIC_GROUPS, MOCK_METRICS } from './metric-groups';
import { panel as PANEL_TEMPLATE } from './panel';

import type { MetricItemModel } from '../types/metric-group';
import type { MetricGroupPanelOrder } from '../types/panel-order';
import type { HostViewsGraphPanel, HostViewsRowPanel } from '../types/panels';

/**
 * 进程指标视图本期复用「系统指标」的分组与指标 mock，使图表展示与系统指标一致。
 * 分组顺序：自定义分组在前、未分组固定置底（与仪表盘渲染顺序保持一致）。
 */
const orderedGroups: { id: string; title: string }[] = [
  ...MOCK_METRIC_GROUPS,
  { id: UNGROUP_ID, title: '未分组的指标' },
];

/** 取某分组下的指标（保持 MOCK_METRICS 原始顺序，即展示顺序） */
const metricsOfGroup = (groupId: string): MetricItemModel[] => MOCK_METRICS.filter(metric => metric.groupId === groupId);

/** 进程图表面板 id 约定：`process.{指标 id}`，作为 panel 与 order 的关联键 */
export const toProcessPanelId = (metricId: string): string => `process.${metricId}`;

/** 以单个指标为模板生成进程图表面板 JSON（含 $变量占位符） */
const createProcessGraphPanel = (metric: MetricItemModel): HostViewsGraphPanel =>
  ({
    ...cloneDeep(PANEL_TEMPLATE),
    id: toProcessPanelId(metric.id),
    title: metric.title,
    subTitle: `system.${metric.id}`,
    type: HostViewsPanelType.Graph,
  }) as HostViewsGraphPanel;

/** @description 进程视图面板 mock（按分组聚合的图表面板） */
export const getMockProcessViewsPanels = (): HostViewsRowPanel[] =>
  orderedGroups
    .map(group => ({
      id: group.id,
      title: group.title,
      type: HostViewsPanelType.Row,
      panels: metricsOfGroup(group.id).map(createProcessGraphPanel),
    }))
    .filter(group => group.panels.length > 0);

/** @description 进程指标分组面板排序配置 mock（分组 + 指标顺序 + 显隐） */
export const getMockProcessMetricGroupPanelOrder = (): MetricGroupPanelOrder[] =>
  orderedGroups
    .map(group => ({
      id: group.id,
      title: group.title,
      panels: metricsOfGroup(group.id).map(metric => ({
        id: metric.id,
        title: metric.title,
        hidden: metric.hidden,
      })),
    }))
    .filter(group => group.panels.length > 0);
