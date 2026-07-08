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

import { type PropType, computed, defineComponent, provide, shallowRef } from 'vue';

import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import { useMetricAggregation } from '../../composables/use-metric-aggregation';
import { useMetricGroups } from '../../composables/use-metric-groups';
import { MOCK_COMPARE_TARGETS, MOCK_CURRENT_TARGET } from '../../mock/aggregation';
import { buildScopedVars, DashboardPanel, useDashboardPanels } from '../dashbords';
import GroupManageDialog from './group-manage-dialog';
import MetricToolbar from './metric-toolbar';
import { useHostStore } from '@/store/modules/host';

import type { IHostTopoTreeNode, MetricCompareType } from '../../types';
import type { MetricGroupModel, MetricItemModel } from '../../types/metric-group';

import './host-metric.scss';

export default defineComponent({
  name: 'HostMetric',
  props: {
    selectedNode: {
      type: Object as PropType<IHostTopoTreeNode | null>,
      default: null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    // 汇聚状态：由本容器持有，向 Toolbar（受控）与图表（props）统一分发
    const aggregation = useMetricAggregation();
    // 分组与指标数据：图表渲染与「视图分组管理」的单一数据源
    const groupsCtrl = useMetricGroups();

    // 是否选中的是主机或者是服务实例
    const isCheckedHost = computed(() => {
      return 'bk_host_id' in props.selectedNode;
    });

    /** 可选的对比类型 */
    const compareListEnable = computed<MetricCompareType[]>(() => {
      if (isCheckedHost.value) return ['none', 'target', 'time'];
      return ['none', 'time'];
    });

    // 向下游图表（useEcharts）提供时间范围与刷新信号
    const { timeRange, refreshImmediate } = storeToRefs(useHostStore());
    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);
    provide('viewOptions', aggregation.viewOptions);

    // 变量取值：仅请求态字段变化才会触发图表重新取数
    const scopedVars = computed(() => buildScopedVars(aggregation.state, MOCK_CURRENT_TARGET));

    // 仪表盘分组行：按分组聚合、显隐与关键字过滤
    const { rows } = useDashboardPanels({
      groups: () => groupsCtrl.groups.value,
      metrics: () => groupsCtrl.metrics.value,
      keyword: () => aggregation.state.keyword,
      ungroupTitle: () => t('未分组'),
    });

    const settingShow = shallowRef(false);

    const handleSave = (groups: MetricGroupModel[], metrics: MetricItemModel[]) => {
      groupsCtrl.setData(groups, metrics);
    };

    return () => (
      <div class='host-metric'>
        <MetricToolbar
          compareListEnable={compareListEnable.value}
          currentTarget={MOCK_CURRENT_TARGET}
          targetList={MOCK_COMPARE_TARGETS}
          value={aggregation.state}
          onChange={aggregation.updateState}
          onOpenSetting={() => (settingShow.value = true)}
        />
        <DashboardPanel
          class='host-metric__charts'
          columns={aggregation.state.columns}
          rows={rows.value}
          scopedVars={scopedVars.value}
        />
        <GroupManageDialog
          groups={groupsCtrl.groups.value}
          isShow={settingShow.value}
          metrics={groupsCtrl.metrics.value}
          onSave={handleSave}
          onUpdate:isShow={(v: boolean) => (settingShow.value = v)}
        />
      </div>
    );
  },
});
