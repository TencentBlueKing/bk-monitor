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
import { shallowRef } from 'vue';

import { updateSceneView } from 'monitor-api/modules/scene_view';
import { useI18n } from 'vue-i18n';

import { getProcessMetricGroupPanelOrderApi, getProcessViewsPanelsApi } from '../services/graph-service';

import type { DashboardRow } from '../components/dashbords';
import type { HostViewsRowPanel, MetricGroupPanelOrder } from '../types';

export type ProcessMetricController = ReturnType<typeof useProcessMetric>;
interface UseProcessMetricOptions {
  /** 关键字过滤（按指标标题） */
  keyword: MaybeRefOrGetter<string>;
  /** 未分组标题（i18n 文案由调用方传入） */
  ungroupTitle: MaybeRefOrGetter<string>;
}

/**
 * 进程指标视图数据控制器。
 * 持有后端返回的 DashboardRow[]（展示用）与 MetricGroupPanelOrder[]（管理用）。
 */
export function useProcessMetric(options: UseProcessMetricOptions) {
  const { t } = useI18n();
  const loading = shallowRef(false);
  /** 后端返回的原始面板分组数据（getProcessViewsPanelsApi） */
  const panels = shallowRef<HostViewsRowPanel[]>([]);
  /** 后端返回的分组与指标排序配置（getProcessMetricGroupPanelOrderApi，供 GroupManageDialog 使用） */
  const orderData = shallowRef<MetricGroupPanelOrder[]>([]);

  const load = async (needCache = true) => {
    loading.value = true;
    try {
      const [panelsRes, orderRes] = await Promise.all([
        getProcessViewsPanelsApi(),
        getProcessMetricGroupPanelOrderApi(needCache),
      ]);
      panels.value = panelsRes;
      orderData.value = orderRes;
    } finally {
      loading.value = false;
    }
  };

  /** 保存 */
  const handleSave = async (value: MetricGroupPanelOrder[]) => {
    try {
      loading.value = true;
      await updateSceneView({
        scene_id: 'host',
        type: 'detail',
        id: 'process',
        name: t('进程'),
        config: {
          order: value,
        },
      });
      await load(false);
    } finally {
      loading.value = false;
    }
  };

  /** 恢复默认 */
  const handleReset = async () => {
    try {
      loading.value = true;
      await updateSceneView({
        scene_id: 'host',
        type: 'detail',
        id: 'process',
        name: t('进程'),
        config: {
          order: [],
        },
      });
      await load(false);
    } finally {
      loading.value = false;
    }
  };

  /** 仪表盘分组行：仅按关键字过滤面板，空分组不展示 */
  const rows = computed<DashboardRow[]>(() => {
    const keyword = toValue(options.keyword).trim().toLowerCase();

    const result: DashboardRow[] = [];
    for (const row of panels.value) {
      const filteredPanels = keyword
        ? row.panels.filter(panel => panel.title.toLowerCase().includes(keyword))
        : row.panels;

      if (filteredPanels.length) {
        result.push({
          id: row.id,
          title: row.title,
          panels: filteredPanels,
        });
      }
    }

    return result;
  });

  return {
    rows,
    orderData,
    loading,
    handleSave,
    handleReset,
    load,
  };
}
