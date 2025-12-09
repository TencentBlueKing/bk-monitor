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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { SceneEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';
import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import K8sSceneSelector from './components/k8s-scene-selector/k8s-scene-selector';
import PanelContainerDashboard from './components/panel-container-dashboard/panel-container-dashboard';

import './index.scss';

export default defineComponent({
  name: 'PanelContainer',
  props: {
    id: String as PropType<string>,
  },
  setup(_props) {
    /** 场景 */
    const scene = shallowRef<SceneEnum>(SceneEnum.Performance);
    const {
      /** 数据时间范围 */
      timeRange,
    } = storeToRefs(useAlarmCenterDetailStore());

    /**
     * @description 切换场景回调
     */
    function handleSceneChange(val: SceneEnum) {
      scene.value = val;
    }

    /**
     * @description 跳转容器监控页面
     */
    function handleToK8s(v) {
      console.log('================ v ================', v);
    }

    return { scene, timeRange, handleToK8s, handleSceneChange };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-k8s'>
        <div class='panel-k8s-white-bg-container'>
          <div class='k8s-condition-wrap'>
            <div class='k8s-condition-container'>
              <span>pod = authmanager-debug-5586485485-848qx</span>
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
          </div>
          <div class='k8s-scene-selector-wrap'>
            <K8sSceneSelector
              scene={this.scene}
              onSceneChange={this.handleSceneChange}
            />
          </div>
        </div>
        <div class='panel-k8s-chart-wrap'>
          <PanelContainerDashboard
            scene={this.scene}
            timeRange={this.timeRange}
          />
        </div>
      </div>
    );
  },
});
