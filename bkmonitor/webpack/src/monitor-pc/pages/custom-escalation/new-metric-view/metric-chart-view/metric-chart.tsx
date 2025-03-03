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
import { Component, Mixins, Prop, Watch, Provide } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { toPng } from 'html-to-image';
import { CancelToken } from 'monitor-api/index';
import { alertDateHistogram } from 'monitor-api/modules/alert';
import { dimensionUnifyQuery, graphUnifyQuery, logQuery } from 'monitor-api/modules/grafana';
import { Debounce } from 'monitor-common/utils/utils';
import { generateFormatterFunc, handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import ChartHeader from 'monitor-ui/chart-plugins/components/chart-title/chart-title';
import StatusTab from 'monitor-ui/chart-plugins/plugins/apm-custom-graph/status-tab';
import CommonSimpleChart from 'monitor-ui/chart-plugins/plugins/common-simple-chart';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';
import { downFile, handleRelateAlert, reviewInterval } from 'monitor-ui/chart-plugins/utils';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import { mockChart } from './data';
import { metricData } from './mock-data';

import type { ICommonCharts, IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import './metric-chart.scss';
const APM_CUSTOM_METHODS = ['SUM', 'AVG', 'MAX', 'MIN', 'INC'];

interface INewMetricChartProps {
  chartHeight?: number;
  isToolIconShow?: boolean;
  panel?: PanelModel;
}
interface INewMetricChartEvents {
  onMenuClick?: any;
  onDrillDown?: any;
}
/** 图表 - 曲线图 */
@Component
class NewMetricChart extends CommonSimpleChart {
  // 图表panel实例
  // @Prop({ default: false }) readonly panel: PanelModel;
  @Prop({ default: 300 }) chartHeight: number;
  @Prop({ default: true }) isToolIconShow: boolean;
  methodList = APM_CUSTOM_METHODS.map(method => ({
    id: method,
    name: method,
  }));
  width = 300;
  init = true;
  metrics = metricData;
  collectIntervalDisplay = '1m';
  cancelTokens = [];
  options = {
    tooltip: {
      className: 'new-metric-chart-tooltips',
      trigger: 'axis',
    },
    grid: {
      top: '6%',
      left: '1%',
      right: '1%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      axisTick: {
        show: false,
      },
      boundaryGap: false,
      axisLabel: {
        fontSize: 12,
        color: '#979BA5',
        showMinLabel: false,
        showMaxLabel: false,
        align: 'left',
      },
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
    },
    series: mockChart.series,
  };
  empty = false;
  emptyText = window.i18n.tc('暂无数据');
  // x轴格式化函数
  formatterFunc = null;
  method = 'SUM';
  loading = false;

  /** 操作的icon列表 */
  get handleIconList() {
    return [
      { id: 'fullscreen', text: window.i18n.tc('全屏'), icon: 'icon-mc-full-screen' },
      { id: 'drillDown', text: window.i18n.tc('维度下钻'), icon: 'icon-dimension-line' },
    ];
  }
  /** 更多里的操作列表 */
  get menuList() {
    return ['save', 'more', 'explore', 'area', 'drill-down', 'relate-alert'];
  }
  /** 拉伸的时候图表重新渲染 */
  @Watch('chartHeight')
  handleHeightChange() {
    this.handleResize();
  }
  /** 切换计算的Method */
  handleMethodChange(method: (typeof APM_CUSTOM_METHODS)[number]) {
    this.method = method;
    // this.customScopedVars = {
    //   method,
    // };
    // this.getPanelData();
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
        this.unregisterOberver();
      }
      this.registerObserver();
      return;
    }
    this.formatterFunc = generateFormatterFunc(this.timeRange);
    if (this.init) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    this.loading = true;
    try {
      this.unregisterOberver();
      // const [start, end] = handleTransformToTimestamp(this.timeRange);
      // const params = {
      //   bk_biz_id: 105,
      //   start_time: 1740996743,
      //   end_time: 1741000343,
      //   expression: 'A',
      //   down_sample_range: '9s',
      //   query_configs: this.panel.targets[0]?.query_configs,
      // };
      // const { series } = await graphUnifyQuery(params, {
      //   cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
      //   needMessage: false,
      // });
      // console.log(series, params, 'variablesService', this.panel.targets);
      // if (series?.length) {
      //   this.empty = false;
      //   this.updateChartData(this.options);
      // } else {
      //   this.empty = true;
      //   this.emptyText = window.i18n.tc('暂无数据');
      // }
      this.updateChartData(this.options);
    } catch {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
    } finally {
      this.cancelTokens = [];
      this.loading = false;
    }
    this.handleLoadingChange(false);
  }

  updateChartData(srcData) {
    this.options = srcData;
  }
  /**
   * @description: 下载图表为png图片
   * @param {string} title 图片标题
   * @param {HTMLElement} targetEl 截图目标元素 默认组件$el
   * @param {*} customSave 自定义保存图片
   */
  handleStoreImage(title: string, targetEl?: HTMLElement, customSave = false) {
    const el = targetEl || (this.$el as HTMLElement);
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }
  getCopyPanel() {}
  /** 工具栏各个icon的操作 */
  handleIconClick(menuItem) {
    switch (menuItem.id) {
      /** 维度下钻 */
      case 'drillDown':
        this.$emit('drillDown');
        break;
      // 保存到仪表盘
      case 'save':
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.panel.title || '测试');
        }, 300);
        break;
      case 'fullscreen': {
        // 大图检索
        const copyPanel = this.getCopyPanel();
        this.handleFullScreen(copyPanel as any);
        break;
      }

      case 'area': // 面积图
        (this.$refs.baseChart as any)?.handleTransformArea(menuItem.checked);
        break;
      case 'set': // 转换Y轴大小
        (this.$refs.baseChart as any)?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': {
        // 跳转数据检索
        const copyPanel = this.getCopyPanel();
        this.handleExplore(copyPanel as any, {});
        break;
      }
      case 'strategy': {
        // 新增策略
        const copyPanel = this.getCopyPanel();
        this.handleAddStrategy(copyPanel as any, null, {}, true);
        break;
      }
      case 'relate-alert': {
        // 大图检索
        const copyPanel = this.getCopyPanel();
        handleRelateAlert(copyPanel as any, this.timeRange);
        break;
      }
      default:
        break;
    }
  }
  render() {
    console.log(this.panel, 'this.panel');
    return (
      <div class='new-metric-chart'>
        <ChartHeader
          collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          // draging={this.panel.draging}
          isHoverShow={true}
          // isInstant={this.panel.instant}
          menuList={this.menuList as any}
          metrics={this.metrics}
          needMoreMenu={true}
          showMore={true}
          subtitle={this.panel.sub_title || ''}
          title={this.panel.title}
          onMenuClick={this.handleIconClick}
        >
          <span class='status-tab-view'>
            <StatusTab
              maxWidth={this.width - 300}
              statusList={this.methodList}
              value={this.method}
              onChange={this.handleMethodChange}
            />
          </span>
          {this.isToolIconShow && (
            <span
              class='icon-tool-list'
              slot='iconList'
            >
              {this.handleIconList.map(item => (
                <i
                  key={item.id}
                  class={`icon-monitor ${item.icon} menu-list-icon`}
                  v-bk-tooltips={{
                    content: this.$t(item.text),
                    delay: 200,
                  }}
                  onClick={() => this.handleIconClick(item)}
                ></i>
              ))}
            </span>
          )}
        </ChartHeader>
        {!this.empty ? (
          <div class='new-metric-chart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.init && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.chartHeight}
                  groupId={this.panel.dashboardId}
                  options={this.options}
                />
              )}
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
export default ofType<INewMetricChartProps, INewMetricChartEvents>().convert(NewMetricChart);
