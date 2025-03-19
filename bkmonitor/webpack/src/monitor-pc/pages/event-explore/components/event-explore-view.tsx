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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, random } from 'monitor-common/utils';
import ExploreCustomGraph, {
  type IntervalType,
} from 'monitor-ui/chart-plugins/plugins/explore-custom-graph/explore-custom-graph';
import { type ILegendItem, type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import BackTop from '../../../components/back-top/back-top';
import { APIType, getEventLogs, getEventTimeSeries, getEventTotal } from '../api-utils';
import {
  type ConditionChangeEvent,
  type DimensionsTypeEnum,
  type EventExploreTableRequestConfigs,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  ExploreTableLoadingEnum,
  type IFormData,
} from '../typing';
import { eventChartMap, getEventLegendColorByType } from '../utils';
import EventExploreTable from './event-explore-table';

import type { TimeRangeType } from '../../../components/time-range/time-range';

import './event-explore-view.scss';

interface IEventExploreViewProps {
  queryConfig: IFormData;
  source: APIType;
  timeRange: TimeRangeType;
  refreshImmediate: string;
  fieldMap: ExploreFieldMap;
  entitiesMapList: ExploreEntitiesMap[];
}

interface IEventExploreViewEvents {
  onClearSearch: () => void;
  onConditionChange(e: ConditionChangeEvent): void;
}

@Component
export default class EventExploreView extends tsc<IEventExploreViewProps, IEventExploreViewEvents> {
  @Ref('eventExploreTableRef') eventExploreTableRef: InstanceType<typeof EventExploreTable>;

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
  /** table表格请求配置 */
  tableRequestConfigs: EventExploreTableRequestConfigs = {};
  /** 是否滚动到底 */
  isTheEnd = false;

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
    this.updateTableRequestConfigs();
  }

  @Watch('refreshImmediate')
  refreshImmediateChange() {
    this.getEventTotal();
    this.updateTableRequestConfigs();
  }

  @Watch('queryConfig', { deep: true })
  queryParamsChange() {
    this.getEventTotal();
    this.updatePanelConfig();
    this.updateTableRequestConfigs();
  }

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  mounted() {
    this.getEventTotal();
    this.updatePanelConfig();
    this.updateTableRequestConfigs();
    this.$el.addEventListener('scroll', this.handleScrollToEnd);
  }
  beforeDestroy() {
    this.$el.removeEventListener('scroll', this.handleScrollToEnd);
  }

  /**
   * @description: 监听滚动到底部
   * @param {Event} evt 滚动事件对象
   * @return {*}
   */
  handleScrollToEnd(evt: Event) {
    if (this.eventExploreTableRef) {
      // @ts-ignore
      this.eventExploreTableRef.$el.style.pointEvents = 'none';
      this.eventExploreTableRef.handlePopoverHide?.();
    }
    const target = evt.target as HTMLElement;
    const { scrollHeight } = target;
    const { scrollTop } = target;
    const { clientHeight } = target;
    const isEnd = !!scrollTop && scrollHeight - Math.ceil(scrollTop) === clientHeight;
    this.isTheEnd = isEnd;

    if (this.isTheEnd) {
      this.updateTableRequestConfigs(ExploreTableLoadingEnum.SCROLL);
    }
    this.updateTablePointEventsToAll();
  }

  @Debounce(1000)
  updateTablePointEventsToAll() {
    if (this.eventExploreTableRef) {
      // @ts-ignore
      this.eventExploreTableRef.$el.style.pointEvents = 'all';
    }
  }

  /**
   * @description 获取数据总数
   */
  async getEventTotal() {
    this.total = 0;
    if (!this.eventQueryParams) {
      return;
    }
    const { total } = await getEventTotal(this.eventQueryParams, this.source).catch(() => ({
      total: 0,
    }));
    this.total = total;
  }

  /** 更新 表格请求配置 */
  updateTableRequestConfigs(loadingType: ExploreTableLoadingEnum = ExploreTableLoadingEnum.REFRESH) {
    if (!this.eventQueryParams) {
      this.tableRequestConfigs = {};
      return;
    }

    const api = getEventLogs(this.source);
    const [apiModule, apiFunc] = api.split('.');
    this.tableRequestConfigs = {
      apiModule,
      apiFunc,
      loadingType,
      data: this.eventQueryParams,
    };
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
            ref='eventExploreTableRef'
            entitiesMapList={this.entitiesMapList}
            fieldMap={this.fieldMap}
            limit={30}
            requestConfigs={this.tableRequestConfigs}
            total={this.total}
            onClearSearch={this.clearSearch}
            onConditionChange={this.conditionChange}
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
