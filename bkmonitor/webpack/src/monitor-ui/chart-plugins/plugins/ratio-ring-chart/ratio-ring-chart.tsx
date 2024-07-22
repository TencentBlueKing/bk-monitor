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
import { Component, InjectReactive, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import Big from 'big.js';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import bus from 'monitor-common/utils/event-bus';
import { deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import RatioLegend from '../../components/chart-legend/ratio-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { MONITOR_PIE_OPTIONS } from '../../constants';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';

import type {
  IExtendMetricData,
  ILegendItem,
  IMenuItem,
  LegendActionType,
  MonitorEchartOptions,
  PanelModel,
} from '../../typings';

import './ratio-ring-chart.scss';
/** 传递接口数据key */
const ORIGINAL_DATA_KEY = 'ORIGINAL_DATA_KEY';
const LEGEND_ROW_HEIGHT = 26;
interface IRatioRingChartProps {
  panel: PanelModel;
}
@Component
class RatioRingChart extends CommonSimpleChart {
  @Ref() chartLegend: HTMLElement;

  height = 300;
  width = 288;
  needResetChart = true;
  isLegendFullContainer = false;
  legendData = [];
  inited = false;
  metrics: IExtendMetricData[];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  chartOption: MonitorEchartOptions;
  panelTitle = '';
  defaultColors = Object.freeze([
    '#699DF4',
    '#F7B936',
    '#1788C9',
    '#C8E74A',
    '#FF2D23',
    '#57AC3E',
    '#FF5422',
    '#8C00A9',
    '#A91947',
    '#FB962E',
  ]);

  // 是否在分屏展示
  @InjectReactive('isSplitPanel') isSplitPanel: boolean;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  /** 是否隐藏中间文字 */
  get hideLabel() {
    return this.panel.options?.hideLabel || false;
  }

  /**
   * @desc 设置图例高度
   */
  handleResetLegendHeight() {
    const elem = this.$refs.chartLegend as HTMLDivElement;
    if (!elem) return;
    const containerHeight = elem.getBoundingClientRect()?.height || 0;
    const legendLen = this.legendData.length;
    this.isLegendFullContainer = legendLen * LEGEND_ROW_HEIGHT > containerHeight;
  }
  /**
   * @description: 获取图表数据
   */
  async getPanelData(start_time?: string, end_time?: string) {
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params,
              view_options: {
                ...this.viewOptions,
              },
            },
            { needMessage: false }
          )
          .then(res => {
            const seriesData = res.data || [];
            this.panelTitle = res.name;
            this.updateChartData(seriesData);
            if (!seriesData.length) return false;
            this.clearErrorMsg();
            return true;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList);
      if (res?.every?.(item => item)) {
        this.inited = true;
        this.empty = false;
        this.$nextTick(() => {
          this.handleResetLegendHeight();
        });
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }
  /**
   * 处理计算百分比精度问题
   * @param value 当前值
   * @param total 总数
   * @returns string
   */
  handleDivide(value: number, total: number): string {
    return new Big(value).div(total).times(100).toFixed(2).replace('.00', '');
  }
  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    let totalValue = 0;
    const legendList = [];
    const dataList = [];
    srcData.forEach((item, index) => {
      const defaultColor = this.defaultColors[index % this.defaultColors.length];
      const { name, value, color = defaultColor, borderColor = defaultColor } = item;
      totalValue = totalValue + value;
      legendList.push({ name, value, color, borderColor, show: true });
      dataList.push({ name, value, itemStyle: { color }, [ORIGINAL_DATA_KEY]: item });
    });
    this.legendData = legendList;
    const echartOptions = deepClone(MONITOR_PIE_OPTIONS);
    this.chartOption = Object.freeze(
      deepmerge(echartOptions, {
        series: [
          {
            emphasis: {
              label: {
                show: !this.hideLabel,
                fontWeight: 'bold',
                formatter: params => {
                  const ratio = this.handleDivide(+params.value, +totalValue);
                  return `${ratio}%\n${params.name}`;
                },
              },
            },
            label: {
              show: !this.hideLabel,
              position: 'center',
              fontWeight: 'bold',
              formatter: params => {
                if (params.dataIndex === 0) {
                  const ratio = this.handleDivide(+params.value, +totalValue);
                  return `${ratio}%\n${params.name}`;
                }
                return '';
              },
            },
            radius: ['45%', '70%'],
            data: dataList,
            type: 'pie',
          },
        ],
      })
    ) as MonitorEchartOptions;
  }
  /**
   * @description: 选中图例触发事件
   * @param {LegendActionType} actionType 事件类型
   * @param {ILegendItem} item 当前选中的图例
   */
  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    const { needResetChart, chartOption, hideLabel } = this;
    const option = chartOption;
    // 鼠标悬浮图例高亮选中
    if (['highlight', 'downplay'].includes(actionType) && item.show) {
      this.handleToggleLabelShow(actionType !== 'highlight');
    }

    this.handleSelectPieLegend({ actionType, item, option, needResetChart, hideLabel });
  }
  /**
   * @description: 鼠标进入选中图例
   */
  handleMouseover() {
    this.handleToggleLabelShow(false);
  }
  /**
   * @description: 鼠标离开图例
   */
  handleMouseout() {
    this.handleToggleLabelShow(true);
  }
  /**
   * @description: 鼠标进入选中图例
   * @param {Boolean} isShow 圆环中心是否显示label
   */
  handleToggleLabelShow(isShow: boolean) {
    (this.$refs.baseChart as any).instance.setOption({
      series: {
        label: {
          show: this.hideLabel ? false : isShow,
        },
      },
    });
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
        // (this.$refs.baseChart as BaseEchart)?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        // (this.$refs.baseChart as BaseEchart)?.handleSetYAxisSetScale(!menuItem.checked);
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
  /**
   * 处理点击跳转
   * @param arg 图表数据
   */
  handleClickChart(arg: Record<string, any>) {
    if (!this.readonly && !!arg.data) {
      const itemData = arg.data[ORIGINAL_DATA_KEY];
      if (!itemData.link) return;
      const { link } = itemData;
      if (link.target === 'event') {
        if (this.isSplitPanel) {
          const route = this.$router.resolve({
            path: link.url,
          });
          window.open(location.href.replace(location.pathname, '/').replace(location.hash, '') + route.href);
        } else {
          bus.$emit(link.key, link);
        }
        return;
      }
      window.open(link.url, random(10));
    }
  }
  render() {
    return (
      <div class='ratio-ring-chart'>
        <ChartHeader
          class='draggable-handle'
          draging={this.panel.draging}
          isInstant={this.panel.instant && this.showHeaderMoreTool}
          metrics={this.metrics}
          showMore={false}
          title={this.panelTitle}
          onMenuClick={this.handleMenuToolsSelect}
          onUpdateDragging={() => this.panel.updateDraging(false)}
        />
        {!this.empty ? (
          <div class='ratio-ring-chart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                options={this.chartOption}
                onClick={this.handleClickChart}
                onMouseout={this.handleMouseout}
                onMouseover={this.handleMouseover}
              />
            </div>
            {
              <div
                ref='chartLegend'
                class='chart-legend right-legend'
              >
                <RatioLegend
                  style={`height:${this.isLegendFullContainer ? '100%' : 'auto'}`}
                  legendData={this.legendData as any}
                  percent={this.panel.percent}
                  onSelectLegend={this.handleSelectLegend}
                />
              </div>
            }
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<IRatioRingChartProps>().convert(RatioRingChart);
