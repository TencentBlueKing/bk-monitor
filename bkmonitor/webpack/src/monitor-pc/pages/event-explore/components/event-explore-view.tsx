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

import { random } from 'monitor-common/utils';
import ExploreCustomGraph, {
  type IntervalType,
} from 'monitor-ui/chart-plugins/plugins/explore-custom-graph/explore-custom-graph';
import { type ILegendItem, type IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import { APIType, getEventTimeSeries, getEventTotal } from '../api-utils';

import type { IFormData } from '../typing';

import './event-explore-view.scss';

interface IEventExploreViewProps {
  queryConfig: IFormData;
  source: APIType;
}

/**
 * @description 维度信息数据类型
 */
enum DimensionsTypeEnum {
  DEFAULT = 'Default',
  NORMAL = 'Normal',
  WARNING = 'Warning',
}
/**
 * @description 固定维度信息数据类型显示排序顺序及固定类型与图表颜色的映射顺序
 */
const eventChartMap = {
  [DimensionsTypeEnum.WARNING]: 0,
  [DimensionsTypeEnum.NORMAL]: 1,
  [DimensionsTypeEnum.DEFAULT]: 2,
};
const eventChartColors = ['#F5C78E', '#92BEF1', '#DCDEE5'];

@Component
export default class EventExploreView extends tsc<IEventExploreViewProps> {
  /** 请求接口公共请求参数中的 query_configs 参数 */
  @Prop({ type: Object, default: () => ({}) }) queryConfig: IFormData;
  /** 来源 */
  @Prop({ default: APIType.MONITOR }) source: APIType;
  /** 是否立即刷新 */
  @InjectReactive('refleshImmediate') refreshImmediate: string;
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
  panel: PanelModel = null;

  @Watch('commonParams', { deep: true })
  commonParamsChange() {
    this.getEventTotal();
  }

  @Watch('queryConfig', { deep: true })
  queryParamsChange() {
    this.updatePanelConfig();
  }

  @Watch('refreshImmediate')
  refreshImmediateChange() {
    this.getEventTotal();
    this.updatePanelConfig();
  }

  /**
   * @description 获取数据总数
   */
  async getEventTotal() {
    const {
      start_time: commonStartTime,
      end_time: commonEndTime,
      query_configs: [commonQueryConfig],
    } = this.commonParams;
    if (!commonQueryConfig?.table || !commonStartTime || !commonEndTime) {
      return;
    }
    const { total } = await getEventTotal(this.commonParams, this.source).catch(() => ({ total: 0 }));
    this.total = total;
  }

  /** 更新 图表配置实例 */
  updatePanelConfig() {
    const {
      query_configs: [commonQueryConfig],
    } = this.commonParams;

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
      // @ts-ignore
      externalData: {
        total: this.total,
      },
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
      .map((item, index) => ({
        ...item,
        stack,
        color: eventChartColors[index],
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
          {!!this.panel && (
            <ExploreCustomGraph
              ref='chartRef'
              chartInterval={this.chartInterval}
              panel={this.panel}
              showChartHeader={true}
              onIntervalChange={this.handleIntervalChange}
              onSelectLegend={this.handleShowLegendChange}
              onSeriesData={this.handleChartApiResponseTransform}
            />
          )}
        </div>
        <div class='event-explore-table'>table</div>
      </div>
    );
  }
}
