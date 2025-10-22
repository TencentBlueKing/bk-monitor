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
import { type PropType, defineComponent, onMounted, shallowRef } from 'vue';

import { random } from 'monitor-common/utils';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';

import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import { getHostSceneView } from '../../../services/alarm-detail';
import PanelHostDashboard from './components/host-dashboard/panel-host-dashboard';

import type { IBookMark } from 'monitor-ui/chart-plugins/typings';

import './index.scss';

export default defineComponent({
  name: 'PanelHost',
  props: {
    id: {
      type: String,
    },
    detail: {
      // TODO 类型需补充完善
      type: Object as PropType<any>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** host 场景指标视图配置信息 */
    const hostSceneData = shallowRef<IBookMark>(null);
    /** 是否处于请求加载状态 */
    const loading = shallowRef(false);
    /** 图表联动Id */
    const dashboardId = random(10);

    onMounted(() => {
      getDashboardPanels();
    });
    /**
     * @description 获取仪表盘数据数组
     */
    async function getDashboardPanels() {
      loading.value = true;
      const sceneView = await getHostSceneView(props.detail?.bk_biz_id ?? 2);

      // for (const dashboard of sceneView.panels) {
      //   if (!dashboard?.panels?.length) continue;
      //   dashboard.panels = dashboard.panels.map(
      //     item =>
      //       new PanelModel({
      //         ...item,
      //         dashboardId,
      //       })
      //   );
      // }
      hostSceneData.value = sceneView;
      echartsConnect(dashboardId);
      loading.value = false;
    }
    return { hostSceneData, dashboardId };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-host'>
        <div class='panel-host-white-bg-container'>
          <div class='host-selector-wrap'>
            <div class='host-selector'>host-selector</div>
            <div class='host-explore-link-btn'>
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
          />
        </div>
      </div>
    );
  },
});
