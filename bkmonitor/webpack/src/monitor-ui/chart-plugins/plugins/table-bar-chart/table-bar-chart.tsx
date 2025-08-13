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
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { MONITOR_BAR_OPTIONS } from '../../constants';
import { ChartLoadingMixin, IntersectionMixin, LegendMixin, ResizeMixin, ToolsMixin } from '../../mixins';
import { createImg, setStyle } from '../../utils';
import BaseEchart from '../monitor-base-echart';

import type { MonitorEchartOptions, PanelModel } from '../../typings';
import type { ITableDataItem } from '../../typings/table-chart';
import type { IMenuItem, ITableColumn, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings';

import './table-bar-chart.scss';

const option: MonitorEchartOptions = {
  animation: false,
  color: ['#73C2A8', '#4051A3'],
  xAxis: {
    show: true,
    type: 'time',
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
  { name: 'Limits', max: '2.7%', min: '1.1%', avg: '1.8%', total: '107.7%', color: '#73C2A8', show: true },
  { name: 'Requests', max: '2.8%', min: '1.1%', avg: '1.8%', total: '105.6%', color: '#4051A3', show: true },
];

interface INumberChartProps {
  panel: PanelModel;
}
@Component
class TableBarChart extends Mixins<
  ChartLoadingMixin & ChartLoadingMixin & IntersectionMixin & LegendMixin & ResizeMixin & ToolsMixin
>(IntersectionMixin, ChartLoadingMixin, ChartLoadingMixin, LegendMixin, ToolsMixin, ResizeMixin) {
  @Prop({ required: true }) panel: PanelModel;
  @Ref() scrollRef: HTMLElement;
  @Ref() baseChartRef: InstanceType<typeof BaseEchart>;

  showHeaderMoreTool = false;

  legendData = legendData;
  customOptions: MonitorEchartOptions = deepmerge(MONITOR_BAR_OPTIONS, option, {
    arrayMerge: (_, srcArr) => srcArr,
  });

  /** 图表数据 */
  tableData: ITableDataItem[] = [];

  /** 表格列数据 */
  columns: ITableColumn[] = [];

  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 12,
    limit: 6,
  };

  /**
   * @description: 获取图表数据
   */
  async getPanelData() {
    this.unregisterObserver();
    this.handleLoadingChange(true);
    const data = await this.mockData().finally(() => this.handleLoadingChange(false));
    data && this.updateChartData(data);
  }

  handleTimeRangeChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }

  mockData() {
    return new Promise(resolve => {
      const data = {
        total: 1736,
        tableData: new Array(10).fill({
          Timeline: 'Timeline',
          Events: '1001_log_nginx',
          detail: {
            url: '/',
            value: '详情',
          },
        }),
        columns: [
          { type: 'string', id: 'Timeline', name: 'Timeline' },
          { type: 'string', id: 'Events', name: 'Events' },
          { type: 'link', id: 'detail', name: '操作', props: { width: 80 } },
        ],
        chartData: [
          {
            datapoints: [],
          },
          {
            datapoints: [],
          },
        ],
      };
      const linePoit = data.chartData[0].datapoints;
      const barPoit = data.chartData[1].datapoints;
      let i = 0;
      const time1 = +new Date();
      const interval = 1000 * 60;
      while (i < 7) {
        const value = Math.random() * 10;
        linePoit.push([time1 + i * interval, value + 3]);
        barPoit.push([time1 + i * interval, value]);
        i += 1;
      }
      setTimeout(() => resolve(data), 1000);
    });
  }
  getPageData() {
    return new Promise(resolve => {
      const data = new Array(10).fill({
        Timeline: `Timeline-${+new Date()}`,
        Events: '1001_log_nginx',
        detail: {
          url: '/',
          value: '详情',
        },
      });
      setTimeout(() => resolve(data), 1000);
    });
  }

  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    this.tableData = srcData.tableData;
    this.columns = srcData.columns;
    const data = {
      xAxis: {
        show: true,
        type: 'time',
        data: srcData.chartData[0].datapoints.map(item => item[0]),
      },
      series: [
        {
          data: srcData.chartData[0].datapoints,
          type: 'bar',
          colorBy: 'data',
          name: 'Limits',
          zlevel: 100,
        },
        {
          data: srcData.chartData[1].datapoints,
          type: 'bar',
          colorBy: 'data',
          barGap: '-100%',
          barCategoryGap: '50%',
          name: 'Requests',
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
        this.handleSaveImage();
        break;
      case 'fullscreen': // 大图检索
        // this.handleFullScreen();
        break;
      case 'area': // 面积图
        // this.baseChart?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        // this.baseChart?.handleSetYAxisSetScale(!menuItem.checked);
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
   * @description: 截图处理
   */
  async handleSaveImage() {
    await this.$nextTick();
    /** 存在滚动 */
    if (this.scrollRef.scrollHeight > this.scrollRef.clientHeight) {
      const targetEl = this.$el.cloneNode(true) as HTMLElement;
      const scrollWrap = targetEl.querySelector('.table-bar-chart-contain') as HTMLElement;
      const baseChartUrl = await this.handleStoreImage('chart-img.png', this.baseChartRef.$el as HTMLElement, true);
      const imgEl = createImg(baseChartUrl as string);
      const chartInstance = targetEl.querySelector('.chart-instance');
      const chartEl = targetEl.querySelector('.base-chart');
      chartInstance.replaceChild(imgEl, chartEl);
      setStyle(targetEl, {
        position: 'absolute',
        top: '0',
        left: '0',
        height: 'auto',
      });
      setStyle(scrollWrap, { overflow: 'initial' });
      this.$el.appendChild(targetEl);
      await this.handleStoreImage(this.panel.title, targetEl);
      this.$el.removeChild(targetEl);
    } else {
      this.handleStoreImage(this.panel.title);
    }
  }

  /**
   * @description: 切换分页
   * @param {number} page
   */
  handlePageChange(page: number) {
    this.handleLoadingChange(true);
    this.getPageData().then(data => {
      this.handleLoadingChange(false);
      this.tableData = data as ITableDataItem[];
      this.pagination.current = page;
    });
  }

  render() {
    const { legend } = this.panel.options;
    return (
      <div
        class='table-bar-chart-wrap monitor-echart-common'
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
        <div
          ref='scrollRef'
          class='table-bar-chart-contain'
        >
          <div
            class={[
              'monitor-echart-common-content',
              'bar-chart-wrap',
              { 'right-legend': legend?.placement === 'right' },
            ]}
          >
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChartRef'
                width={this.width}
                height={this.height}
                class='base-chart'
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
          <CommonTable
            checkable={false}
            columns={this.columns}
            data={this.tableData}
            defaultSize='small'
            pagination={this.pagination}
            paginationType='simple'
            onPageChange={this.handlePageChange}
          />
        </div>
      </div>
    );
  }
}

export default ofType<INumberChartProps>().convert(TableBarChart);
