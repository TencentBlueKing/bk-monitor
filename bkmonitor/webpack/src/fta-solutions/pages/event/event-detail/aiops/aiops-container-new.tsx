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

import FunctionalDependency from '@blueking/functional-dependency/vue2';
import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { dimensionDrillDown, metricRecommendation } from 'monitor-api/modules/alert';
import { frontendReportEvent } from 'monitor-api/modules/commons';
import { alertIncidentDetail } from 'monitor-api/modules/incident';
import { skipToDocsLink } from 'monitor-common/utils/docs';
import { ETagsType } from 'monitor-pc/components/biz-select/list';

import DimensionTable from './dimension.table';
import MetricsCollapse from './metrics-collapse';
import MetricsView from './metrics-view';
import TabTitle from './tab-title';
import AiopsTroubleshootingCollapse from './troubleshooting-collapse';
import { type IAnomalyDimensions, type IIncidentDetail, type IInfo, ETabNames, EventReportType } from './types';

import type { IDetail } from '../type';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './aiops-container-new.scss';
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
  tabActive = ETabNames.diagnosis;
  /** 告警前后时间 */
  timeRange = 3;

  // showDimensionDrill = false;
  // dimensionDrillTips = '';
  // showMetricRecommendation = false;
  // metricRecommendationTips = '';

  dimensionDrillAiSetting: Record<string, any> = {};
  metricRecommendationAiSetting: Record<string, any> = {};
  wxCsLink = '';

  /** 是否上报了view 数据 */
  hasReportView = false;
  hasReportClick = false;
  hasReportTips = false;
  observer: IntersectionObserver = null;
  troubleShootingLoading = false;
  troubleShootingDataError = {
    isError: false,
    message: '',
  };
  troubleShootingData: IIncidentDetail = null;
  // 是否有权限查看故障诊断
  hasTroubleShootingAuth = false;
  troubleShootingNoData = false;
  // bk助手链接
  incidentWxCsLink = '';
  spaceId = '';

  /** 展示collapse的配置 */
  get tabConfigs() {
    return [
      {
        name: 'diagnosis',
        icon: 'icon-guzhang',
        titleKey: '故障诊断',
        isShow: this.hasTroubleShootingAuth && !this.troubleShootingNoData,
        loading: this.troubleShootingLoading,
        error: this.troubleShootingDataError.isError,
        contentRender: () => {
          if (!this.troubleShootingNoData && this.hasTroubleShootingAuth) {
            return (
              <AiopsTroubleshootingCollapse
                data={this.troubleShootingData}
                errorData={this.troubleShootingDataError}
                loading={this.troubleShootingLoading}
                spaceId={this.spaceId}
                onToIncidentDetail={this.goToIncidentDetail}
              />
            );
          }
        },
        tipsRenderer: this.renderDiagnosisTips,
        tips: '',
      },
      {
        name: 'dimension',
        icon: 'icon-yichangweidu',
        titleKey: '异常维度',
        loading: this.dimensionDrillDownLoading,
        isShow: this.dimensionDrillAiSetting.is_enabled,
        error: this.dimensionDrillDownErr,
        tipsRenderer: this.renderDimensionTips,
        contentRender: this.renderDimensionAndIndexView,
        aiSettings: this.dimensionDrillAiSetting,
      },
      {
        name: 'index',
        icon: 'icon-mc-correlation-metrics',
        titleKey: '关联指标',
        loading: this.metricRecommendationLoading,
        isShow: this.metricRecommendationAiSetting.is_enabled,
        error: this.metricRecommendationErr,
        contentRender: this.renderDimensionAndIndexView,
        tipsRenderer: this.renderMetricTips,
        aiSettings: this.metricRecommendationAiSetting,
      },
    ];
  }
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
    const anomalyDimensions = this.tabData.dimension?.anomaly_dimensions || [];
    // const selects = this.anomalyDimensionsSelected.map(select => select.anomaly_dimension_class);
    const dimensionPanels = [];

    anomalyDimensions.map(item => {
      const panelList = graphPanels
        .filter(panel => panel.anomaly_dimension_class === item.anomaly_dimension_class)
        .map(panel =>
          Object.assign(panel, {
            metric_name: panel.id,
            metric_name_alias: panel.title,
          })
        );
      dimensionPanels.push({
        ...item,
        ...{
          metric_name: item.anomaly_dimension_class,
          metric_name_alias: item.anomaly_dimension_alias,
          result_table_label_name: item.anomaly_dimension_alias,
          panels: panelList,
          metrics: panelList,
        },
      });
    });
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
  @Watch('detail.id', { immediate: true })
  handleAiopsTopoData(val: string) {
    if (val) {
      this.getTabData();
      this.getAiopsTopoData();
    }
  }
  /** 挂载实例事件 */
  mounted() {
    this.$nextTick(() => {
      const detailWrapper = document.querySelector('.correlation-metrics-collapse');
      if (detailWrapper) {
        detailWrapper.addEventListener('scroll', this.handleScroll);
      }
    });
  }
  beforeDestroy() {
    const detailWrapper = document.querySelector('.correlation-metrics-collapse');
    if (detailWrapper) {
      detailWrapper.removeEventListener('scroll', this.handleScroll);
    }
  }
  /** tips点击联动 */
  handleTipsClick(id) {
    (this.$refs.metricsView as any)?.scrollToIdView?.(id);
  }
  setTabActive(active) {
    this.tabActive = active[0];
    this.isCorrelationMetrics = this.tabActive === ETabNames.index;
    this.selectActive = this.tabActive;
    this.troubleShootingLoading = false;
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
  handleScroll() {
    (this.$refs?.dimensionTable as any)?.hideTooltip?.();
    (this.$refs?.metricsView as any)?.handleScroll?.();
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
    const { dimension_drill, metric_recommend, wx_cs_link } = await fetchAiSetting({
      bk_biz_id: this.detail.bk_biz_id,
      alert_id: this.detail.id,
    }).catch(() => ({
      dimension_drill: {
        is_enabled: false,
        is_supported: false,
      },
      metric_recommend: {
        is_enabled: false,
        is_supported: false,
      },
      wx_cs_link: '',
    }));
    const params = {
      bk_biz_id: this.detail.bk_biz_id,
      alert_id: this.detail.id,
    };
    this.isDataInit = true;
    const catchFn = () => (this.isDataInit = false);
    this.dimensionDrillAiSetting = dimension_drill;
    this.wxCsLink = wx_cs_link;
    if (dimension_drill.is_supported && dimension_drill.is_enabled) {
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
    this.metricRecommendationAiSetting = metric_recommend;
    if (metric_recommend.is_supported && metric_recommend.is_enabled) {
      /** 关联指标 */
      this.metricRecommendationLoading = true;
      if (!metric_recommend.is_enabled) {
        this.tabActive = ETabNames.index;
      }
      metricRecommendation(params, { needMessage: false })
        .then(res => {
          const maxPanels = [];
          let recommendedMetric = 0;
          if (res?.info) {
            for (const item of res.recommended_metrics) {
              item.indicators = 0;
              recommendedMetric += item.metrics.length;
              for (const metric of item.metrics) {
                const panelsLen = metric.panels.length;
                item.indicators = item.indicators + panelsLen;
                maxPanels.push(panelsLen);
                this.setMorePanels(metric, item.result_table_label_name);
              }
            }
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
    if (this.dimensionDrillAiSetting.is_enabled || this.metricRecommendationAiSetting.is_enabled) {
      if (this.observer) return;
      this.observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            this.reportEventLog(EventReportType.View);
            this.observer.disconnect();
            this.observer.unobserve(this.aiopsContainerRef);
            this.observer = null;
          }
        }
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
  /** 维度下钻和关联指标视图 */
  renderDimensionAndIndexView() {
    const isDimension = this.tabActive === ETabNames.dimension;
    return (!this.dimensionDrillAiSetting.is_enabled && isDimension) ||
      (!this.metricRecommendationAiSetting.is_enabled && this.tabActive === ETabNames.index) ? (
      <FunctionalDependency
        functionalDesc={this.$t('启用 AI 功能，将支持维度下钻、关联指标事件展示等功能。')}
        guideDescList={[this.$t('1. 基础计算平台：将 AI 相关的模型导入到该环境运行')]}
        guideTitle={this.$t('如需使用该功能，需要部署：')}
        mode='partial'
        title={this.$t('暂无 AI 功能')}
        onGotoMore={this.handleFunctionalDepsGotoMore}
      />
    ) : (
      <MetricsView
        key='metricsView'
        ref='metricsView'
        info={this.tabData.index?.info || {}}
        metricRecommendationErr={isDimension ? this.dimensionDrillDownErr : this.metricRecommendationErr}
        metricRecommendationLoading={isDimension ? this.dimensionDrillDownLoading : this.metricRecommendationLoading}
        panelMap={this.panelMap}
      />
    );
  }
  /** 故障诊断的信息提示 */
  renderDiagnosisTips() {
    if (!this.hasTroubleShootingAuth || this.troubleShootingNoData) {
      this.renderStatusTipsErr('diagnosis');
    }
    return (
      <span
        key='diagnosis-info-text'
        class='diagnosis-info-text'
      >
        {this.$t('当前告警关联故障')}
        <span
          class='diagnosis-text_blue'
          v-bk-overflow-tips
          onClick={this.goToIncidentDetail}
        >
          {this.troubleShootingData?.incident_name}
        </span>
        {this.$t('中')}
      </span>
    );
  }
  /** 异常维度的信息提示 */
  renderDimensionTips(isLoading = true) {
    const isExitDimensionInfo = Object.keys(this.info?.dimensionInfo || {}).length > 0;
    return [
      <span
        key='dimension-info-text'
        class={[isExitDimensionInfo ? 'vis-show' : 'vis-hide']}
      >
        {this.$t('异常维度(组合)')}
        {isLoading
          ? [
              <div
                key={'skeleton'}
                class='skeleton-element inline-skeleton'
              />,
              this.$t('个'),
            ]
          : [
              <font key='font'> {this.info?.dimensionInfo.anomaly_dimension_count}</font>,
              this.$t('个'),
              isExitDimensionInfo ? ',' : '',
            ]}
      </span>,
      <span
        key='dimension-count-text'
        style='marginLeft: 6px'
        class={[isExitDimensionInfo ? 'vis-show' : 'vis-hide']}
      >
        {this.$t('异常维度值')}
        {!isLoading ? (
          <font> {this.info?.dimensionInfo.anomaly_dimension_value_count}</font>
        ) : (
          <div class='skeleton-element inline-skeleton' />
        )}
        {this.$t('个')}
      </span>,
    ];
  }
  /** 关联指标的信息提示 */
  renderMetricTips(isLoading) {
    const isExitIndexInfo = Object.keys(this.info?.indexInfo || {}).length > 0;
    return [
      <span
        key='metric_text'
        class={[isExitIndexInfo ? 'vis-show' : 'vis-hide']}
      >
        <i18n path='{0} 个指标'>
          {!isLoading ? (
            <font>{this.info?.indexInfo.recommended_metric || 0} </font>
          ) : (
            <div class='skeleton-element inline-skeleton' />
          )}
        </i18n>
        {isExitIndexInfo ? ',' : ''}
      </span>,
      <span
        key='metric_count_text'
        style='marginLeft: 6px'
        class={[isExitIndexInfo ? 'vis-show' : 'vis-hide']}
      >
        <i18n path='{0} 条曲线'>
          {!isLoading ? (
            <font>{this.info?.indexInfo.recommended_metric_count || 0} </font>
          ) : (
            <div class='skeleton-element inline-skeleton' />
          )}
        </i18n>
      </span>,
    ];
  }
  /** 绘制collapse头部需要展示的内容 */
  renderStatusTips(config) {
    const { isShow, loading, error, name, aiSettings } = config;
    if (aiSettings) {
      if (!aiSettings.is_supported) {
        return (
          <div style='color: #63656e'>
            {!aiSettings.error_msg
              ? this.$t('当前告警不支持{0}功能', [config.titleKey])
              : this.$t('{0}不支持{1}功能', [aiSettings.error_msg, config.titleKey])}
          </div>
        );
      }
      if (!aiSettings.is_enabled) {
        return (
          <div style='color: #63656e'>
            {this.$t('当前空间未开启{0}功能', [config.titleKey])}, {this.$t('请联系')}{' '}
            <span
              class='bk-assistant-link'
              onClick={e => this.handleToBkAssistant(e, this.wxCsLink)}
            >
              {this.$t('BK助手')}
            </span>
          </div>
        );
      }
    }
    return isShow || loading ? (
      <span class={['aiops-tab-title-message', { 'aiops-tab-title-index-message': name === 'index' }]}>
        {[
          error ? (
            <span
              key='dimension-err-text'
              class='err-text'
            >
              <span>
                <i class='bk-icon icon-exclamation-circle-shape tooltips-icon' />
                {this.$t('模型输出异常')}
              </span>
            </span>
          ) : (
            config.tipsRenderer(loading)
          ),
        ]}
      </span>
    ) : (
      this.renderStatusTipsErr(name)
    );
  }
  /** 绘制collapse头部异常的内容 */
  renderStatusTipsErr(name) {
    if (name === 'diagnosis' && this.troubleShootingNoData && this.hasTroubleShootingAuth) {
      return <div key='diagnosis-info-err-text'>{this.$t('当前告警无关联故障')}</div>;
    }
    return (
      <div
        style='color: #63656e'
        class='aiops-tab-title-message aiops-tab-title-no-auth'
      >
        {this.$t('当前空间未开启故障诊断功能, 请联系')}
        <span
          class='bk-assistant-link'
          onClick={this.handleToBkAssistant}
        >
          {this.$t('BK助手')}
        </span>
      </div>
    );
  }
  /** 获取故障拓扑图展示数据 */
  async getAiopsTopoData() {
    this.troubleShootingLoading = true;
    const { bk_biz_id, id } = this.detail;
    const params = {
      alert_id: id,
      bk_biz_id,
    };
    return alertIncidentDetail(params)
      .then(res => {
        this.troubleShootingDataError.isError = false;
        this.troubleShootingDataError.message = '';

        this.troubleShootingNoData = !(res.incident && Object.keys(res.incident).length !== 0);
        this.hasTroubleShootingAuth = res.greyed_spaces?.includes(bk_biz_id) || false;
        this.troubleShootingData = res.incident ?? null;
        this.incidentWxCsLink = res.wx_cs_link ?? '';
        if (!this.troubleShootingNoData) {
          this.spaceId = this.getSpaceId(res.incident);
        }
      })
      .catch(err => {
        this.troubleShootingDataError.isError = true;
        this.troubleShootingDataError.message = err.data?.error_details ? err.data.error_details.overview : err.message;
      })
      .finally(() => {
        this.troubleShootingLoading = false;
      });
  }
  /** 获取根据空间类型转换后的id */
  getSpaceId(data) {
    const { bizList } = this.$store.getters;
    const spaceData = bizList.find(f => f.space_id === data.bk_biz_id && f.space_name === data.bk_biz_name);
    if (!spaceData) return;
    const { space_type_id, id, space_id, space_code } = spaceData;
    return space_type_id === ETagsType.BKCC ? `(#${id})` : `(${space_id || space_code})`;
  }
  /** 跳转打开bk助手 */
  handleToBkAssistant(e: MouseEvent, url?: string) {
    e.stopPropagation();
    if (url) {
      return window.open(url, '__blank');
    }
    this.incidentWxCsLink && window.open(this.incidentWxCsLink, '__blank');
  }
  /** 跳转至故障详情页面 */
  goToIncidentDetail(e: MouseEvent) {
    e.stopPropagation();
    const { href } = this.$router.resolve({
      name: 'incident-detail',
      params: {
        id: this.troubleShootingData.id,
      },
    });
    const { bk_biz_id } = this.detail;
    window.open(`/?bizId=${bk_biz_id}${href}`, '_blank');
  }

  render() {
    return (
      <div
        ref='aiopsContainer'
        class={['aiops-container-new', { 'aiops-container-show': this.displayConditions && this.show }]}
        onClick={this.handleReportClick}
      >
        <bk-collapse
          class='aiops-container-menu'
          v-model={this.tabActive}
          accordion={true}
          on-item-click={this.setTabActive}
        >
          {this.tabConfigs.map(config => (
            <bk-collapse-item
              key={config.name}
              style={{
                maxHeight:
                  this.tabActive === config.name && config.isShow
                    ? `calc(100% - ${(this.tabConfigs.length - 1) * 60}px)`
                    : '52px',
              }}
              class={[
                `aiops-container-menu-item-${config.name}`,
                'aiops-container-menu-item',
                config.name === 'diagnosis' && (!this.hasTroubleShootingAuth || this.troubleShootingNoData)
                  ? 'cursor-allowed'
                  : '',
              ]}
              disabled={
                config.loading ||
                (['dimension', 'index'].includes(config.name) &&
                  (!config.aiSettings.is_enabled || !config.aiSettings.is_supported))
              }
              name={config.name}
            >
              <div class='aiops-container-menu-item-head'>
                <span class='aiops-tab-title-icon'>
                  <i class={`aiops-tab-icon icon-monitor ${config.icon}`} />
                </span>
                <span class='aiops-tab-title-text'>
                  <span class='aiops-tab-title-name'>{this.$t(config.titleKey)}</span>
                  {this.renderStatusTips(config)}
                </span>
              </div>
              <div
                class={['aiops-container-menu-item-content', `aiops-container-menu-item-content-${config.name}`]}
                slot='content'
              >
                {!config.loading && this.tabActive === config.name && config.contentRender()}
              </div>
            </bk-collapse-item>
          ))}
        </bk-collapse>
      </div>
    );
  }
}
