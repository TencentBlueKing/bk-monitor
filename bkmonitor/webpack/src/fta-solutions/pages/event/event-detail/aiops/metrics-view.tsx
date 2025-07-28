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
import { Component, InjectReactive, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  createAnomalyDimensionTips,
  createGroupAnomalyDimensionTips,
} from 'monitor-common/tips/anomaly-dimension-tips';
import { random } from 'monitor-common/utils/utils';
import DashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import CorrelationNav from './correlation-nav';
import MetricsCollapse from './metrics-collapse';

import type { IInfo } from './types';
import type { IPanelModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './metrics-view.scss';

interface IMetrics {
  metric_name?: string;
  metric_name_alias?: string;
  panels?: IPanelModel[];
  title?: string;
}
interface IPanelMap {
  dimensionPanels?: IPanelModel[];
  recommendedMetricPanels?: IRecommendedMetricPanels[];
}
interface IProps {
  info?: IInfo;
  metricRecommendationErr?: string;
  metricRecommendationLoading: boolean;
  panelMap?: IPanelMap;
}
interface IRecommendedMetricPanels {
  metrics: IMetrics[];
  result_table_label: string;
  result_table_label_name: string;
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
  @ProvideReactive('layoutActive') layoutActive = 0;

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
  // @Watch('info')
  // handleChangePanelInfo() {
  //   this.layoutActive = this.info.default_column > 1 ? 2 : 0;
  // }
  /** 指标加载全部 */
  handleLoadPanels(panel) {
    panel.showMore = false;
    panel.panels = panel.totalPanels;
    // this.$nextTick(this.handleScroll);
  }
  /** 联动对应图表 */
  scrollToIdView(id: string) {
    const scrollToDom = document.getElementById(`${id}__key__`);
    if (!scrollToDom) {
      return;
    }
    scrollToDom.scrollIntoView({
      behavior: 'smooth',
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
            id={item.metric_name}
            key={item.metric_name}
            column={props.column}
            customHeightFn={column => '200px' || (column === 1 ? '220px' : '256px')}
            isSingleChart={false}
            isSplitPanel={false}
            needOverviewBtn={false}
            panels={item.panels}
          />
        ) : (
          ''
        )}
        {item.showMore ? (
          <span
            class='add-more'
            onClick={() => this.handleLoadPanels(item)}
          >
            {this.$t('加载更多')}
          </span>
        ) : (
          ''
        )}
      </div>
    );
  }

  handleActive(item) {
    clearTimeout(this.scrollActiveTime);
    this.scrollActiveFlag = true;
    let current: HTMLElement | null = null;
    if (this.isCorrelationMetrics) {
      current = document.getElementById(`${item.metric_name}_collapse`);
    } else {
      current = document.getElementById(`${CSS.escape(item.id)}__key__`);
    }
    const detailWrapper = document.querySelector('.bk-collapse-item-active .correlation-metric-panels');
    if (!current) {
      return;
    }
    detailWrapper.scrollTo({
      top: current.offsetTop - 10,
      behavior: 'smooth',
    });

    if (this.$refs[key] && (this.$refs[key] as any).isCollapse) {
      setTimeout(() => {
        (this.$refs[key] as any)?.handleToggleCollapse?.(true);
      }, 60);
    }
  }
  /** 将指标打平展示 */
  get recommendedMetricPanels() {
    return (
      this.panelMap.recommendedMetricPanels?.reduce?.((prev, curr) => {
        return prev.concat(curr.metrics);
      }, []) || []
    );
  }
  /** 关联指标渲染 */
  renderCorrelationMetricPanels() {
    const key = !this.isCorrelationMetrics ? 'dimensionPanels' : 'recommendedMetricPanels';
    const chartList = !this.isCorrelationMetrics ? this.panelMap.dimensionPanels : this.recommendedMetricPanels;
    return (
      <div
        class={['correlation-metric-wrap', this.metricRecommendationErr ? 'metrics-err' : '']}
        v-bkloading={{ isLoading: this.metricRecommendationLoading }}
      >
        {this.panelMap[key].length > 0 ? (
          [
            <div
              key='wrap-panels'
              class={['correlation-metric-panels']}
            >
              {chartList.map(item => this.renderMetricsCollapse(item))}
            </div>,
            // <div
            //   key='wrap-bg'
            //   class='correlation-metric-nav-wrap-bg'
            // />,
            <div
              key='wrap-nav'
              style={this.isFixed ? { top: this.isDetailRoute ? '52px' : '60px' } : {}}
              class={['correlation-metric-nav-wrap']}
            >
              <CorrelationNav
                ref='correlationNav'
                isCorrelationMetrics={this.isCorrelationMetrics}
                list={this.panelMap[key]}
                onActive={this.handleActive}
              />
            </div>,
          ]
        ) : (
          <div class={'bk-table-empty-block'}>
            <bk-exception
              scene='part'
              type={this.metricRecommendationErr ? '500' : 'empty'}
            >
              {this.metricRecommendationErr ? this.metricRecommendationErr : this.$t('暂无数据')}
            </bk-exception>
          </div>
        )}
      </div>
    );
  }

  renderMetricsCollapse(item) {
    return (
      <MetricsCollapse
        id={`${item.metric_name}_collapse`}
        key={`${item.metric_name}_collapse`}
        ref={`${item.metric_name}_collapse`}
        headerTips={
          this.isCorrelationMetrics
            ? createAnomalyDimensionTips(item, true)
            : createGroupAnomalyDimensionTips(item, false)
        }
        info={this.info}
        layoutActive={this.layoutActive}
        needLayout={true}
        title={!this.isCorrelationMetrics ? item.anomaly_dimension_alias : `【${item.title}】${item.metric_name_alias}`}
        valueCount={item.totalPanels?.length}
        valueTotal={item?.dimension_value_total_count || 0}
        {...{
          on: {
            // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
            layoutChange: val => (this.layoutActive = val),
          },
          scopedSlots: {
            default: this.renderDashboardPanel.bind(this, item),
          },
        }}
      />
    );
  }

  render() {
    return <div class='aiops-metrics-view'>{this.renderCorrelationMetricPanels()}</div>;
  }
}
