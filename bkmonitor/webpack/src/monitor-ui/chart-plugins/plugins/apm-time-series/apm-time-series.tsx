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
import { Component, Inject, InjectReactive } from 'vue-property-decorator';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/cancel';
import { deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, MONITOR_LINE_OPTIONS } from '../../constants';
import { createMenuList, type CustomChartConnector, reviewInterval } from '../../utils';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from '../../utils/axis';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';
import DetailsSide, { EDataType } from './components/details-side';

import './apm-time-series.scss';

export const COLOR_LIST_BAR = ['#4051A3', ...COLOR_LIST];

@Component
export default class ApmTimeSeries extends TimeSeries {
  @Inject('handlePageTabChange') handlePageTabChange: (
    id: string,
    customRouterQuery: Record<string, number | string>
  ) => void;
  @InjectReactive('customChartConnector') customChartConnector: CustomChartConnector;

  contextmenuInfo = {
    options: [
      // { id: 'details', name: window.i18n.t('查看详情') },
      { id: 'topo', name: window.i18n.t('查看拓扑') },
    ],
    sliceStartTime: 0, // 当前切片起始时间
    sliceEndTime: 0,
  };

  detailsSideData = {
    show: false,
  };

  needTips = true;

  /* 错误数图表维度分类 */
  errorCountCategory: Record<string, string> = {};

  /* 用于customChartConnector */
  chartId = random(8);
  /* 是否显示鼠标提示 */
  showMouseTips = false;

  get apmMetric(): EDataType {
    return (this.panel.options?.apm_time_series?.metric || '') as EDataType;
  }

  get appName() {
    return this.viewOptions?.app_name || '';
  }

  get serviceName() {
    return this.viewOptions?.service_name || '';
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

  get xAxisSplitNumber() {
    return this.panel.options?.apm_time_series?.xAxisSplitNumber;
  }

  /* 禁用框选 */
  get disableZoom() {
    return !!this.panel.options?.apm_time_series?.disableZoom;
  }

  tooltipsContentLastItem(params) {
    if (this.apmMetric === EDataType.requestCount) {
      try {
        let count = 0;
        for (const p of params) {
          count += p.value[1];
        }
        return `<li class="tooltips-content-item">
                    <span class="item-series"
                    style="background-color:transparent;">
                    </span>
                    <span class="item-name" style="color: #fafbfd;">${this.$t('总数量')}:</span>
                    <span class="item-value" style="color: #fafbfd;">
                    ${count}</span>
                    </li>`;
      } catch (e) {
        console.error(e);
        return '';
      }
    }
    return '';
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
        this.unregisterObserver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    if (this.initialized) this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    if (!this.enableSelectionRestoreAll) {
      this.showRestore = !!start_time;
    }
    try {
      this.unregisterObserver();
      const series = [];
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
          const newParams = {
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
          return (this as any).$api[item.apiModule]
            [item.apiFunc](newParams, {
              cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
              needMessage: false,
            })
            .then(res => {
              this.$emit('seriesData', res);
              res.metrics && metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => {
                  const name = `${this.handleSeriesName(item, set) || set.target}`;
                  if (this.apmMetric === EDataType.errorCount) {
                    this.errorCountCategory[name] = (item as any)?.apm_time_series_category || '';
                  }
                  return {
                    ...set,
                    stack,
                    name: name,
                    yAxisIndex: item.yAxisIndex || 0,
                    chart_type: item.chart_type,
                  };
                })
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
      if (series.length && series?.some(s => !!s?.datapoints?.length)) {
        const { maxSeriesCount, maxXInterval } = getSeriesMaxInterval(series);
        /* 派出图表数据包含的维度*/
        this.emitDimensions(series);
        this.series = Object.freeze(series) as any;
        const xAxisSet = new Set<number>();
        const seriesResult = series.map(item => ({
          ...item,
          datapoints: item.datapoints.map(point => {
            xAxisSet.add(point[1]);
            return [JSON.parse(point[0])?.anomaly_score ?? point[0], point[1]];
          }),
        }));
        const isBar = this.panel.options?.time_series?.type === 'bar';
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
            yAxisIndex: item.yAxisIndex || 0,
            chart_type: item.chart_type || undefined,
          })) as any,
          isBar ? COLOR_LIST_BAR : COLOR_LIST
        );
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
          type: item.chart_type || item.type,
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
        const { canScale, maxThreshold } = this.handleSetThresholds();

        let chartBaseOptions = MONITOR_LINE_OPTIONS;
        if (this.disableZoom) {
          chartBaseOptions = deepmerge(MONITOR_LINE_OPTIONS, {
            toolbox: {
              feature: {
                dataZoom: {
                  show: false,
                },
              },
            },
          });
        }
        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        const xInterval = getTimeSeriesXInterval(maxXInterval, this.width, maxSeriesCount);
        const width = (this.$refs?.baseChart as any)?.clientWidth;
        const splitNumber = Math.ceil(width / 100);
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: hasShowSymbol,
            color: isBar ? COLOR_LIST_BAR : COLOR_LIST,
            animationThreshold: 1,
            yAxis: [
              {
                axisLabel: {
                  formatter: (v: any) => {
                    const item = seriesList.find(item => item.yAxisIndex === 0);
                    if (item.unit !== 'none') {
                      const obj = getValueFormat(item.unit)(v, item.precision);
                      return obj.text + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                    }
                    return v;
                  },
                },
                splitNumber: this.height < 120 ? 2 : 4,
                minInterval: 1,
                scale: this.height < 120 ? false : canScale,
                max: v => Math.max(v.max, +maxThreshold),
                min: 0,
                position: 'left',
              },
              {
                axisLabel: {
                  formatter: (v: any) => {
                    const item = seriesList.find(item => item.yAxisIndex === 1);
                    if (item.unit !== 'none') {
                      const obj = getValueFormat(item.unit)(v, item.precision);
                      return obj.text + (this.yAxisNeedUnitGetter ? obj.suffix : '');
                    }
                    return v;
                  },
                },
                position: 'right',
                splitNumber: this.height < 120 ? 2 : 4,
                minInterval: 1,
                scale: this.height < 120 ? false : canScale,
                max: v => Math.max(v.max, +maxThreshold),
                min: 0,
              },
            ],
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}',
              },
              splitNumber,
              ...xInterval,
              ...(this.xAxisSplitNumber ? { splitNumber: this.xAxisSplitNumber } : {}),
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
        this.initialized = true;
        this.empty = false;
        if (!this.hasSetEvent && this.needSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
        setTimeout(() => {
          this.handleResize();
          this.setChartInstance();
        }, 100);
      } else {
        this.initialized = this.metrics.length > 0;
        this.emptyText = window.i18n.t('暂无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了');
      console.error(e);
    }
    // 初始化刷新定时器
    if (!this.refreshIntervalInstance && this.refreshInterval) {
      this.handleRefreshIntervalChange(this.refreshInterval);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }

  /* 整个图的右键菜单 */
  handleChartContextmenu(event: MouseEvent) {
    event.preventDefault();
    if (this.enableContextmenu) {
      const { pageX, pageY } = event;
      const instance = (this.$refs.baseChart as any).instance;
      createMenuList(
        this.contextmenuInfo.options,
        { x: pageX, y: pageY },
        (id: string) => {
          const startTime = (this.$refs.baseChart as any)?.curPoint?.xAxis || 0;
          let endTime = 0;
          let i = 0;
          const datas = this.seriesList[0].data || [];
          for (const item of datas) {
            i += 1;
            if (item?.value?.[0] === startTime || item?.[0] === startTime) {
              const nextItem = datas[i];
              endTime = nextItem?.value?.[0] || nextItem?.[0] || 0;
              break;
            }
          }
          this.contextmenuInfo = {
            ...this.contextmenuInfo,
            sliceStartTime: startTime,
            sliceEndTime: endTime || startTime + 1000 * 60,
          };
          this.handleClickMenuItem(id);
        },
        instance
      );
    }
  }

  /**
   * @description: 处理右键菜单点击事件
   * @param id
   */
  handleClickMenuItem(id: string) {
    if (id === 'details') {
      this.detailsSideData.show = true;
    } else if (id === 'topo') {
      const { sliceStartTime, sliceEndTime } = this.contextmenuInfo;
      this.handlePageTabChange(this.serviceName ? 'service-default-topo' : 'topo', {
        sliceStartTime,
        sliceEndTime,
      });
    }
  }

  handleCloseDetails() {
    this.detailsSideData.show = false;
  }

  /* 与非echarts图联动时需要调用此函数（存储实例） */
  setChartInstance() {
    if (this.panel.dashboardId === this.customChartConnector?.groupId) {
      this.customChartConnector.setChartInstance(this.chartId, this.$refs?.baseChart);
    }
  }
  /* 与非echarts图联动时需要调用此函数 (联动动作) */
  handleUpdateAxisPointer(event) {
    if (this.panel.dashboardId === this.customChartConnector?.groupId) {
      this.customChartConnector.updateAxisPointer(this.chartId, event?.axesInfo?.[0]?.value || 0);
    }
  }
  handleBaseChartMouseover(v: boolean) {
    this.showMouseTips = v;
  }
  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='time-series apm-time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            customArea={this.detailsSideData.show}
            description={this.panel.options?.header?.tips || ''}
            dragging={this.panel.dragging}
            drillDownOption={this.drillDownOptions}
            initialized={this.initialized}
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
            onUpdateDragging={() => this.panel.updateDragging(false)}
          >
            {this.enableContextmenu && (
              <div class='context-menu-info'>
                {this.showMouseTips && [
                  <i
                    key='1'
                    class='icon-monitor icon-mc-mouse mouse-icon'
                  />,
                  this.$t('右键更多操作'),
                ]}

                <bk-button
                  size='small'
                  text
                  onClick={() => this.handleClickMenuItem('details')}
                >
                  {this.$t('查看详情')}
                </bk-button>
              </div>
            )}
          </ChartHeader>
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
              onMouseenter={() => this.handleBaseChartMouseover(true)}
              onMouseleave={() => this.handleBaseChartMouseover(false)}
            >
              {this.initialized && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  hoverAllTooltips={this.hoverAllTooltips}
                  isContextmenuPreventDefault={true}
                  needTooltips={this.needTips}
                  options={this.options}
                  showRestore={this.showRestore}
                  sortTooltipsValue={false}
                  tooltipsContentLastItemFn={this.tooltipsContentLastItem}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                  onRestore={this.handleRestore}
                  onUpdateAxisPointer={this.handleUpdateAxisPointer}
                />
              )}
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
            errorCountCategory={this.errorCountCategory}
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
