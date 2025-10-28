/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { type PropType, computed, defineComponent, onMounted, provide, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { random } from 'monitor-common/utils';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';
import { storeToRefs } from 'pinia';

import { DEFAULT_TIME_RANGE } from '../../../../../components/time-range/utils';
import { createAutoTimeRange } from '../../../../../plugins/charts/failure-chart/failure-alarm-chart';
import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import { getHostSceneView } from '../../../services/alarm-detail';
import PanelHostDashboard from './components/panel-host-dashboard/panel-host-dashboard';
import PanelHostSelector from './components/panel-host-selector/panel-host-selector';

import type { AlarmDetail } from '../../../typings';
import type { IBookMark } from 'monitor-ui/chart-plugins/typings';

import './index.scss';

export default defineComponent({
  name: 'PanelHost',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
    },
  },
  setup(props) {
    /** 图表联动Id */
    const dashboardId = random(10);

    /** 业务ID */
    const { bizId } = storeToRefs(useAlarmCenterDetailStore());
    /** host 场景指标视图配置信息 */
    const hostSceneData = shallowRef<IBookMark>({ id: '', panels: [], name: '' });
    /** 是否处于请求加载状态 */
    const loading = shallowRef(false);
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');

    /** 图表数据的时间间隔 */
    const interval = computed(
      () => props.detail?.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60
    );
    /** 默认监控的目标配置 */
    const defaultCurrentTarget = computed(() => {
      const currentTarget: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
      };
      for (const item of props.detail?.dimensions ?? []) {
        if (item.key === 'bk_host_id') {
          currentTarget.bk_host_id = item.value;
        }
        if (['bk_target_ip', 'ip', 'bk_host_id'].includes(item.key)) {
          currentTarget.bk_target_ip = item.value;
        }
        if (['bk_cloud_id', 'bk_target_cloud_id', 'bk_host_id'].includes(item.key)) {
          currentTarget.bk_target_cloud_id = item.value;
        }
      }
      return currentTarget;
    });
    /** 数据时间范围 */
    const timeRange = computed(() => {
      const { startTime, endTime } = createAutoTimeRange(
        props.detail?.begin_time,
        props.detail?.end_time,
        get(interval)
      );
      return startTime && endTime ? [startTime, endTime] : DEFAULT_TIME_RANGE;
    });
    /** 图表请求参数变量 */
    const viewOptions = computed(() => ({
      method: 'AVG',
      interval: get(interval),
      group_by: [],
      current_target: get(defaultCurrentTarget),
    }));

    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);
    onMounted(() => {
      getDashboardPanels();
    });

    /**
     * @description 获取仪表盘数据数组
     */
    async function getDashboardPanels() {
      loading.value = true;
      const sceneView = await getHostSceneView(bizId.value);
      hostSceneData.value = sceneView;
      echartsConnect(dashboardId);
      loading.value = false;
    }

    /**
     * @description 跳转主机检索页面
     */
    function handleToPerformance() {
      const currentTarget = viewOptions.value?.current_target;
      const ip = currentTarget?.bk_target_ip ?? '0.0.0.0';
      const cloudId = currentTarget?.bk_target_cloud_id ?? '0';
      const bkHostId = currentTarget?.bk_host_id ?? 0;
      // 跳转至容器监控时的详情Id
      const detailId = bkHostId ? bkHostId : `${ip}-${cloudId}`;
      window.open(`${location.origin}${location.pathname}?bizId=${bizId.value}#/performance/detail/${detailId}`);
    }

    return { loading, hostSceneData, dashboardId, viewOptions, handleToPerformance };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-host'>
        <div class='panel-host-white-bg-container'>
          <div class='host-selector-wrap'>
            <PanelHostSelector class='host-selector' />
            <div
              class='host-explore-link-btn'
              onClick={this.handleToPerformance}
            >
              <span class='link-text'>{window.i18n.t('主机检索')}</span>
              <i class='icon-monitor icon-mc-goto' />
            </div>
          </div>
          <AiHighlightCard
            content='该模块哈哈哈哈哈，我是一段随意的文本占位。'
            title={`${window.i18n.t('AI 分析结论')}：`}
          />
        </div>
        <div class='panel-host-chart-wrap'>
          <PanelHostDashboard
            dashboardId={this.dashboardId}
            sceneData={this.hostSceneData}
            viewOptions={this.viewOptions}
          />
        </div>
      </div>
    );
  },
});
