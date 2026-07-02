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

import { type MaybeRefOrGetter, computed, toValue } from 'vue';

import { cloneDeep } from 'lodash';

import { panel as PANEL_TEMPLATE } from '../../../mock/panel';
import { UNGROUP_ID } from '../../../types/metric-group';

import type { MetricGroupModel, MetricItemModel } from '../../../types/metric-group';
import type { HostViewsGraphPanel } from '../../../types/panels';
import type { DashboardRow } from '../typings/dashboard';

interface UseDashboardPanelsOptions {
  /** 分组定义 */
  groups: MaybeRefOrGetter<MetricGroupModel[]>;
  /** 关键字过滤（按指标标题） */
  keyword: MaybeRefOrGetter<string>;
  /** 指标列表（含分组归属、显隐） */
  metrics: MaybeRefOrGetter<MetricItemModel[]>;
  /** 未分组标题（i18n 文案由调用方传入） */
  ungroupTitle: MaybeRefOrGetter<string>;
}

/**
 * 由「分组 + 指标」数据构建仪表盘分组行：
 * - 按分组定义顺序排列，未分组固定置底；
 * - 仅展示「可见」指标（hidden=false）；
 * - 关键字按指标标题过滤；
 * - 过滤后为空的分组不展示。
 *
 * 分组与显隐数据是图表渲染与「视图分组管理」的单一数据源。
 */
export function useDashboardPanels(options: UseDashboardPanelsOptions) {
  const rows = computed<DashboardRow[]>(() => {
    const groups = toValue(options.groups);
    const metrics = toValue(options.metrics);
    const keyword = toValue(options.keyword).trim().toLowerCase();
    const ungroupTitle = toValue(options.ungroupTitle);

    const matchKeyword = (metric: MetricItemModel) => !keyword || metric.title.toLowerCase().includes(keyword);

    /** 按分组聚合可见且命中关键字的指标，保留指标原数组顺序 */
    const groupedMetrics = new Map<string, MetricItemModel[]>();
    for (const metric of metrics) {
      if (metric.hidden || !matchKeyword(metric)) continue;
      const list = groupedMetrics.get(metric.groupId) ?? [];
      list.push(metric);
      groupedMetrics.set(metric.groupId, list);
    }

    const orderedGroups: MetricGroupModel[] = [...groups, { id: UNGROUP_ID, title: ungroupTitle }];

    return orderedGroups.reduce<DashboardRow[]>((rowList, group) => {
      const groupMetrics = groupedMetrics.get(group.id);
      if (groupMetrics?.length) {
        rowList.push({
          id: group.id,
          title: group.title,
          panels: groupMetrics.map(createGraphPanel),
        });
      }
      return rowList;
    }, []);
  });

  return { rows };
}

/**
 * 以单个指标为模板生成图表面板 JSON（含 $变量占位符）。
 * 当前取数为 mock，target 仅做标题/副标题的展示性替换。
 */
function createGraphPanel(metric: MetricItemModel): HostViewsGraphPanel {
  return {
    ...cloneDeep(PANEL_TEMPLATE),
    id: `host.${metric.id}`,
    title: metric.title,
    subTitle: `system.${metric.id}`,
  } as HostViewsGraphPanel;
}
