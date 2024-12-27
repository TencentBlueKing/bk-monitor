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
import { Component, Emit, Prop, Ref, Mixins } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { alertDateHistogram } from 'monitor-api/modules/alert';
import { Debounce } from 'monitor-common/utils/utils';
import ListLegend from 'monitor-ui/chart-plugins/components/chart-legend/common-legend';
import {
  ChartLoadingMixin,
  ErrorMsgMixins,
  IntersectionMixin,
  LegendMixin,
  ResizeMixin,
  ToolsMxin,
} from 'monitor-ui/chart-plugins/mixins';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';

import { handleYAxisLabelFormatter, EStatusType } from '../utils';
import { chartData } from './data';

import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './home-alarm-chart.scss';

interface IHomeAlarmChartProps {
  config: object;
}

@Component
class HomeAlarmChart extends Mixins<ChartLoadingMixin & ToolsMxin & ResizeMixin & LegendMixin & ErrorMsgMixins>(
  IntersectionMixin,
  ChartLoadingMixin,
  ToolsMxin,
  ResizeMixin,
  LegendMixin,
  ErrorMsgMixins
) {
  @Prop({ default: () => ({}) }) config: object;
  @Ref('menuPopover') menuPopoverRef: HTMLDivElement;
  // 高度
  height = 100;
  // 宽度度
  width = 300;
  empty = false;
  init = true;
  cancelTokens = [];
  emptyText = window.i18n.tc('暂无数据');
  minBase = 0;
  colorList = ['#F8B4B4', '#A1E3BA', '#C4C6CC'];
  searchList = [
    {
      name: 'ABNORMAL',
      display_name: window.i18n.tc('致命'),
    },
    {
      name: 'RECOVERED',
      display_name: window.i18n.tc('预警'),
    },
    {
      name: 'CLOSED',
      display_name: window.i18n.tc('提醒'),
    },
  ];
  legendData = [];
  /** 更多操作列表 */
  menuList = [
    {
      name: window.i18n.tc('查看详情'),
      checked: false,
      id: 'detail',
    },
    {
      name: window.i18n.tc('编辑'),
      checked: false,
      id: 'edit',
    },
    {
      name: window.i18n.tc('删除'),
      checked: false,
      id: 'delete',
    },
  ];
  searchValue = ['ABNORMAL', 'RECOVERED', 'CLOSED'];
  options = {};
  chartOption = {
    color: this.colorList,
    tooltip: {
      className: 'new-home-chart-tooltips',
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
    },
    legend: {
      show: false,
    },
    grid: {
      containLabel: true,
      left: 16,
      right: 16,
      top: 10,
      bottom: 6,
      backgroundColor: 'transparent',
    },
    xAxis: {
      type: 'category',
      axisTick: {
        show: false,
      },
      axisLine: {
        show: false,
      },
      axisLabel: {
        formatter: (v: any) => {
          return dayjs.tz(+v).format('YYYY-MM-DD');
        },
        fontSize: 12,
        color: '#979BA5',
      },
    },
    yAxis: {
      type: 'value',
      splitLine: {
        show: true,
        lineStyle: {
          color: '#F0F1F5',
          type: 'solid',
        },
      },
      axisLabel: {
        formatter: (v: number) => handleYAxisLabelFormatter(v - this.minBase),
      },
    },
  };
  /** 更多操作 */
  @Emit('menuClick')
  handleMenuClick(item) {
    console.log(item);
    this.menuPopoverRef?.hideHandler();
    return item;
  }

  changeSelect(val: string[]) {
    console.log(val);
    this.getPanelData();
  }
  mounted() {
    this.getPanelData();
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(100)
  async getPanelData() {
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (this.init) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      // const seriesData = chartData.series;
      const { series } = await alertDateHistogram({
        bk_biz_ids: [2],
        conditions: [{ key: 'strategy_id', value: this.config.strategy_ids || [] }],
        query_string: '',
        start_time: 1734683156,
        end_time: 1735287956,
        interval: 'auto',
        bk_biz_id: 2,
      });
      console.log('seriesData', series);
      // const res = await aipHandle;
      this.updateChartData(series);
      // if (res) {
      //   this.init = true;
      //   this.empty = false;
      // } else {
      //   this.emptyText = window.i18n.tc('查无数据');
      //   this.empty = true;
      // }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
    }
    this.handleLoadingChange(false);
  }
  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    console.log(srcData, 'srcData');
    const legendList = [];
    const dataList = [];
    srcData.forEach((item, ind) => {
      const { data, display_name } = item;
      legendList.push({ name: display_name, color: this.colorList[ind], show: true });
      dataList.push({
        name: display_name,
        type: 'bar',
        stack: 'total',
        data: data,
      });
    });
    this.legendData = legendList;
    this.options = Object.freeze(
      deepmerge(this.chartOption, {
        series: dataList,
      })
    ) as MonitorEchartOptions;
  }

  render() {
    return (
      <div class='home-alarm-chart'>
        <div class='alarm-chart-header'>
          <bk-popover
            class='home-chart-tips-popover'
            ext-cls='new-home-tips'
            theme='light'
          >
            <span class='chart-tips'>
              <i class='icon-monitor icon-mind-fill' />
            </span>
            <div
              class='home-chart-tips-list'
              slot='content'
            >
              {(this.config.status || []).map(item => (
                <div
                  key={item.name}
                  class={`tips-item ${item.status}`}
                >
                  <span class='tips-item-tag'>{EStatusType[item.status]}</span>
                  <span class='txt'>{item.name}</span>
                </div>
              ))}
            </div>
          </bk-popover>
          <span
            class='header-title'
            v-bk-overflow-tips
          >
            {this.config.name}
          </span>
          <bk-select
            class='chart-header-select'
            v-model={this.searchValue}
            behavior='simplicity'
            clearable={false}
            multiple
            on-Change={this.changeSelect}
          >
            {this.searchList.map(item => (
              <bk-option
                id={item.name}
                key={item.name}
                name={item.display_name}
              />
            ))}
          </bk-select>
          <bk-popover
            ref='menuPopover'
            class='home-chart-more-popover'
            ext-cls='new-home-popover'
            arrow={false}
            offset={'0, 0'}
            placement='bottom-start'
            theme='light'
            trigger='click'
          >
            <span class='more-operation'>
              <i class='icon-monitor icon-mc-more' />
            </span>
            <div
              class='home-chart-more-list'
              slot='content'
            >
              {this.menuList.map(item => (
                <span
                  key={item.id}
                  class={`more-list-item ${item.id}`}
                  on-click={() => this.handleMenuClick(item)}
                >
                  {item.name}
                </span>
              ))}
            </div>
          </bk-popover>
        </div>
        {!this.empty ? (
          <div class={'home-alarm-content'}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.init && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  options={this.options}
                />
              )}
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
        <div class='chart-legend'>
          <ListLegend
            legendData={this.legendData}
            onSelectLegend={this.handleSelectLegend}
          />
        </div>
      </div>
    );
  }
}
export default ofType<IHomeAlarmChartProps>().convert(HomeAlarmChart);
