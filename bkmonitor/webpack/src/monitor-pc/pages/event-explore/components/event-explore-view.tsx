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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';
import ExploreCustomGraph, {
  type IntervalType,
} from 'monitor-ui/chart-plugins/plugins/explore-custom-graph/explore-custom-graph';
import { type ILegendItem, type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import BackTop from '../../../components/back-top/back-top';
import { APIType, getEventTimeSeries, getEventTotal } from '../api-utils';
import {
  type ConditionChangeEvent,
  type DimensionsTypeEnum,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  type IFormData,
  ExploreSourceTypeEnum,
} from '../typing';
import { eventChartMap, ExploreSubject, getEventLegendColorByType } from '../utils';
import EventExploreTable from './event-explore-table';

import type { TimeRangeType } from '../../../components/time-range/time-range';

import './event-explore-view.scss';

interface IEventExploreViewEvents {
  onClearSearch: () => void;
  onConditionChange(e: ConditionChangeEvent): void;
  onSearch: () => void;
  onSetRouteParams(otherQuery: Record<string, any>): void;
  onShowEventSourcePopover(event: Event): void;
}

interface IEventExploreViewProps {
  entitiesMapList: ExploreEntitiesMap[];
  eventSourceType?: ExploreSourceTypeEnum[];
  fieldMap: ExploreFieldMap;
  queryConfig: IFormData;
  refreshImmediate: string;
  source: APIType;
  timeRange: TimeRangeType;
}

@Component
export default class EventExploreView extends tsc<IEventExploreViewProps, IEventExploreViewEvents> {
  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;
  /** 请求接口公共请求参数中的 query_configs 参数 */
  @Prop({ type: Object, default: () => ({}) }) queryConfig: IFormData;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Object, default: () => ({ source: {}, target: {} }) }) fieldMap: ExploreFieldMap;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Array, default: () => [] }) entitiesMapList: ExploreEntitiesMap[];
  // 数据时间间隔
  @Prop({ type: Array, default: () => [] }) timeRange: TimeRangeType;
  /** 是否立即刷新 */
  @Prop({ type: String, default: '' }) refreshImmediate: string;
  @Prop({ type: Array, default: () => [ExploreSourceTypeEnum.ALL] }) eventSourceType: ExploreSourceTypeEnum[];
  /** 请求接口公共请求参数 */
  @InjectReactive('commonParams') commonParams;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  /** 时间对比值 */
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  /** 图表汇聚周期 */
  chartInterval: IntervalType = 'auto';
  /** 数据总数 */
  total = 0;
  /** 当前显示的图例 */
  showLegendList: DimensionsTypeEnum[] = [];
  /** 图表配置实例 */
  panel: PanelModel = this.initPanelConfig();
  /** 滚动事件被观察者实例 */
  scrollSubject: ExploreSubject = null;
  /** 刷新表格数据，重新请求 */
  refreshTable = random(8);
  /** 数据总条数total请求中止控制器 */
  abortController: AbortController = null;

  /** view 页面中的公共请求参数 queryConfig 中的 group_by 都需要默认传入 type, 因此这里统一处理 */
  get eventQueryParams() {
    const {
      start_time: commonStartTime,
      end_time: commonEndTime,
      query_configs: [commonQueryConfig],
    } = this.commonParams;
    if (!commonQueryConfig?.table || !commonStartTime || !commonEndTime) {
      return null;
    }
    const queryConfigs: Record<string, any> = [
      {
        ...commonQueryConfig,
        group_by: ['type'],
      },
    ];
    return { ...this.commonParams, query_configs: queryConfigs };
  }

  @Watch('timeRange')
  commonParamsChange() {
    this.getEventTotal();
    this.refreshTableData();
  }

  @Watch('refreshImmediate')
  refreshImmediateChange() {
    this.getEventTotal();
    this.refreshTableData();
  }

  @Watch('queryConfig', { deep: true })
  queryParamsChange() {
    this.getEventTotal();
    this.updatePanelConfig();
    this.refreshTableData();
  }

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  @Emit('search')
  filterSearch() {
    return;
  }

  @Emit('setRouteParams')
  setRouteParams(otherQuery = {}) {
    return otherQuery;
  }

  created() {
    this.scrollSubject = new ExploreSubject('explore-view-scroll-trigger');
  }

  mounted() {
    this.getEventTotal();
    this.updatePanelConfig();
    this.$el.addEventListener('scroll', this.handleScroll);
  }
  beforeDestroy() {
    this.$el.removeEventListener('scroll', this.handleScroll);
    this.scrollSubject?.destroy?.();
    this.scrollSubject = null;
  }

  /**
   * @description 滚动事件触发并通知所有观察者
   *
   */
  handleScroll(e) {
    if (!this.scrollSubject) {
      return;
    }
    this.scrollSubject.notifyObservers(e);
  }

  /**
   * @description 获取数据总数
   */
  async getEventTotal() {
    this.total = 0;
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    if (!this.eventQueryParams) {
      return;
    }
    this.abortController = new AbortController();
    const { total } = await getEventTotal(this.eventQueryParams, this.source, {
      signal: this.abortController.signal,
    });
    this.total = total;
  }

  initPanelConfig() {
    return new PanelModel({
      id: 'event-explore-chart',
      title: this.$tc('总趋势'),
      options: {},
      targets: [],
    });
  }

  /** 更新 图表配置实例 */
  updatePanelConfig() {
    if (!this.eventQueryParams) {
      this.panel = this.initPanelConfig();
      return;
    }

    const {
      start_time: commonStartTime,
      end_time: commonEndTime,
      query_configs: [commonQueryConfig],
      ...remainParam
    } = this.eventQueryParams;

    if (!commonQueryConfig.table) {
      return;
    }

    const queryConfigs: Record<string, any> = [
      {
        ...commonQueryConfig,
        metrics: [
          {
            field: '_index',
            method: 'SUM',
            alias: 'a',
          },
        ],
      },
    ];

    if (typeof this.chartInterval === 'number') {
      queryConfigs[0].interval = this.chartInterval;
    }

    const api = getEventTimeSeries(this.source);

    this.panel = new PanelModel({
      id: 'event-explore-chart',
      title: this.$tc('总趋势'),
      options: {
        time_series: {
          type: 'bar',
          echart_option: {
            grid: {
              bottom: 6,
            },
            yAxis: {
              splitLine: {
                lineStyle: {
                  type: 'solid',
                },
              },
            },
          },
        },
      },
      targets: [
        {
          datasource: 'time_series',
          dataType: 'time_series',
          api,
          data: {
            expression: 'a',
            query_configs: queryConfigs,
            ...remainParam,
          },
        },
      ],
    });
  }

  /**
   * @description 刷新表格数据
   */
  refreshTableData() {
    this.refreshTable = random(8);
  }

  /**
   * @description 对图表接口响应数据进行个性处理--添加图表堆叠（stack）功能
   * @param seriesData
   */
  handleChartApiResponseTransform(seriesData: Record<string, any>) {
    if (!seriesData?.series?.length) {
      return;
    }
    const { series } = seriesData;
    const stack = `event-explore-chart-${random(8)}`;
    seriesData.series = series
      .sort((a, b) => eventChartMap[a.dimensions.type] - eventChartMap[b.dimensions.type])
      .map(item => ({
        ...item,
        stack,
        color: getEventLegendColorByType(item.dimensions.type),
      }));
  }

  /**
   * @description: 切换汇聚周期
   */
  handleIntervalChange(interval: IntervalType) {
    if (this.chartInterval === interval) {
      return;
    }
    this.chartInterval = interval;
    this.updatePanelConfig();
  }

  /**
   * @description: 图表显示图例改变后回调
   */
  handleShowLegendChange(legends: ILegendItem[]) {
    this.showLegendList = legends.filter(v => v.show).map(v => v.name) as DimensionsTypeEnum[];
  }

  @Emit('showEventSourcePopover')
  handleShowEventSourcePopover(e: Event) {
    return e;
  }

  render() {
    return (
      <div class='event-explore-view-wrapper'>
        <div class='event-explore-chart-wrapper'>
          <ExploreCustomGraph
            ref='chartRef'
            chartInterval={this.chartInterval}
            panel={this.panel}
            showChartHeader={true}
            total={this.total}
            onIntervalChange={this.handleIntervalChange}
            onSelectLegend={this.handleShowLegendChange}
            onSeriesData={this.handleChartApiResponseTransform}
          />
        </div>
        <div class='event-explore-table-wrapper'>
          <EventExploreTable
            entitiesMapList={this.entitiesMapList}
            eventSourceType={this.eventSourceType}
            fieldMap={this.fieldMap}
            limit={30}
            queryParams={this.eventQueryParams}
            refreshTable={this.refreshTable}
            scrollSubject={this.scrollSubject}
            source={this.source}
            total={this.total}
            onClearSearch={this.clearSearch}
            onConditionChange={this.conditionChange}
            onSearch={this.filterSearch}
            onSetRouteParams={this.setRouteParams}
            onShowEventSourcePopover={this.handleShowEventSourcePopover}
          />
        </div>
        <BackTop
          ref='backTopRef'
          class='back-to-top'
          scrollTop={100}
        >
          <i class='icon-monitor icon-BackToTop' />
        </BackTop>
      </div>
    );
  }
}
