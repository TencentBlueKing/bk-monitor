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
import { Component, Emit, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/cancel';
import { alertDateHistogram } from 'monitor-api/modules/alert';
import { Debounce } from 'monitor-common/utils/utils';
import ListLegend from 'monitor-ui/chart-plugins/components/chart-legend/common-legend';
import {
  ChartLoadingMixin,
  ErrorMsgMixins,
  IntersectionMixin,
  LegendMixin,
  ResizeMixin,
  ToolsMixin,
} from 'monitor-ui/chart-plugins/mixins';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';

import { generateFormatterFunc, handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { DEFAULT_SEVERITY_LIST, EAlertLevel, EStatusType, handleYAxisLabelFormatter } from '../utils';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IAlarmGraphConfig } from '../type';
import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './home-alarm-chart.scss';

interface IHomeAlarmChartEvents {
  onMenuClick: any;
  onSeverityChange: any;
}
interface IHomeAlarmChartProps {
  config: IAlarmGraphConfig;
  currentActiveId: number;
  severityProp?: Array<string>;
  timeRange: TimeRangeType;
}

const handleSetTooltip = params => {
  // 获取时间并格式化
  const pointTime = dayjs.tz(Number(params[0].axisValue)).format('YYYY-MM-DD HH:mm:ss');

  // 构建每个数据点的 HTML 列表项
  const liHtmlList = params
    .map(item => {
      return `
          <li class="tooltips-content-item" style="--series-color: ${item.color}">
              <span class="item-series" style="background-color:${item.color};"></span>
              <span class="item-name">${item.seriesName}:</span>
              <span class="item-value">${item.value[1]}</span>
          </li>`;
    })
    .join('');

  // 构建 tooltip 的 HTML
  return `
      <div class="monitor-chart-tooltips">
          <p class="tooltips-header">${pointTime}</p>
          <ul class="tooltips-content">${liHtmlList}</ul>
      </div>`;
};

@Component
class HomeAlarmChart extends Mixins<
  ChartLoadingMixin & ErrorMsgMixins & IntersectionMixin & LegendMixin & ResizeMixin & ToolsMixin
>(IntersectionMixin, ChartLoadingMixin, ToolsMixin, ResizeMixin, LegendMixin, ErrorMsgMixins) {
  @Prop({ default: () => ({}) }) config: IAlarmGraphConfig;
  @Prop() currentActiveId: number;
  @Prop({ default: () => ['', ''] }) timeRange: TimeRangeType;
  @Prop({ default: () => DEFAULT_SEVERITY_LIST }) severityProp;
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
  colorList = ['#F59789', '#6FC5BF', '#DCDEE5'];
  severityList = [
    {
      name: 'FATAL',
      display_name: window.i18n.tc('致命'),
    },
    {
      name: 'WARNING',
      display_name: window.i18n.tc('预警'),
    },
    {
      name: 'INFO',
      display_name: window.i18n.tc('提醒'),
    },
  ];
  loading = false;
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
  severityValue = DEFAULT_SEVERITY_LIST;
  options = {};
  chartOption = {
    color: this.colorList,
    tooltip: {
      className: 'new-home-chart-tooltips',
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: handleSetTooltip,
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
    yAxis: {
      type: 'value',
      minInterval: 1,
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

  formatterFunc = null; // x轴格式化函数

  created() {
    this.severityValue = this.severityProp.slice();
  }

  /** 更多操作 */
  @Emit('menuClick')
  handleMenuClick(item) {
    this.menuPopoverRef?.hideHandler();
    return item;
  }

  // 告警等级切换
  @Emit('severityChange')
  @Debounce(100)
  changeSelect(val) {
    this.getPanelData();
    return val;
  }

  @Watch('timeRange')
  handleTimeRangeChange(newTime, oldTime) {
    const [newS, newE] = newTime;
    const [oldS, oldE] = oldTime;
    if (newS === oldS && newE === oldE) return;
    this.getPanelData();
  }
  /**
   * @description: 获取图表数据
   */
  @Debounce(100)
  async getPanelData() {
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterObserver();
      }
      this.registerObserver();
      return;
    }
    this.formatterFunc = generateFormatterFunc(this.timeRange);
    if (this.init) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    this.loading = true;
    try {
      this.unregisterObserver();
      const [start, end] = handleTransformToTimestamp(this.timeRange);
      const conditions = [{ key: 'strategy_id', value: this.config.strategy_ids || [] }];
      // 下拉切换告警级别筛选
      if (this.severityValue.length !== this.severityList.length) {
        conditions.push({ key: 'severity', value: this.severityValue.map(val => EAlertLevel[val]) });
      }
      const { series } = await alertDateHistogram(
        {
          bk_biz_ids: [this.currentActiveId],
          conditions,
          start_time: start,
          end_time: end,
        },
        {
          cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
          needMessage: false,
        }
      );
      if (series?.length) {
        this.empty = false;
        this.updateChartData(series);
      } else {
        this.empty = true;
        this.emptyText = window.i18n.tc('暂无数据');
      }
    } catch {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
    } finally {
      this.cancelTokens = [];
      this.loading = false;
    }
    this.handleLoadingChange(false);
  }
  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
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
        xAxis: {
          type: 'category',
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            formatter: v => this.formatterFunc(dayjs.tz(+v)),
            fontSize: 12,
            color: '#979BA5',
          },
        },
      })
    ) as MonitorEchartOptions;
  }

  render() {
    return (
      <div class='home-alarm-chart'>
        <div class='alarm-chart-header'>
          {this.config.status.some(({ status }) => EStatusType[status]) && (
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
                {(this.config.status || []).map(
                  (item, index) =>
                    EStatusType[item.status] && (
                      <div
                        key={item.name + index}
                        class={`tips-item ${item.status}`}
                      >
                        <span class='tips-item-tag'>{EStatusType[item.status]}</span>
                        <span class='txt'>{item.name}</span>
                      </div>
                    )
                )}
              </div>
            </bk-popover>
          )}
          <span
            class='header-title'
            v-bk-overflow-tips
          >
            {this.config.name}
          </span>
          <bk-select
            class='chart-header-select'
            v-model={this.severityValue}
            behavior='simplicity'
            clearable={false}
            multiple
            on-Change={this.changeSelect}
          >
            {this.severityList.map(item => (
              <bk-option
                id={item.name}
                key={item.name}
                disabled={this.severityValue.length === 1 && this.severityValue.includes(item.name)}
                name={item.display_name}
              />
            ))}
          </bk-select>
          <bk-popover
            ref='menuPopover'
            class='home-chart-more-popover'
            ext-cls='new-home-popover'
            tippy-options={{
              trigger: 'click',
            }}
            arrow={false}
            offset={'0, 0'}
            placement='bottom-start'
            theme='light common-monitor'
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
          <div class='home-alarm-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              {!this.loading ? (
                this.init && (
                  <BaseEchart
                    ref='baseChart'
                    width={this.width}
                    height={this.height}
                    needZrClick={true}
                    options={this.options}
                    onZrClick={item =>
                      this.handleMenuClick({
                        name: window.i18n.tc('查看详情'),
                        checked: false,
                        id: 'detail',
                        xAxis: item.xAxis,
                      })
                    }
                  />
                )
              ) : (
                <div class='loading-chart'>
                  <div class='loading-img' />
                </div>
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
export default ofType<IHomeAlarmChartProps, IHomeAlarmChartEvents>().convert(HomeAlarmChart);
