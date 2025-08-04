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
import { Component, Mixins, Prop, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { random } from 'monitor-common/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import ListLegend from '../../components/chart-legend/common-legend';
import { MONITOR_BAR_OPTIONS } from '../../constants';
import { ChartLoadingMixin, IntersectionMixin, LegendMixin, ResizeMixin, ToolsMixin } from '../../mixins';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import BaseEchart from '../monitor-base-echart';

import type {
  ICommonCharts,
  ILegendItem,
  IMenuItem,
  LegendActionType,
  MonitorEchartOptions,
  PanelModel,
} from '../../typings';
import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';

import './alarm-event-chart.scss';

interface ILineEchartProps {
  panel: PanelModel;
}
@Component
class AlarmEventChart
  extends Mixins<ChartLoadingMixin & IntersectionMixin & LegendMixin & ResizeMixin & ToolsMixin>(
    ResizeMixin,
    IntersectionMixin,
    LegendMixin,
    ToolsMixin,
    ChartLoadingMixin
  )
  implements ICommonCharts
{
  @Prop({ required: true }) panel: PanelModel;

  @Ref() baseChart: any;

  height = 80;
  width = 300;

  customOptions: any | MonitorEchartOptions = deepmerge(MONITOR_BAR_OPTIONS, {
    backgroundColor: 'transparent',
    yAxis: {
      type: 'value',
      splitNumber: 2,
      splitLine: {
        show: false,
      },
    },
  });

  legendData: ILegendItem[] = [
    {
      name: '无告警',
      color: '#2DCB56',
      value: 0,
      show: true,
    },
    {
      name: '提醒',
      color: '#3A84FF',
      value: 3,
      show: true,
    },
    {
      name: '预警',
      color: '#FF9C01',
      value: 2,
      show: true,
    },
    {
      name: '致命',
      color: '#EA3636',
      value: 1,
      show: true,
    },
  ];

  markAreaIconPosition = [];

  tableColumns = [];
  tableData = [
    {
      event_name: 'xxxxxx01',
      event_count: 10,
    },
    {
      event_name: 'xxxxxx02',
      event_count: 20,
    },
  ];

  searchValue = '';

  emptyType: EmptyStatusType = 'empty';

  seriesList = [];

  created() {
    this.tableColumns = [
      {
        label: this.$t('事件名称'),
        prop: 'event_name',
        formatter: row => <span class='event-name'>{row.event_name}</span>,
      },
      {
        label: this.$t('事件数'),
        prop: 'event_count',
      },
    ];
  }

  /**
   * @description: 获取图表数据
   */
  async getPanelData() {
    this.unregisterObserver();
    this.handleLoadingChange(true);
    const data = await this.mockData().finally(() => this.handleLoadingChange(false));
    data && this.updateChartData(data);
  }

  mockData() {
    return new Promise(resolve => {
      const data = [
        {
          display_name: '无告警',
          name: 0,
          datapoints: [],
        },
        {
          display_name: '提醒',
          name: 3,
          datapoints: [],
        },
        {
          display_name: '预警',
          name: 2,
          datapoints: [],
        },
        {
          display_name: '致命',
          name: 1,
          datapoints: [],
        },
      ];
      const point1 = data[0].datapoints;
      const point2 = data[1].datapoints;
      const point3 = data[2].datapoints;
      const point4 = data[3].datapoints;
      let i = 0;
      const time1 = +new Date();
      const interval = 60000;
      while (i < 20) {
        const value = Math.random() * 10;
        point1.push([time1 + i * interval, value + 3]);
        point2.push([time1 + i * interval, value + 2]);
        point3.push([time1 + i * interval, value + 1]);
        point4.push([time1 + i * interval, value + 0]);
        i += 1;
      }
      setTimeout(() => resolve(data), 1000);
    });
  }

  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    const stack = random(8);
    const colors = ['#2DCB56', '#3A84FF', '#FF9C01', '#EA3636'];
    const names = [this.$t('无告警'), this.$t('致命'), this.$t('预警'), this.$t('提醒')];
    const series = srcData.map((item, index) => ({
      data: item.datapoints,
      name: item.display_name,
      type: 'bar',
      itemStyle: {
        color: colors[index],
      },
      stack,
    }));
    this.seriesList = Object.freeze(series) as any;
    this.setMarkArea(series[0]);
    const maxXInterval = getSeriesMaxInterval(srcData);
    const xInterval = getTimeSeriesXInterval(maxXInterval.maxXInterval, this.width, maxXInterval.maxSeriesCount);
    const formatterFunc = this.handleSetFormatterFunc(srcData[0].datapoints);
    const data = {
      xAxis: {
        axisLabel: {
          formatter: formatterFunc || '{value}',
        },
        type: 'time',
        ...xInterval,
        splitNumber: 3,
      },
      tooltip: {
        className: 'alarm-event-chart-tooltip',
        show: true,
        trigger: 'axis',
        appendToBody: true,
        padding: [8, 8, 8, 8],
        transitionDuration: 0,
        formatter: params => {
          const time = dayjs(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss');
          const alarms = [];
          for (const param of params) {
            alarms.push({
              color: colors[param.seriesIndex],
              name: names[param.seriesIndex],
              count: param.value[1],
            });
          }
          const events = [
            {
              name: '事件名称1',
              color: '#C464FF',
              count: 10,
            },
            {
              name: '事件名称2',
              color: '#C464FF',
              count: 10,
            },
            {
              name: '事件名称3',
              color: '#C464FF',
              count: 10,
            },
          ];
          return `
            <div class="time-text">${time}</div>
            <div class="alarm-title">
              <span class="icon-monitor icon-menu-event"></span>
              <span>${this.$t('告警')}</span>
            </div>
            <div class="alarm-list">
              ${alarms
                .map(
                  item => `<div class="alarm-item">
                  <span class="alarm-item-point" style="background-color:${item.color};"></span>
                  <span class="alarm-item-name">${item.name}</span>
                  <span class="alarm-item-count">${item.count}</span>
                </div>`
                )
                .join('')}
            </div>
            <div class="split-line"></div>
            <div class="alarm-title">
              <span class="icon-monitor icon-menu-event"></span>
              <span>${this.$t('告警')}</span>
            </div>
            <div class="alarm-list">
            ${events
              .map(
                item => `<div class="alarm-item">
                <span class="alarm-item-point" style="background-color:${item.color};"></span>
                <span class="alarm-item-name">${item.name}</span>
                <span class="alarm-item-count">${item.count}</span>
              </div>`
              )
              .join('')}
            </div>
          `;
        },
      },
      series,
    };
    this.customOptions = deepmerge(this.customOptions, data);
    setTimeout(() => {
      this.handleSetMarkAreaIconPosition();
    }, 300);
  }

  setMarkArea(seriesItem) {
    seriesItem.markArea = {
      data: [
        [
          {
            xAxis: seriesItem.data[2][0],
            itemStyle: {
              color: '#F2E8FB',
            },
            emphasis: {
              itemStyle: {
                color: '#EDE9FB',
              },
            },
          },
          {
            xAxis: seriesItem.data[5][0],
          },
        ],
        [
          {
            xAxis: seriesItem.data[12][0],
            itemStyle: {
              color: '#F2E8FB',
            },
            emphasis: {
              itemStyle: {
                color: '#EDE9FB',
              },
            },
          },
          {
            xAxis: seriesItem.data[15][0],
          },
        ],
      ],
    };
  }

  handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
    let formatterFunc = null;
    const [firstItem] = seriesData;
    const lastItem = seriesData[seriesData.length - 1];
    const val = new Date('2010-01-01').getTime();
    const getXVal = (timeVal: any) => {
      if (!timeVal) return timeVal;
      return timeVal[0] > val ? timeVal[0] : timeVal[1];
    };
    const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
    const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);
    if (minX && maxX) {
      formatterFunc = (v: any) => {
        const duration = dayjs.tz(maxX).diff(dayjs.tz(minX), 'second');
        if (onlyBeginEnd && v > minX && v < maxX) {
          return '';
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(v).format('MM-DD');
        }
        return dayjs.tz(v).format('YYYY-MM-DD');
      };
    }
    return formatterFunc;
  }

  handleMenuToolsSelect(menuItem: IMenuItem) {
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        // this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        this.handleStoreImage(this.panel.title || '测试');
        break;
      case 'fullscreen': // 大图检索
        // this.handleFullScreen();
        break;
      case 'area': // 面积图
        this.baseChart?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        this.baseChart?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': // 跳转数据检索
        // this.handleExplore();
        break;
      case 'strategy': // 新增策略
        // this.handleAddStrategy();
        break;
      default:
        break;
    }
  }

  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (this.legendData.length < 2) {
      return;
    }
    const copyOptions = { ...this.customOptions };
    const setSeriesFilter = () => {
      const showNames = [];
      this.legendData.forEach(l => {
        l.show && showNames.push(l.name);
      });
      copyOptions.series = this.seriesList?.filter(s => showNames.includes(s.name));
      this.setMarkArea(copyOptions.series[0]);
      this.customOptions = Object.freeze({ ...copyOptions });
    };
    if (actionType === 'shift-click') {
      item.show = !item.show;
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    } else if (actionType === 'click') {
      const hasOtherShow = this.legendData.filter(item => !item.hidden).some(set => set.name !== item.name && set.show);
      this.legendData.forEach(legend => {
        legend.show = legend.name === item.name || !hasOtherShow;
      });
      setSeriesFilter();
      this.$emit('selectLegend', this.legendData);
    }
    setTimeout(() => {
      this.handleResize();
    }, 100);
  }

  handleSetMarkAreaIconPosition() {
    try {
      const markAareData = this.customOptions.series[0].markArea.data || [];
      const yMax = this.baseChart.instance.getModel().getComponent('yAxis').axis.scale._extent[1] || 0;
      const markAreaIconPosition = [];
      for (const item of markAareData) {
        const start = item[0].xAxis;
        const end = item[1].xAxis;
        const x = start + (end - start) / 2;
        const xy = this.baseChart.instance.convertToPixel({ seriesIndex: 0 }, [x, yMax]);
        markAreaIconPosition.push({
          show: true,
          x: xy[0] - 6,
          y: xy[1] - 6,
        });
        console.log(xy);
      }
      this.markAreaIconPosition = markAreaIconPosition;
    } catch (e) {
      console.error(e);
    }
  }

  /** 空状态处理 */
  handleOperation(type: EmptyStatusOperationType) {
    console.log(type);
    if (type === 'clear-filter') {
      return;
    }
    if (type === 'refresh') {
      this.emptyType = 'empty';
      return;
    }
  }

  render() {
    return (
      <div class='monitor-echart-common alarm-event-chart'>
        <div class='chart-instance'>
          <BaseEchart
            ref='baseChart'
            width={this.width}
            height={this.height}
            options={this.customOptions as MonitorEchartOptions}
          />
          {this.markAreaIconPosition
            .filter(item => item.show)
            .map((item, index) => (
              <div
                key={index}
                style={{
                  left: `${item.x}px`,
                  top: `${item.y}px`,
                }}
                class='mark-area-icon'
              >
                <span class='icon-monitor icon-mc-fault' />
              </div>
            ))}
        </div>
        <ListLegend
          legendData={this.legendData}
          onSelectLegend={this.handleSelectLegend}
        />
        <div class='table-wrap'>
          <bk-input
            v-model={this.searchValue}
            clearable={true}
            placeholder={this.$t('请输入事件名称')}
            right-icon='bk-icon icon-search'
          />
          <bk-table
            class='mt-12'
            data={this.tableData}
          >
            <div slot='empty'>
              <EmptyStatus
                type={this.emptyType}
                onOperation={this.handleOperation}
              />
            </div>
            {this.tableColumns.map(item => (
              <bk-table-column
                key={item.prop}
                label={item.label}
                prop={item.prop}
                {...{ props: item.props }}
                formatter={item?.formatter || null}
                min-width={item.minWidth}
              />
            ))}
          </bk-table>
        </div>
      </div>
    );
  }
}

export default ofType<ILineEchartProps>().convert(AlarmEventChart);
