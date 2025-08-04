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

import deepmerge from 'deepmerge';

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { MONITOR_LINE_OPTIONS } from '../../constants';
import { ChartLoadingMixin, IntersectionMixin, LegendMixin, ResizeMixin, ToolsMixin } from '../../mixins';
import BaseEchart from '../monitor-base-echart';

import type { ICommonCharts, IMenuItem, MonitorEchartOptions, PanelModel } from '../../typings';

import './line-bar-echart.scss';

const option: MonitorEchartOptions = {
  animation: false,
  xAxis: {
    type: 'time',
    minInterval: 0,
    axisLabel: {
      fontSize: 12,
      color: '#979BA5',
      showMinLabel: false,
      showMaxLabel: false,
      align: 'center',
      interval: 0,
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
  },
  series: [],
};

const legendData = [
  { name: 'cpu0', max: '2.7%', min: '1.1%', avg: '1.8%', total: '107.7%', color: '#7EB26D', show: true },
  { name: 'cpu1', max: '2.8%', min: '1.1%', avg: '1.8%', total: '105.6%', color: '#EAB839', show: true },
];

interface ILineEchartProps {
  panel: PanelModel;
}
@Component
class LineBarEChart
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
  @Ref() baseChart: InstanceType<typeof BaseEchart>;
  customOptions: MonitorEchartOptions = deepmerge(MONITOR_LINE_OPTIONS, option);
  showHeaderMoreTool = false;
  legendData = legendData;
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
          datapoints: [],
        },
        {
          datapoints: [],
        },
      ];
      const linePoit = data[0].datapoints;
      const barPoit = data[1].datapoints;
      let i = 0;
      const time1 = +new Date() + 3000;
      const time2 = +new Date();
      const interval = 1000;
      while (i < 20) {
        linePoit.push([time1 + i * interval, Math.random() * 10]);
        barPoit.push([time2 + i * interval, Math.random() * 5]);
        i += 1;
      }
      setTimeout(() => resolve(data), 1000);
    });
  }

  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    const data = {
      series: [
        {
          data: srcData[0].datapoints,
          type: 'line',
          itemStyle: {
            opacity: 0,
          },
          name: 'cpu1',
          zlevel: 100,
        },
        {
          data: srcData[1].datapoints,
          type: 'bar',
          colorBy: 'data',
          barCategoryGap: '50%',
          name: 'cpu0',
          zlevel: 100,
        },
      ],
    };
    const updateOption = deepmerge(option, data);
    this.customOptions = deepmerge(this.customOptions, updateOption);
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
  render() {
    const { legend } = this.panel.options;
    return (
      <div
        class='line-bar-echart monitor-echart-common'
        onMouseenter={() => (this.showHeaderMoreTool = true)}
        onMouseleave={() => (this.showHeaderMoreTool = false)}
      >
        <ChartHeader
          class='draggable-handle'
          isInstant={this.panel.instant}
          showMore={this.showHeaderMoreTool}
          subtitle={'这是一个副标题'}
          title={'这是一个标题'}
          onMenuClick={this.handleMenuToolsSelect}
        />
        <div class={`monitor-echart-common-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
          <div
            ref='chart'
            class='chart-instance'
          >
            <BaseEchart
              ref='baseChart'
              width={this.width}
              height={this.height}
              options={this.customOptions}
            />
          </div>
          {legend.displayMode !== 'hidden' && (
            <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
              {legend?.displayMode === 'table' ? (
                <TableLegend
                  legendData={this.legendData}
                  onSelectLegend={this.handleSelectLegend}
                />
              ) : (
                <ListLegend
                  legendData={this.legendData}
                  onSelectLegend={this.handleSelectLegend}
                />
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}

export default ofType<ILineEchartProps>().convert(LineBarEChart);
