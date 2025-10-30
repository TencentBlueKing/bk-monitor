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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import PanelHostDashboard from './components/panel-host-dashboard/panel-host-dashboard';
import PanelHostSelector from './components/panel-host-selector/panel-host-selector';

import type { AlarmDetail } from '../../../typings';

import './index.scss';

export default defineComponent({
  name: 'PanelHost',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
    },
  },
  setup(props) {
    const {
      /** 业务ID */
      bizId,
      /** 图表数据的时间间隔 */
      interval,
      /** 数据时间范围 */
      timeRange,
    } = storeToRefs(useAlarmCenterDetailStore());
    /** 是否处于请求加载状态 */
    const loading = shallowRef(false);

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
    /** 图表请求参数变量 */
    const viewOptions = computed(() => {
      const currentTarget = get(defaultCurrentTarget);
      return {
        method: 'AVG',
        interval: get(interval),
        group_by: [],
        current_target: currentTarget,
        ip: currentTarget?.bk_target_ip,
        bk_cloud_id: currentTarget?.bk_target_cloud_id,
        ...currentTarget,
      };
    });

    /**
     * @description 跳转主机检索页面
     */
    function handleToPerformance() {
      const currentTarget = get(defaultCurrentTarget);
      const ip = currentTarget?.bk_target_ip ?? '0.0.0.0';
      const cloudId = currentTarget?.bk_target_cloud_id ?? '0';
      const bkHostId = currentTarget?.bk_host_id ?? 0;
      // 跳转至容器监控时的详情Id
      const detailId = bkHostId ? bkHostId : `${ip}-${cloudId}`;
      // TODO : 待确认 跳转至主机监控时的路径参数
      // 模块级别 ?filter-bk_inst_id=190&filter-bk_obj_id=module
      // 主机级别 ?filter-bk_target_ip=10.0.7.4&filter-bk_target_cloud_id=0&filter-bk_host_id=8
      window.open(`${location.origin}${location.pathname}?bizId=${bizId.value}#/performance/detail/${detailId}`);
    }

    /**
     * @description 创建骨架屏 dom 元素
     */
    function createSkeletonDom() {
      return <div class='alarm-detail-panel-host-skeleton-dom skeleton-element' />;
    }

    return { bizId, timeRange, loading, viewOptions, handleToPerformance, createSkeletonDom };
  },
  render() {
    return (
      <div class={['alarm-center-detail-panel-host', this.loading ? 'is-loading' : '']}>
        <div class='panel-host-white-bg-container'>
          <div class='host-selector-wrap'>
            <div class='host-selector-container'>
              <PanelHostSelector class='host-selector' />
              {/* {this.createSkeletonDom()} */}
            </div>
            <div
              class='host-explore-link-btn'
              onClick={this.handleToPerformance}
            >
              <span class='link-text'>{window.i18n.t('主机检索')}</span>
              <i class='icon-monitor icon-mc-goto' />
            </div>
          </div>
          <div class='ai-hight-card-wrap'>
            <AiHighlightCard
              content='该模块哈哈哈哈哈，我是一段随意的文本占位。'
              title={`${window.i18n.t('AI 分析结论')}：`}
            />
            {/* {this.createSkeletonDom()} */}
          </div>
        </div>
        <div class='panel-host-chart-wrap'>
          <PanelHostDashboard
            bizId={this.bizId}
            timeRange={this.timeRange}
            viewOptions={this.viewOptions}
          />
        </div>
      </div>
    );
  },
});
