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
import { type PropType, defineComponent, toRef } from 'vue';

import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import AlarmDashboardGroup from '../../../components/alarm-dashboard-group/alarm-dashboard-group';
import { useAlertK8s } from '../../../composables/use-alert-k8s';
import { useK8sChartPanel } from '../../../composables/use-k8s-chart-panel';
import K8SCustomChart from './components/k8s-custom-chart/k8s-custom-chart';
import K8sSceneSelector from './components/k8s-scene-selector/k8s-scene-selector';
import K8sTargetSelector from './components/k8s-target-selector/k8s-target-selector';

import './index.scss';

export default defineComponent({
  name: 'PanelK8s',
  props: {
    /** 告警ID */
    alertId: String as PropType<string>,
  },
  setup(props) {
    const { timeRange, bizId } = storeToRefs(useAlarmCenterDetailStore());
    const { scene, currentTarget, sceneList, targetList, groupBy, loading } = useAlertK8s(toRef(props, 'alertId'));
    /** 需要渲染的仪表盘面板配置数组 */
    const { dashboards, loading: k8sDashboardLoading } = useK8sChartPanel({
      scene,
      groupBy,
      currentTarget,
      bizId,
    });

    /**
     * @description 跳转容器监控页面
     */
    const handleToK8s = v => {
      console.log('================ v ================', v);
    };
    /**
     * @description 创建骨架屏 dom 元素
     */
    function createSkeletonDom() {
      return <div class='alarm-detail-panel-k8s-skeleton-dom skeleton-element' />;
    }

    return {
      scene,
      currentTarget,
      sceneList,
      targetList,
      groupBy,
      loading,
      k8sDashboardLoading,
      dashboards,
      timeRange,
      handleToK8s,
      createSkeletonDom,
    };
  },
  render() {
    return (
      <div class={['alarm-center-detail-panel-k8s', this.loading ? 'is-loading' : '']}>
        <div class='panel-k8s-white-bg-container'>
          <div class='k8s-selector-wrap'>
            <div class='k8s-selector-container'>
              <K8sTargetSelector
                currentTarget={this.currentTarget}
                groupBy={this.groupBy}
                targetList={this.targetList}
                onChange={target => {
                  this.currentTarget = target;
                }}
              />
              {this.createSkeletonDom()}
            </div>
            <div
              class='k8s-link-btn'
              onClick={this.handleToK8s}
            >
              <span class='link-text'>{window.i18n.t('容器监控')}</span>
              <i class='icon-monitor icon-mc-goto' />
            </div>
          </div>
          <div class='ai-hight-card-wrap'>
            <AiHighlightCard
              content={`tE monitor_web，incident，resources, fronted_resources. IncidentHandlersResource 这个 span 中，发生了一个类型为 TypeError 的异常。异常信息为'<' not supported between instances of 'str' and 'int'. 这表明在代表中存在一个比较操作。试图将字符串和整数进行比较，导致了类型错误。`}
              title={`${window.i18n.t('AI 分析结论')}：`}
            />
            {this.createSkeletonDom()}
          </div>
          <div class='k8s-scene-selector-wrap'>
            <K8sSceneSelector
              scene={this.scene}
              sceneList={this.sceneList}
              onSceneChange={v => {
                this.scene = v;
              }}
            />
            {this.createSkeletonDom()}
          </div>
        </div>
        <div class='panel-k8s-chart-wrap'>
          <AlarmDashboardGroup
            viewOptions={{
              interval: 'auto',
              method: 'sum',
              unit: undefined,
              time_shift: ' ',
            }}
            dashboards={this.dashboards}
            loading={this.k8sDashboardLoading}
            timeRange={this.timeRange}
          >
            {{
              customBaseChart: renderContext => <K8SCustomChart {...renderContext} />,
            }}
          </AlarmDashboardGroup>
        </div>
      </div>
    );
  },
});
