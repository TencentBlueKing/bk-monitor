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
import { type PropType, computed, defineComponent, shallowRef, toRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
// import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import AlarmDashboardGroup from '../../../components/alarm-dashboard-group/alarm-dashboard-group';
import { useAlertHost } from '../../../composables/use-alert-host';
import { useHostSceneView } from '../../../composables/use-host-scene-view';
import PanelHostSelector from './components/panel-host-selector/panel-host-selector';

import type { IDataQuery } from '../../../../../plugins/typings';
import type { DateValue } from '@blueking/date-picker';

import './index.scss';

export default defineComponent({
  name: 'PanelHost',
  props: {
    /** 告警ID */
    alertId: String as PropType<string>,
  },
  setup(props) {
    const { bizId, interval, timeRange } = storeToRefs(useAlarmCenterDetailStore());
    const { currentTarget, targetList, loading } = useAlertHost(toRef(props, 'alertId'));
    const { hostDashboards, loading: sceneViewLoading } = useHostSceneView(bizId);
    /** 图表执行 dataZoom 框线缩放后的时间范围 */
    const dataZoomTimeRange = shallowRef<DateValue>(null);
    /** 当前图表视图的时间范围 */
    const viewerTimeRange = computed<DateValue>(() => get(dataZoomTimeRange) ?? get(timeRange));
    /** 图表请求参数变量 */
    const viewOptions = computed(() => {
      const target = {
        bk_target_cloud_id: get(currentTarget)?.bk_cloud_id,
        bk_target_ip: get(currentTarget)?.bk_target_ip,
      };
      return {
        method: 'AVG',
        interval: get(interval),
        group_by: [],
        current_target: target,
        ip: target?.bk_target_ip,
        bk_cloud_id: target?.bk_target_cloud_id,
        ...target,
      };
    });
    /**
     * @description: 获取跳转url
     * @param {string} hash hash值
     * @param {number} bizId 业务ID
     * @return {*}
     */
    const commOpenUrl = (hash: string, bizId?: number) => {
      let url = '';
      if (process.env.NODE_ENV === 'development') {
        url = `${process.env.proxyUrl}?bizId=${bizId || window.cc_biz_id}${hash}`;
      } else {
        url = location.href.replace(location.hash, hash);
      }
      return url;
    };

    /**
     * @description: 格式化图表数据
     * @param {any} data 图表接口返回的series数据
     */
    const formatterData = (data: any, target: IDataQuery) => {
      return {
        ...data,
        query_config: data?.query_config || target.data,
        series: data.series.map(item => {
          return {
            ...item,
            alias: item?.dimensions?.device_name || item.target,
          };
        }),
      };
    };

    /**
     * @description 跳转主机检索页面
     */
    const handleToPerformance = () => {
      const target = get(currentTarget);
      const ip = target?.bk_target_ip ?? '0.0.0.0';
      const cloudId = target?.bk_cloud_id ?? '0';
      const bkHostId = target?.bk_host_id ?? 0;
      // 跳转至容器监控时的详情Id
      const detailId = bkHostId ? bkHostId : `${ip}-${cloudId}`;
      const url = commOpenUrl(`#/performance/detail/${detailId}`, get(bizId));
      // TODO : 待确认 跳转至主机监控时的路径参数
      // 模块级别 ?filter-bk_inst_id=190&filter-bk_obj_id=module
      // 主机级别 ?filter-bk_target_ip=10.0.7.4&filter-bk_target_cloud_id=0&filter-bk_host_id=8
      window.open(url);
    };

    /**
     * @description 数据时间间隔 值改变后回调
     * @param {[number, number]} e
     */
    const handleDataZoomTimeRangeChange = (e?: [number, number]) => {
      if (!e?.[0] || !e?.[1]) {
        dataZoomTimeRange.value = null;
        return;
      }
      dataZoomTimeRange.value = e;
    };

    /**
     * @description 创建骨架屏 dom 元素
     */
    const createSkeletonDom = () => {
      return <div class='alarm-detail-panel-host-skeleton-dom skeleton-element' />;
    };

    watch(
      () => get(currentTarget),
      () => {
        handleDataZoomTimeRangeChange();
      }
    );

    return {
      bizId,
      currentTarget,
      sceneViewLoading,
      hostDashboards,
      targetList,
      dataZoomTimeRange,
      viewerTimeRange,
      loading,
      viewOptions,
      createSkeletonDom,
      formatterData,
      handleToPerformance,
      handleDataZoomTimeRangeChange,
    };
  },
  render() {
    return (
      <div class={['alarm-center-detail-panel-host', this.loading ? 'is-loading' : '']}>
        <div class='panel-host-white-bg-container'>
          <div class='host-selector-wrap'>
            <div class='host-selector-container'>
              <PanelHostSelector
                currentTarget={this.currentTarget}
                targetList={this.targetList}
                onChange={target => {
                  this.currentTarget = target;
                }}
              />
              {this.createSkeletonDom()}
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
            {/* <AiHighlightCard
              content='该模块哈哈哈哈哈，我是一段随意的文本占位。'
              title={`${window.i18n.t('AI 分析结论')}：`}
            /> */}
            {this.createSkeletonDom()}
          </div>
        </div>
        <div class='panel-host-chart-wrap'>
          <AlarmDashboardGroup
            customOptions={{
              formatterData: this.formatterData,
            }}
            params={{
              bk_biz_id: this.bizId,
            }}
            dashboards={this.hostDashboards}
            loading={this.sceneViewLoading}
            showRestore={!!this.dataZoomTimeRange}
            timeRange={this.viewerTimeRange}
            viewOptions={this.viewOptions}
            onDataZoomChange={this.handleDataZoomTimeRangeChange}
            onRestore={this.handleDataZoomTimeRangeChange}
          />
        </div>
      </div>
    );
  },
});
