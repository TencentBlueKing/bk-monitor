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
import { Component, Prop, Provide, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import FuctionalDependency from '@blueking/functional-dependency/vue2';
import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { dimensionDrillDown, metricRecommendation } from 'monitor-api/modules/alert';
import { frontendReportEvent } from 'monitor-api/modules/commons';
import { skipToDocsLink } from 'monitor-common/utils/docs';

import DimensionTable from './dimension.table';
import MetricsCollapse from './metrics-collapse';
import MetricsView from './metrics-view';
import TabTitle from './tab-title';
import { type IAnomalyDimensions, type IInfo, ETabNames, EventReportType } from './types';

import type { IDetail } from '../type';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './aiops-container.scss';
import '@blueking/functional-dependency/vue2/vue2.css';

interface IPanel {
  [key: string]: any;
  anomaly_dimension_class?: string;
  anomaly_dimensions?: IAnomalyDimensions[];
  configured_metric?: IPanelModel[];
  graph_panels?: IPanelModel[];
  info?: IInfo;
  panels?: IPanelModel[];
  recommended_metric?: IPanelModel[];
}

interface IProps {
  detail?: IDetail;
  show?: boolean;
}

interface ITabData {
  dimension?: IPanel;
  index?: IPanel;
}

@Component({
  components: {
    TabTitle,
    DimensionTable,
    MetricsCollapse,
    MetricsView,
  },
})
export default class AiopsContainer extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Ref('aiopsContainer') aiopsContainerRef: HTMLDivElement;
  // 是否关联指标
  @ProvideReactive('isCorrelationMetrics') isCorrelationMetrics = false;
  @ProvideReactive('selectActive') selectActive = ETabNames.dimension;
  dimensionDrillDownLoading = false;
  metricRecommendationLoading = false;
  /** 保存接口错误信息 */
  metricRecommendationErr = '';
  dimensionDrillDownErr = '';
  /** 是否初始化过数据 */
  isDataInit = false;
  /** 纬度下钻及关联指标存储数据 */
  tabData: ITabData = {
    dimension: {},
    index: {},
  };
  /** 表格勾选的维度 */
  anomalyDimensionsSelected = [];
  /** 排序信息 */
  anomalyDimensionsSort = {
    order: 'descending',
    prop: 'dim_surprise',
  };
  /** tab切换 */
  tabActive = ETabNames.dimension;
  /** 告警前后时间 */
  timeRange = 3;

  showDimensionDrill = false;
  showMetricRecommendation = false;
  /** 是否上报了view 数据 */
  hasReportView = false;
  hasReportClick = false;
  hasReportTips = false;
  observer: IntersectionObserver = null;
  /** 首次告警时间 */
  get firstAnomalyTime() {
    return this.detail?.first_anomaly_time;
  }
  /** 是否是时序数据 */
  get isTimeSeries() {
    if (this.detail.extra_info?.strategy) {
      const { strategy } = this.detail.extra_info;
      const typeLabel = strategy.items?.[0]?.query_configs?.[0]?.data_type_label;
      return typeLabel === 'time_series';
    }
    return false;
  }
  /** 时序数据且单指标才能展示纬度下钻 */
  get displayConditions() {
    return this.isTimeSeries && this.detail.metric.length < 2;
  }
  /** 获取数据 */
  @Watch('show')
  handleChangeShow(val) {
    val && this.displayConditions && !this.isDataInit && this.getTabData();
  }
  /** tips点击联动 */
  handleTipsClick(id) {
    (this.$refs.metricsView as any)?.scrollToIdView?.(id);
  }
  setTabActive(active) {
    this.tabActive = active;
    this.isCorrelationMetrics = this.tabActive === ETabNames.index;
    this.selectActive = this.tabActive;
  }
  /** 指标数量信息 */
  get info() {
    return {
      dimensionInfo: this.tabData.dimension?.info || {},
      indexInfo: this.tabData.index?.info || {},
    };
  }
  /** 图表信息 */
  get panelMap() {
    /** 纬度下钻数据需要根据表格选择的维度来进行展示 */
    const graphPanels = this.tabData.dimension?.graph_panels || [];
    const selects = this.anomalyDimensionsSelected.map(select => select.anomaly_dimension_class);
    const dimensionPanels =
      selects.length === 0
        ? graphPanels
        : graphPanels.filter(({ anomaly_dimension_class }) => selects.includes(anomaly_dimension_class));
    return {
      dimensionPanels,
      recommendedMetricPanels: this.tabData.index?.recommended_metrics || [],
    };
  }
  /** 纬度下钻表格展示数据 */
  get anomalyDimensions() {
    const anomalyDimensions = this.tabData.dimension?.anomaly_dimensions || [];
    const { order, prop } = this.anomalyDimensionsSort;
    if (order) {
      anomalyDimensions.sort((curr, next) => {
        if (order === 'ascending') {
          return curr[prop] - next[prop];
        }
        return next[prop] - curr[prop];
      });
    }
    return anomalyDimensions;
  }
  /** 前端排序 */
  handleSortChange({ prop, order }) {
    this.anomalyDimensionsSort.order = order;
    this.anomalyDimensionsSort.prop = prop;
  }
  /** 根据表格勾选过滤图表 */
  handleSelectionChange(selected) {
    this.anomalyDimensionsSelected = selected;
  }
  /** 挂载实例事件 */
  mounted() {
    this.$nextTick(() => {
      const detailWrapper = document.querySelector('.event-detail-container');
      if (detailWrapper) {
        detailWrapper.addEventListener('scroll', this.handleScroll);
      }
    });
  }
  handleScroll() {
    (this.$refs?.dimensionTable as any)?.hideTooltip?.();
    (this.$refs?.metricsView as any)?.handleScroll?.();
  }
  beforeDestroy() {
    const detailWrapper = document.querySelector('.event-detail-container');
    if (detailWrapper) {
      detailWrapper.removeEventListener('scroll', this.handleScroll);
    }
  }
  /** 关联指标每个指标默认将图表数据只展示3条 点击加载更多时全部展示 */
  setMorePanels(panel, title) {
    panel.showMore = panel.panels.length > 3;
    panel.totalPanels = panel.panels;
    panel.panels = panel.panels.slice(0, 3);
    panel.title = title;
  }
  /**
   *
   * @param el dom元素
   * @returns boolean
   * @description 判断元素是否在可视区域内
   */
  isDomInViewport(el: Element) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    return rect.top <= window.innerHeight && rect.left <= window.innerWidth && rect.bottom >= 0 && rect.right >= 0;
  }
  /**
   * @param reportType 上报类型
   * @description 获取上报参数
   */
  getReportParams(reportType: EventReportType) {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { bk_biz_id, id, alert_name, strategy_id, strategy_name } = this.detail;
    return {
      event_name: '维度下钻/指标推荐前端上报',
      event_content: '维度下钻/指标推荐前端上报',
      target: '维度下钻/指标推荐前端上报',
      dimensions: {
        report_type: reportType,
        bk_biz_id,
        space_name: window.space_list?.find(item => +item.bk_biz_id === +bk_biz_id)?.space_name || bk_biz_id,
        alert_id: id,
        alert_name,
        strategy_id,
        strategy_name,
        user_name: window.user_name,
      },
    };
  }
  handleReportClick() {
    this.reportEventLog(EventReportType.Click);
  }
  @Provide('reportEventLog')
  reportEventLog(type: EventReportType) {
    if (type === EventReportType.View) {
      if (this.hasReportView) return;
      if (this.isDomInViewport(this.aiopsContainerRef)) {
        if (
          this.info?.dimensionInfo?.anomaly_dimension_count ||
          this.info?.dimensionInfo?.anomaly_dimension_value_count ||
          this.info?.indexInfo?.recommended_metric_count ||
          this.info?.indexInfo?.recommended_metric
        ) {
          this.hasReportView = true;
          frontendReportEvent(this.getReportParams(EventReportType.View), {
            needMessage: false,
            needTraceId: false,
          }).catch(() => false);
        }
      }
    } else if (type === EventReportType.Click) {
      if (this.hasReportClick) return;
      this.hasReportClick = true;
      frontendReportEvent(this.getReportParams(EventReportType.Click), {
        needMessage: false,
        needTraceId: false,
      }).catch(() => false);
    } else if (type === EventReportType.Tips) {
      if (this.hasReportTips) return;
      this.hasReportTips = true;
      frontendReportEvent(this.getReportParams(EventReportType.Tips), {
        needMessage: false,
        needTraceId: false,
      }).catch(() => false);
    }
  }
  /** 请求数据 */
  async getTabData() {
    const { dimension_drill, metric_recommend } = await fetchAiSetting({
      bk_biz_id: this.detail.bk_biz_id,
    }).catch(() => ({
      dimension_drill: {
        is_enabled: false,
      },
      metric_recommend: {
        is_enabled: false,
      },
    }));
    const params = {
      bk_biz_id: this.detail.bk_biz_id,
      alert_id: this.detail.id,
    };
    this.isDataInit = true;
    const catchFn = () => (this.isDataInit = false);
    this.showDimensionDrill = !!dimension_drill.is_enabled;
    if (dimension_drill.is_enabled) {
      /** 维度下钻数据 */
      this.dimensionDrillDownLoading = true;
      dimensionDrillDown(params, { needMessage: false })
        .then(res => {
          this.tabData.dimension = res || {};
          this.dimensionDrillDownLoading = false;
          this.dimensionDrillDownErr = '';
          this.$nextTick(() => {
            this.reportEventLog(EventReportType.View);
            !this.hasReportView && this.setOberverInservation();
          });
        })
        .catch(err => {
          this.dimensionDrillDownErr = err?.message || this.$t('未知错误');
          catchFn();
          this.dimensionDrillDownLoading = false;
        });
    }
    this.showMetricRecommendation = !!metric_recommend.is_enabled;
    if (metric_recommend.is_enabled) {
      /** 关联指标 */
      this.metricRecommendationLoading = true;
      if (!this.showDimensionDrill) {
        this.tabActive = ETabNames.index;
      }
      metricRecommendation(params, { needMessage: false })
        .then(res => {
          const maxPanels = [];
          let recommendedMetric = 0;
          if (res?.info) {
            res.recommended_metrics.forEach(item => {
              item.indicators = 0;
              recommendedMetric += item.metrics.length;
              item.metrics.forEach(metric => {
                const panelsLen = metric.panels.length;
                item.indicators = item.indicators + panelsLen;
                maxPanels.push(panelsLen);
                this.setMorePanels(metric, item.result_table_label_name);
              });
            });
            res.info.recommended_metric = recommendedMetric;
            /** 判断所有纬度图表数据长度，设置默认列数 */
            res.info.default_column = Math.max(...maxPanels);
            this.$nextTick(() => {
              this.reportEventLog(EventReportType.View);
              !this.hasReportView && this.setOberverInservation();
            });
          }
          this.tabData.index = res || {};
          this.metricRecommendationLoading = false;
          this.metricRecommendationErr = '';
        })
        .catch(err => {
          this.metricRecommendationErr = err?.message || this.$t('未知错误');
          catchFn();
          this.metricRecommendationLoading = false;
        });
    }
  }
  /**
   *
   * @description 设置aiops容器的观察
   */
  setOberverInservation() {
    if (this.showDimensionDrill || this.showMetricRecommendation) {
      if (this.observer) return;
      this.observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            this.reportEventLog(EventReportType.View);
            this.observer.disconnect();
            this.observer.unobserve(this.aiopsContainerRef);
            this.observer = null;
          }
        });
      });
      this.observer.observe(this.aiopsContainerRef);
    }
  }
  unmounted() {
    this.observer?.disconnect();
  }
  handleFunctionalDepsGotoMore() {
    skipToDocsLink('bkDeploymentGuides');
  }
  render() {
    // if (!this.showDimensionDrill && !this.showMetricRecommendation) return <div />;
    return (
      <div
        ref='aiopsContainer'
        class={['aiops-container', { 'aiops-container-show': this.displayConditions && this.show }]}
        onClick={this.handleReportClick}
      >
        <TabTitle
          active={this.tabActive}
          dimensionDrillDownErr={this.dimensionDrillDownErr}
          dimensionDrillDownLoading={this.dimensionDrillDownLoading}
          metricRecommendationErr={this.metricRecommendationErr}
          metricRecommendationLoading={this.metricRecommendationLoading}
          showDimensionDrill={this.showDimensionDrill}
          showMetricRecommendation={this.showMetricRecommendation}
          tabInfo={this.info}
          {...{
            on: {
              'active-change': this.setTabActive,
            },
          }}
        />
        {(!this.showDimensionDrill && this.tabActive === ETabNames.dimension) ||
        (!this.showMetricRecommendation && this.tabActive === ETabNames.index) ? (
          <FuctionalDependency
            functionalDesc={this.$t('启用 AI 功能，将支持维度下钻、关联指标事件展示等功能。')}
            guideDescList={[this.$t('1. 基础计算平台：将 AI 相关的模型导入到该环境运行')]}
            guideTitle={this.$t('如需使用该功能，需要部署：')}
            mode='partial'
            title={this.$t('暂无 AI 功能')}
            onGotoMore={this.handleFunctionalDepsGotoMore}
          />
        ) : (
          [
            <DimensionTable
              key='dimensionTable'
              ref='dimensionTable'
              class={`aiops-container-${this.isCorrelationMetrics ? 'hide' : 'show'}`}
              v-bkloading={{ isLoading: this.dimensionDrillDownLoading }}
              dimensionDrillDownErr={this.dimensionDrillDownErr}
              tableData={this.anomalyDimensions}
              {...{
                on: {
                  selectionChange: this.handleSelectionChange,
                  sortChange: this.handleSortChange,
                  tipsClick: this.handleTipsClick,
                },
              }}
            />,
            <MetricsView
              key='metricsView'
              ref='metricsView'
              info={this.tabData.index?.info || {}}
              metricRecommendationErr={this.metricRecommendationErr}
              metricRecommendationLoading={this.metricRecommendationLoading}
              panelMap={this.panelMap}
            />,
          ]
        )}
      </div>
    );
  }
}
