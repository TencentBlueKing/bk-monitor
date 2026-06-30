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

import { type MaybeRefOrGetter, computed, ref as deepRef, shallowRef, toValue } from 'vue';

import { toProcessPanelId } from '../mock/process-metric';
import { getProcessMetricGroupPanelOrder, getProcessViewsPanels } from '../services/graph-service';
import { UNGROUP_ID } from '../types/metric-group';

import type { MetricGroupModel, MetricItemModel } from '../types/metric-group';
import type { HostViewsGraphPanel } from '../types/panels';
import type { DashboardRow } from '../components/dashbords';

interface UseProcessMetricOptions {
  /** 关键字过滤（按指标标题） */
  keyword: MaybeRefOrGetter<string>;
  /** 未分组标题（i18n 文案由调用方传入） */
  ungroupTitle: MaybeRefOrGetter<string>;
}

/**
 * 进程指标视图数据控制器。
 * 取数走带缓存的 `getProcessViewsPanels`（图表面板）与 `getProcessMetricGroupPanelOrder`（分组/顺序/显隐）：
 * - 由「排序配置」派生分组与指标，供 Toolbar 搜索、视图分组管理消费；
 * - 由「视图面板」提供图表 JSON，按分组顺序与显隐拼装仪表盘行。
 */
export function useProcessMetric(options: UseProcessMetricOptions) {
  const loading = shallowRef(false);
  /** 分组（不含「未分组」，与系统指标一致由渲染时置底） */
  const groups = deepRef<MetricGroupModel[]>([]);
  /** 指标（含「未分组」归属，order 即展示顺序） */
  const metrics = deepRef<MetricItemModel[]>([]);
  /** 指标 id → 图表面板 JSON 映射 */
  const panelMap = shallowRef<Record<string, HostViewsGraphPanel>>({});

  /** 仅首次拉取构建一次（service 层已做缓存，这里避免重复拼装） */
  let loaded = false;

  const load = async () => {
    if (loaded) return;
    loading.value = true;
    try {
      const [panels, order] = await Promise.all([getProcessViewsPanels(), getProcessMetricGroupPanelOrder()]);
      const nextPanelMap: Record<string, HostViewsGraphPanel> = {};
      for (const row of panels) {
        for (const panel of row.panels) {
          nextPanelMap[panel.id] = panel;
        }
      }
      panelMap.value = nextPanelMap;
      groups.value = order.filter(group => group.id !== UNGROUP_ID).map(group => ({ id: group.id, title: group.title }));
      metrics.value = order.flatMap(group =>
        group.panels.map(panel => ({ groupId: group.id, id: panel.id, title: panel.title, hidden: panel.hidden }))
      );
      loaded = true;
    } finally {
      loading.value = false;
    }
  };

  /** 覆盖写入分组与指标（供「视图分组管理」保存） */
  const setData = (nextGroups: MetricGroupModel[], nextMetrics: MetricItemModel[]) => {
    groups.value = nextGroups;
    metrics.value = nextMetrics;
  };

  /** 仪表盘分组行：按分组聚合可见且命中关键字的指标，未分组置底，空分组不展示 */
  const rows = computed<DashboardRow[]>(() => {
    const keyword = toValue(options.keyword).trim().toLowerCase();
    const matchKeyword = (metric: MetricItemModel) => !keyword || metric.title.toLowerCase().includes(keyword);

    const groupedMetrics = new Map<string, MetricItemModel[]>();
    for (const metric of metrics.value) {
      if (metric.hidden || !matchKeyword(metric)) continue;
      const list = groupedMetrics.get(metric.groupId) ?? [];
      list.push(metric);
      groupedMetrics.set(metric.groupId, list);
    }

    const orderedGroups: MetricGroupModel[] = [
      ...groups.value,
      { id: UNGROUP_ID, title: toValue(options.ungroupTitle) },
    ];

    return orderedGroups.reduce<DashboardRow[]>((rowList, group) => {
      const groupMetrics = groupedMetrics.get(group.id);
      if (groupMetrics?.length) {
        rowList.push({
          id: group.id,
          title: group.title,
          panels: groupMetrics
            .map(metric => panelMap.value[toProcessPanelId(metric.id)])
            .filter((panel): panel is HostViewsGraphPanel => Boolean(panel)),
        });
      }
      return rowList;
    }, []);
  });

  return {
    loading,
    groups,
    metrics,
    rows,
    load,
    setData,
  };
}
