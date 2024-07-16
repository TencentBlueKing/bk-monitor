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
import { Component } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import PieLegend from '../../components/chart-legend/pie-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { MONITOR_PIE_OPTIONS } from '../../constants';
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

import './pie-echart.scss';

interface IPieEchartProps {
  panel: PanelModel;
}
@Component
class PieChart extends CommonSimpleChart {
  height = 100;
  width = 300;
  showHeaderMoreTool = false;
  needResetChart = true;
  inited = false;
  metrics: IExtendMetricData[];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  chartOption: MonitorEchartOptions;
  legendData = [];
  panelTitle = '';

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
      const viewOptions = {
        ...this.viewOptions,
      };
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc](
            {
              ...item.data,
              ...params,
              view_options: {
                ...viewOptions,
              },
            },
            { needMessage: false }
          )
          .then(res => {
            const seriesData = res.data || [];
            this.panelTitle = res.name;
            this.updateChartData(seriesData);
            this.clearErrorMsg();
            return true;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList);
      if (res) {
        this.inited = true;
        this.empty = false;
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
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    const legendList = [];
    const dataList = [];
    srcData.forEach(item => {
      const { name, value, color, borderColor } = item;
      legendList.push({ name, value, color, borderColor, show: true });
      dataList.push({ name, value, itemStyle: { color } });
    });

    this.legendData = legendList;
    const echartOptions = deepClone(MONITOR_PIE_OPTIONS);
    this.chartOption = Object.freeze(
      deepmerge(echartOptions, {
        series: [
          {
            label: {
              show: false,
              position: 'center',
            },
            labelLine: {
              normal: {
                show: false,
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
    this.handleSelectPieLegend({ option: this.chartOption, actionType, item });
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
  render() {
    return (
      <div
        class='pie-echart'
        onMouseenter={() => (this.showHeaderMoreTool = true)}
        onMouseleave={() => (this.showHeaderMoreTool = false)}
      >
        <ChartHeader
          class='draggable-handle'
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          showMore={this.showHeaderMoreTool}
          title={this.panelTitle}
          onMenuClick={this.handleMenuToolsSelect}
          onUpdateDragging={() => this.panel.updateDraging(false)}
        />
        {!this.empty ? (
          <div class='pie-echart-content right-legend'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                options={this.chartOption}
              />
            </div>
            {
              <div class='chart-legend right-legend'>
                <PieLegend
                  legendData={this.legendData as any}
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

export default ofType<IPieEchartProps>().convert(PieChart);
