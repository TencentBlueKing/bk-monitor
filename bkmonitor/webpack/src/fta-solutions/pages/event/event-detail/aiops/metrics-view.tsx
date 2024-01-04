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
import { Component, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from '../../../../../monitor-common/utils/utils';
import DashboardPanel from '../../../../../monitor-ui/chart-plugins/components/flex-dashboard-panel';
import { IPanelModel, IViewOptions } from '../../../../../monitor-ui/chart-plugins/typings';

import CorrelationNav from './correlation-nav';
import MetricsCollapse from './metrics-collapse';
import { IInfo } from './types';

import './metrics-view.scss';

interface IProps {
  panelMap?: IPanelMap;
  info?: IInfo;
  metricRecommendationErr?: string;
  metricRecommendationLoading: boolean;
}
interface IMetrics {
  metric_name?: string;
  metric_name_alias?: string;
  title?: string;
  panels?: IPanelModel[];
}
interface IRecommendedMetricPanels {
  metrics: IMetrics[];
  result_table_label: string;
  result_table_label_name: string;
}
interface IPanelMap {
  dimensionPanels?: IPanelModel[];
  recommendedMetricPanels?: IRecommendedMetricPanels[];
}

@Component
export default class AiopsMetricsPanel extends tsc<IProps> {
  /** 错误信息 */
  @Prop({ type: String, default: '' }) metricRecommendationErr: string;

  @Prop({ type: Boolean, default: false }) metricRecommendationLoading: boolean;
  /** 指标数量信息 */
  @Prop({ type: Object, default: () => ({}) }) info: IInfo;
  /** panel 数据 */
  @Prop({ type: Object, default: () => {} }) panelMap: IPanelMap;
  /** 关联指标是否展示中 */
  @InjectReactive('isCorrelationMetrics') isCorrelationMetrics: boolean;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 指标布局列
  @ProvideReactive('layoutActive') layoutActive: Number = 2;

  loading = false;
  /** 关联指标是否触发吸附 */
  isFixed = false;
  /** 标志当前为手动选中触发选中，该情况下会触发scroll 事件使用标示来处理scroll事件 */
  scrollActiveFlag = false;
  scrollActiveTime = null;

  /** panel面板 Id */
  dashboardPanelId = random(8);
  correlationMetricPanelId = random(8);

  /** 纬度下钻不存在布局列表，根据长度自动计算列数 默认3 */
  get dimensionPanelsColumn(): number {
    const len = this.panelMap?.dimensionPanels?.length || 3;
    return len > 3 ? 3 : len;
  }
  @Watch('info')
  handleChangePanelInfo() {
    this.layoutActive = this.info.default_column > 1 ? 2 : 0;
  }
  /** 指标加载全部 */
  handleLoadPanels(panel) {
    panel.showMore = false;
    panel.panels = panel.totalPanels;
    this.$nextTick(this.handleScroll);
  }
  /** 联动对应图表 */
  scrollToIdView(id: string) {
    const scrollToDom = document.getElementById(`${id}__key__`);
    if (!scrollToDom) {
      return;
    }
    scrollToDom.scrollIntoView({
      behavior: 'smooth'
    });
    scrollToDom.classList.add('select');
    setTimeout(() => {
      scrollToDom.classList.remove('select');
    }, 2300);
  }
  /** 当前是否是页面形式查看告警详情 */
  get isDetailRoute() {
    return this.$route.name === 'event-center-detail';
  }
  handleScroll() {
    const container = document.querySelector('.aiops-container-show');
    if (!container || !this.isCorrelationMetrics) return;
    clearTimeout(this.scrollActiveTime);
    // 滚动结束后
    this.scrollActiveTime = setTimeout(() => {
      this.scrollActiveFlag = false;
    }, 60);
    const metricWrap = document.querySelector('.correlation-metric-wrap');
    const metricsList = document.querySelectorAll('.aiops-correlation-metrics');
    if (metricWrap) {
      const { top } = metricWrap.getBoundingClientRect();
      const fixedTop = this.isDetailRoute ? 60 : 60;
      const warpTop = fixedTop - 20;
      this.isFixed = top < warpTop || top === warpTop;
      if (this.scrollActiveFlag) return;
      if (!this.isFixed) {
        const metric = metricsList[0];
        metric && this.$refs.correlationNav.setActive(metric.id.replace('_collapse', ''));
        return;
      }
      const metric = [...metricsList].find(metric => {
        const { top, height } = metric.getBoundingClientRect();
        const rectHeight = height - Math.abs(top);
        if (top < 100 && (height > 100 ? rectHeight > 100 : top > 0 && rectHeight < 0)) {
          return true;
        }
        return false;
      });
      metric && this.$refs.correlationNav.setActive(metric.id.replace('_collapse', ''));
    }
  }
  /** 指标展开收起 */
  renderDashboardPanel(item, props) {
    return (
      <div class='panel-warp'>
        {item.panels?.length > 0 ? (
          <DashboardPanel
            panels={item.panels}
            id={item.metric_name}
            key={item.metric_name}
            column={props.column}
            customHeightFn={column => '200px' || (column === 1 ? '220px' : '256px')}
            needOverviewBtn={false}
            isSplitPanel={false}
            isSingleChart={false}
          ></DashboardPanel>
        ) : (
          ''
        )}
        {item.showMore ? (
          <span
            class='add-more'
            onClick={this.handleLoadPanels.bind(this, item)}
          >
            {this.$t('加载更多')}
          </span>
        ) : (
          ''
        )}
      </div>
    );
  }
  renderMetricsCollapse(item, index) {
    const panelLen = this.recommendedMetricPanels.length;
    return (
      <MetricsCollapse
        class={[panelLen > 1 && index !== panelLen - 1 ? 'mb10' : '']}
        key={`${item.metric_name}_collapse`}
        id={`${item.metric_name}_collapse`}
        ref={`${item.metric_name}_collapse`}
        info={this.info}
        title={`【${item.title}】${item.metric_name_alias}`}
        needLayout={true}
        layoutActive={this.layoutActive}
        {...{
          on: {
            layoutChange: val => (this.layoutActive = val)
          },
          scopedSlots: {
            default: this.renderDashboardPanel.bind(this, item)
          }
        }}
      ></MetricsCollapse>
    );
  }

  handleActive(item) {
    clearTimeout(this.scrollActiveTime);
    this.scrollActiveFlag = true;
    const key = `${item.metric_name}_collapse`;
    const current = document.getElementById(key);
    if (!current) {
      return;
    }
    current.scrollIntoView({
      behavior: 'smooth'
    });
    if (this.$refs[key] && (this.$refs[key] as any).isCollapse) {
      setTimeout(() => {
        (this.$refs[key] as any)?.handleToggleCollapse?.(true);
      }, 60);

      //   setTimeout(() => {
      //   //   console.log('213123312---');
      //   //   current.scrollIntoView({
      //   //     behavior: 'smooth'
      //   //   });
      //   // }, 200);
      //   (this.$refs[key] as any)?.handleToggleCollapse?.(true);
      //   // return;
      // })
    }
  }
  /** 将指标打平展示 */
  get recommendedMetricPanels() {
    return (
      this.panelMap.recommendedMetricPanels?.reduce?.((prev, curr) => {
        prev = prev.concat(curr.metrics);
        return prev;
      }, []) || []
    );
  }
  /** 关联指标渲染 */
  renderCorrelationMetricPanels() {
    return (
      <div
        v-bkloading={{ isLoading: this.metricRecommendationLoading }}
        class={[
          'correlation-metric-wrap',
          !this.isCorrelationMetrics ? 'aiops-metrics-view-hide' : '',
          this.metricRecommendationErr ? 'metrics-err' : ''
        ]}
      >
        {this.panelMap.recommendedMetricPanels.length > 0 ? (
          [
            <div class='correlation-metric-nav-wrap-bg'></div>,
            <div
              class={['correlation-metric-nav-wrap', this.isFixed && 'correlation-metric-fixed']}
              style={this.isFixed ? { top: this.isDetailRoute ? '52px' : '60px' } : {}}
            >
              <CorrelationNav
                ref='correlationNav'
                list={this.panelMap.recommendedMetricPanels}
                onActive={this.handleActive}
              ></CorrelationNav>
            </div>,
            <div class={['correlation-metric-panels', this.isFixed && 'correlation-metric-fixed-padding']}>
              {this.recommendedMetricPanels.map((item, index) => this.renderMetricsCollapse(item, index))}
            </div>
          ]
        ) : (
          <div class={`bk-table-empty-block aiops-metrics-view-${!this.isCorrelationMetrics ? 'hide' : 'show'}`}>
            <bk-exception
              type={this.metricRecommendationErr ? '500' : 'empty'}
              scene='part'
            >
              {this.metricRecommendationErr ? this.metricRecommendationErr : this.$t('暂无数据')}
            </bk-exception>
            {/* <div class="bk-table-empty-text">
              <i class="bk-table-empty-icon bk-icon icon-empty"></i>
              <div>{this.$t('暂无数据')}</div>
            </div> */}
          </div>
        )}
      </div>
    );
  }
  /** 纬度下钻图表渲染 */
  renderDimensionPanels() {
    return this.panelMap?.dimensionPanels?.length > 0 ? (
      <DashboardPanel
        class={[`aiops-metrics-view-${this.isCorrelationMetrics ? 'hide' : 'show'}`, 'aiops-dimension-panels']}
        id={this.dashboardPanelId}
        key={this.dashboardPanelId}
        panels={this.panelMap.dimensionPanels}
        column={this.dimensionPanelsColumn}
        customHeightFn={column => '200px' || (column === 1 ? '220px' : '256px')}
        needOverviewBtn={false}
        isSplitPanel={false}
        isSingleChart={false}
      ></DashboardPanel>
    ) : (
      ''
    );
  }
  render() {
    return <div class='aiops-metrics-view'>{[this.renderDimensionPanels(), this.renderCorrelationMetricPanels()]}</div>;
  }
}
