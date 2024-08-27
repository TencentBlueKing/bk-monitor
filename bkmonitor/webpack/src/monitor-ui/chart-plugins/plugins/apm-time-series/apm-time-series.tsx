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

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/index';
import { deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { reviewInterval } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';
import DetailsSide, { type EDataType } from './components/details-side';

import './apm-time-series.scss';

const eventHasId = (event: Event | any, id: string) => {
  let target = event.target;
  let has = false;
  while (target) {
    if (target.id === id) {
      has = true;
      break;
    }
    target = target?.parentNode;
  }
  return has;
};
@Component
export default class ApmTimeSeries extends TimeSeries {
  contextmenuInfo = {
    x: 0,
    y: 0,
    show: false,
    options: [
      { id: 'details', name: window.i18n.t('查看详情') },
      { id: 'topo', name: window.i18n.t('查看拓扑') },
    ],
    id: random(10),
    nearOutRight: false, // 鼠标右侧是否为页面边缘
    nearOutBottom: false, // 鼠标下方是否为页面边缘
    seriesIndex: -1, // 当前选中的seriesIndex
    dataIndex: -1, // 当前选中的dataIndex
  };

  detailsSideData = {
    show: false,
  };

  get apmMetric(): EDataType {
    return (this.panel.options?.apm_time_series?.metric || '') as EDataType;
  }

  get appName() {
    return this.panel.options?.apm_time_series?.app_name || '';
  }

  get serviceName() {
    return this.panel.options?.apm_time_series?.service_name || '';
  }

  /* 是否开启series的右键菜单 */
  get enableSeriesContextmenu() {
    return !!this.panel.options?.apm_time_series?.enableSeriesContextmenu;
  }
  /* 是否开启全局的右键菜单 */
  get enableContextmenu() {
    return !!this.panel.options?.apm_time_series?.enableContextmenu;
  }

  get detailsUnit() {
    return this.panel.options?.apm_time_series?.unit || '';
  }

  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
  async getPanelData(start_time?: string, end_time?: string) {
    this.cancelTokens.forEach(cb => cb?.());
    this.cancelTokens = [];
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    if (this.inited) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    if (!this.enableSelectionRestoreAll) {
      this.showRestore = !!start_time;
    }
    try {
      this.unregisterOberver();
      let series = [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params = {
        start_time: start_time ? dayjs(start_time).unix() : startTime,
        end_time: end_time ? dayjs(end_time).unix() : endTime,
      };
      if (this.bkBizId) {
        params = Object.assign({}, params, {
          bk_biz_id: this.bkBizId,
        });
      }
      const promiseList = [];
      const timeShiftList = ['', ...this.timeOffset];
      const interval = reviewInterval(
        this.viewOptions.interval,
        params.end_time - params.start_time,
        this.panel.collect_interval
      );
      const variablesService = new VariablesService({
        ...this.viewOptions,
        interval,
      });
      for (const time_shift of timeShiftList) {
        const noTransformVariables = !!this.panel?.options?.time_series?.noTransformVariables;
        const list = this.panel.targets.map(item => {
          const stack = item?.data?.stack || '';
          const newPrarams = {
            ...variablesService.transformVariables(
              item.data,
              {
                ...this.viewOptions.filters,
                ...(this.viewOptions.filters?.current_target || {}),
                ...this.viewOptions,
                ...this.viewOptions.variables,
                time_shift,
                interval,
              },
              noTransformVariables
            ),
            ...params,
            down_sample_range: this.downSampleRangeComputed(
              this.downSampleRange as string,
              [params.start_time, params.end_time],
              item.apiFunc
            ),
          };
          // 主机监控ipv6特殊逻辑 用于去除不必要的group_by字段
          if (item.ignore_group_by?.length && newPrarams.query_configs.some(set => set.group_by?.length)) {
            newPrarams.query_configs = newPrarams.query_configs.map(config => ({
              ...config,
              group_by: config.group_by.filter(key => !item.ignore_group_by.includes(key)),
            }));
          }
          return (this as any).$api[item.apiModule]
            [item.apiFunc](newPrarams, {
              cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
              needMessage: false,
            })
            .then(res => {
              this.$emit('seriesData', res);
              res.metrics && metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => ({
                  ...set,
                  stack,
                  name: `${this.timeOffset.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                    this.handleSeriesName(item, set) || set.target
                  }`,
                }))
              );
              this.clearErrorMsg();
              return true;
            })
            .catch(error => {
              this.handleErrorMsgChange(error.msg || error.message);
            });
        });
        promiseList.push(...list);
      }
      await Promise.all(promiseList).catch(() => false);
      this.metrics = metrics || [];
      if (series.length) {
        const maxXInterval = getSeriesMaxInterval(series);
        /* 派出图表数据包含的维度*/
        this.emitDimensions(series);
        this.series = Object.freeze(series) as any;
        if (this.onlyOneResult) {
          let hasResultSeries = false;
          series = series.filter(item => {
            const pass = !(hasResultSeries && item.alias === '_result_');
            pass && (hasResultSeries = true);
            return pass;
          });
        }
        if (this.nearSeriesNum) {
          series = series.slice(0, this.nearSeriesNum);
        }
        const seriesResult = series
          .filter(item => ['extra_info', '_result_'].includes(item.alias))
          .map(item => ({
            ...item,
            datapoints: item.datapoints.map(point => [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]]),
          }));
        let seriesList = this.handleTransformSeries(
          seriesResult.map((item, index) => ({
            name: item.name,
            cursor: 'auto',
            data: item.datapoints.reduce((pre: any, cur: any) => {
              pre.push([...cur].reverse());
              return pre;
            }, []),
            stack: item.stack || random(10),
            unit: this.panel.options?.unit || item.unit,
            markPoint: this.createMarkPointData(item, series),
            markLine: this.createMarkLine(index),
            markArea: this.createMarkArea(item, index),
            z: 1,
            traceData: item.trace_data ?? '',
          })) as any
        );
        const boundarySeries = seriesResult
          .map(item => this.handleBoundaryList(item, series))
          .flat(Number.POSITIVE_INFINITY);
        if (boundarySeries) {
          seriesList = [...seriesList.map((item: any) => ({ ...item, z: 6 })), ...boundarySeries];
        }
        seriesList = seriesList.map((item: any) => ({
          ...item,
          minBase: this.minBase,
          data: item.data.map((set: any) => {
            if (set?.length) {
              return [set[0], set[1] !== null ? set[1] + this.minBase : null];
            }
            return {
              ...set,
              value: [set.value[0], set.value[1] !== null ? set.value[1] + this.minBase : null],
            };
          }),
        }));
        this.seriesList = Object.freeze(seriesList) as any;
        // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
        // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
        // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
        const hasShowSymbol = seriesList.some(item => item.showSymbol);
        if (hasShowSymbol) {
          for (const item of seriesList) {
            item.data = item.data.map(set => {
              if (set?.symbolSize) {
                return {
                  ...set,
                  symbolSize: set.symbolSize > 6 ? 6 : 1,
                  itemStyle: {
                    borderWidth: set.symbolSize > 6 ? 6 : 1,
                    enabled: true,
                    shadowBlur: 0,
                    opacity: 1,
                  },
                };
              }
              return set;
            });
          }
        }
        const formatterFunc = this.handleSetFormatterFunc(seriesList[0].data);
        const { canScale, minThreshold, maxThreshold } = this.handleSetThreholds();

        const chartBaseOptions = MONITOR_LINE_OPTIONS;
        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        const isBar = this.panel.options?.time_series?.type === 'bar';
        const xInterval = getTimeSeriesXInterval(maxXInterval, this.width);
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: hasShowSymbol,
            color: isBar ? COLOR_LIST_BAR : COLOR_LIST,
            animationThreshold: 1,
            yAxis: {
              axisLabel: {
                formatter: seriesList.every((item: any) => item.unit === seriesList[0].unit)
                  ? (v: any) => {
                      if (seriesList[0].unit !== 'none') {
                        const obj = getValueFormat(seriesList[0].unit)(v, seriesList[0].precision);
                        return obj.text + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                      }
                      return v;
                    }
                  : (v: number) => this.handleYxisLabelFormatter(v - this.minBase),
              },
              splitNumber: this.height < 120 ? 2 : 4,
              minInterval: 1,
              scale: this.height < 120 ? false : canScale,
              max: v => Math.max(v.max, +maxThreshold),
              min: v => {
                let min = Math.min(v.min, +minThreshold);
                // 柱状图y轴不能以最小值作为起始点
                if (isBar) min = min <= 10 ? 0 : min - 10;
                return min;
              },
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}',
              },
              ...xInterval,
            },
            series: seriesList,
            tooltip: this.handleSetTooltip(),
            customData: {
              // customData 自定义的一些配置 用户后面echarts实例化后的配置
              maxXInterval,
            },
          })
        );
        this.handleDrillDownOption(this.metrics);
        this.inited = true;
        this.empty = false;
        if (!this.hasSetEvent && this.needSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
        setTimeout(() => {
          this.handleResize();
        }, 100);
      } else {
        this.inited = this.metrics.length > 0;
        this.emptyText = window.i18n.tc('暂无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    // 初始化刷新定时器
    if (!this.refleshIntervalInstance && this.refleshInterval) {
      this.handleRefleshIntervalChange(this.refleshInterval);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }

  /**
   * @description: 处理上下文菜单点击事件
   * @param params
   */
  handleContextmenu(params) {
    if (this.enableSeriesContextmenu) {
      const { offsetX, offsetY } = params.event;
      const { pageX, pageY } = params.event.event;
      const { clientHeight, clientWidth } = document.documentElement;
      this.contextmenuInfo = {
        ...this.contextmenuInfo,
        x: offsetX + 4,
        y: offsetY + 4,
        show: true,
        nearOutRight: pageX > clientWidth - 120,
        nearOutBottom: pageY > clientHeight - 80,
        seriesIndex: params.seriesIndex,
        dataIndex: params.dataIndex,
      };
      document.addEventListener('click', this.handleHideContextmenu);
    }
    setTimeout(() => {
      this.$refs.baseChart?.dispatchAction({
        type: 'highlight',
        seriesIndex: params.seriesIndex,
        dataIndex: params.dataIndex,
      });
    }, 200);
  }

  /* 整个图的右键菜单 */
  handleChartContextmenu(event: MouseEvent) {
    if (this.enableContextmenu) {
      const { offsetX, offsetY } = event;
      const { pageX, pageY } = event;
      const { clientHeight, clientWidth } = document.documentElement;
      this.contextmenuInfo = {
        ...this.contextmenuInfo,
        x: offsetX + 4,
        y: offsetY + 4,
        show: true,
        nearOutRight: pageX > clientWidth - 120,
        nearOutBottom: pageY > clientHeight - 80,
        seriesIndex: 0,
        dataIndex: 0,
      };
      document.addEventListener('click', this.handleHideContextmenu);
    }
  }

  /**
   * @description: 隐藏右键菜单事件
   * @param event
   */
  handleHideContextmenu(event: MouseEvent) {
    if (!eventHasId(event, this.contextmenuInfo.id)) {
      this.hideContextmenu();
    }
  }

  /**
   * @description: 隐藏右键菜单
   */
  hideContextmenu() {
    this.contextmenuInfo.show = false;
    document.removeEventListener('click', this.handleHideContextmenu);
    this.$refs.baseChart?.dispatchAction({
      type: 'downplay',
      seriesIndex: this.contextmenuInfo.seriesIndex,
      dataIndex: this.contextmenuInfo.dataIndex,
    });
  }

  /**
   * @description: 处理右键菜单点击事件
   * @param id
   */
  handleClickMenuItem(id: string) {
    if (id === 'details') {
      // TODO 详情
      this.detailsSideData.show = true;
    } else if (id === 'topo') {
      // TODO 拓扑图
    }
    this.hideContextmenu();
  }

  handleCloseDetails() {
    this.detailsSideData.show = false;
  }

  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            descrition={this.panel.options?.header?.tips || ''}
            draging={this.panel.draging}
            drillDownOption={this.drillDownOptions}
            inited={this.inited}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metrics}
            showAddMetric={this.showAddMetric}
            showMore={this.showHeaderMoreTool}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleAllMetricClick}
            onMenuClick={this.handleMenuToolsSelect}
            onMetricClick={this.handleMetricClick}
            onSelectChild={this.handleSelectChildMenu}
            onUpdateDragging={() => this.panel.updateDraging(false)}
          />
        )}
        {this.panel.options?.logHeader && (
          <div class='log-header'>
            <div
              class='chart-name'
              v-bk-tooltips={{ content: this.$t('跳转查看详情') }}
            >
              {this.panel.title}
              <i class='icon-monitor icon-fenxiang' />
            </div>
            <bk-checkbox>Error</bk-checkbox>
          </div>
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
              onContextmenu={this.handleChartContextmenu}
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  isContextmenuPreventDefault={true}
                  options={this.options}
                  showRestore={this.showRestore}
                  // onContextmenu={this.handleContextmenu}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                  onRestore={this.handleRestore}
                />
              )}
              <div
                id={this.contextmenuInfo.id}
                style={{
                  left: `${this.contextmenuInfo.x}px`,
                  top: `${this.contextmenuInfo.y}px`,
                  display: this.contextmenuInfo.show ? 'block' : 'none',
                  transform: `translateX(${this.contextmenuInfo.nearOutRight ? '-100%' : '0'}) translateY(${this.contextmenuInfo.nearOutBottom ? '-100%' : '0'})`,
                }}
                class='contextmenu-list'
              >
                {this.contextmenuInfo.options.map(item => (
                  <div
                    key={item.id}
                    class='contextmenu-list-item'
                    onClick={() => this.handleClickMenuItem(item.id)}
                  >
                    {item.name}
                  </div>
                ))}
              </div>
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
                  />
                ) : (
                  <ListLegend
                    alignCenter={true}
                    legendData={this.legendData}
                    onSelectLegend={this.handleSelectLegend}
                  />
                )}
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
        {(this.enableSeriesContextmenu || this.enableContextmenu) && (
          <DetailsSide
            appName={this.appName}
            dataType={this.apmMetric}
            dimensions={this.legendData?.map?.(item => item.name) || []}
            panelTitle={this.panel.title}
            pointValueUnit={this.detailsUnit}
            serviceName={this.serviceName}
            show={this.detailsSideData.show}
            timeRange={this.timeRange}
            onClose={this.handleCloseDetails}
          />
        )}
      </div>
    );
  }
}
