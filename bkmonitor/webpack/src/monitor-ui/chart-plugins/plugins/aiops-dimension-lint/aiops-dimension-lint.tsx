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
import { Component, Inject, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/index';
import { metricRecommendationFeedback } from 'monitor-api/modules/alert';
import { random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { MONITOR_BAR_OPTIONS } from '../../constants';
import { IMenuItem, PanelModel } from '../../typings';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import { LineChart } from '../time-series/time-series';

import './aiops-dimension-lint.scss';

enum EEvaluation {
  good = 'good',
  bad = 'bad'
}

interface IFeedback {
  self?: string;
  good?: number;
  bad?: number;
}
interface IRecommendInfo {
  reasons?: string[];
  anomaly_points?: number[];
  class?: string;
  src_metric_id?: string;
}
interface IPanelModel extends PanelModel {
  feedback?: IFeedback;
  recommend_info?: IRecommendInfo;
  anomaly_score?: number;
  enable_threshold?: boolean;
  src_metric_id?: string;
  class?: string;
  bk_biz_id?: string;
}

export enum ETabNames {
  dimension = 'dimension',
  index = 'index'
}

@Component
export default class AiopsDimensionLine extends LineChart {
  /** 是否关联指标 */
  @InjectReactive('isCorrelationMetrics') isCorrelationMetrics: boolean;
  @InjectReactive('layoutActive') layoutActive: number;
  @InjectReactive('selectActive') selectActive: string;
  @InjectReactive('dataZoomTimeRange') dataZoomTimeRange: any;
  @Inject('reportEventLog') reportEventLog: Function;

  @Prop({ required: true }) declare panel: IPanelModel;
  @Prop({ default: false }) declare needLegend: boolean;

  empty = true;
  height = 158;
  /** 缓存查看大图默认展示的时间，在小图使用，大图中使用无意义 */
  fullScreenCustomTimeRange = [];
  /** 缓存当前图请求的时间 */
  cacheTimeRang = [];
  emptyText = '';
  isFetchingData = false;
  /** 用来存储查看大图第一次展示的时间，在大图中使用 */
  needLegendTimeRange = [];

  get enableThreshold() {
    return 'enable_threshold' in this.panel ? this.panel?.enable_threshold : true;
  }
  /** 处理查看大图情况下的判断 */
  getShowRestore(): boolean {
    if (!this.needLegend) return true;
    const startTimeRange = JSON.stringify(this.needLegendTimeRange);
    const cacheTimeRang = JSON.stringify(this.cacheTimeRang);
    return startTimeRange !== cacheTimeRang;
  }
  /** 获取数据 */
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
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      // const series = apdexData.series || [];
      const series = [];
      // const metrics = apdexData.series || [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      let params: any = {
        // eslint-disable-next-line no-nested-ternary
        start_time: start_time ? dayjs.tz(start_time).unix() : this.needLegend ? startTime : '',
        // eslint-disable-next-line no-nested-ternary
        end_time: end_time ? dayjs.tz(end_time).unix() : this.needLegend ? endTime : ''
      };
      const [zoomStartTime, zoomEndTime] = handleTransformToTimestamp(this.dataZoomTimeRange.timeRange);
      if (!params.start_time && zoomStartTime) {
        // const { zStartTime };
        params.start_time = zoomStartTime;
        params.end_time = zoomEndTime;
      }
      if (params.start_time) {
        this.cacheTimeRang = [
          dayjs.tz(params.start_time * 1000).format('YYYY-MM-DD HH:mm'),
          dayjs.tz(params.end_time * 1000).format('YYYY-MM-DD HH:mm')
        ];
        if (this.needLegend && !this.inited) {
          this.needLegendTimeRange = [...this.cacheTimeRang];
        }
      } else {
        this.cacheTimeRang = [];
      }
      /** 查看大图第一次会传入时间所以需要通过标志位判断是否是通过datazoom事件来展示复位按钮 */
      this.showRestore = this.getShowRestore() && !!params.start_time;
      if (this.bkBizId) {
        params = Object.assign({}, params, {
          bk_biz_id: this.bkBizId
        });
      }
      const enableThreshold = 'enable_threshold' in this.panel ? this.panel?.enable_threshold : true;
      const promiseList = [];
      const timeShiftList = ['', ...this.timeOffset];
      const variablesService = new VariablesService(this.viewOptions);
      timeShiftList.forEach(time_shift => {
        const list = this.panel.targets.map(item =>
          (this as any).$api[item.apiModule]
            [item.apiFunc](
              {
                ...variablesService.transformVariables(item.data, {
                  ...this.viewOptions.filters,
                  ...(this.viewOptions.filters?.current_target || {}),
                  ...this.viewOptions,
                  ...this.viewOptions.variables,
                  time_shift
                }),
                ...(params.start_time ? params : {}),
                bk_biz_id: params.bk_biz_id
              },
              {
                cancelToken: new CancelToken((cb: Function) => this.cancelTokens.push(cb)),
                needMessage: false
              }
            )
            .then(res => {
              this.$emit('seriesData', res);
              metrics.push(...res.metrics);
              series.push(
                ...res.series.map(set => ({
                  ...set,
                  sampling: 'lttb',
                  name: `${this.timeOffset.length ? `${this.handleTransformTimeShift(time_shift || 'current')}-` : ''}${
                    this.handleSeriesName(item, set) || set.target
                  }`
                }))
              );
              this.clearErrorMsg();
              return true;
            })
            .catch(error => {
              this.handleErrorMsgChange(error.msg || error.message);
            })
        );
        promiseList.push(...list);
      });
      await Promise.all(promiseList).catch(() => false);
      if (series.length) {
        const { datapoints } = series[0];
        /** 只缓存 */
        if (datapoints.length && !params.startTime && this.fullScreenCustomTimeRange.length === 0) {
          this.fullScreenCustomTimeRange = [
            dayjs.tz(datapoints[0][1]).format('YYYY-MM-DD HH:mm'),
            dayjs.tz(datapoints[datapoints.length - 1][1]).format('YYYY-MM-DD HH:mm')
          ];
        }
        const seriesList = this.handleTransformSeries(
          series.map(item => ({
            name: item.name,
            cursor: 'auto',
            data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
            stack: item.stack || random(10),
            unit: item.unit,
            markArea: this.createMarkArea(),
            markLine: enableThreshold ? this.createdMarkLine(item.thresholds || []) : {}
          })) as any
        );
        /** 默认以这个宽度来进行刻度划分，主要为了解决 watch 未首次监听宽度自动计算splitNumber */
        // const widths = [1192, 586, 383];
        const { canScale, minThreshold, maxThreshold } = this.handleSetThreholds(enableThreshold ? series : []);
        /** 关联指标不需要展示阈值后，可以根据数据来展示最大最小值，因为阈值可能为0 */
        const yAxis = {
          scale: this.height < 120 ? false : canScale,
          max: v => Math.max(v.max, +maxThreshold),
          min: v => Math.min(v.min, +minThreshold)
        };
        const formatterFunc = this.handleSetFormatterFunc(seriesList[0].data);
        const echartOptions: any = MONITOR_BAR_OPTIONS;
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: true,
            animationThreshold: 1,
            grid: {
              top: 10,
              right: 32
            },
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
                  : (v: number) => this.handleYxisLabelFormatter(v - this.minBase)
              },
              splitNumber: this.height < 200 ? 2 : 4,
              minInterval: 1,
              scale: this.height < 120 ? false : canScale,
              max: v => Math.max(v.max, +maxThreshold),
              ...yAxis
            },
            xAxis: {
              axisLabel: {
                formatter: formatterFunc || '{value}'
              },
              splitNumber: Math.ceil((this.$el as Element).getBoundingClientRect().width / 150),
              min: 'dataMin'
            },
            series: seriesList
          })
        );

        this.metrics = metrics || [];
        this.inited = true;
        this.empty = false;
        if (!this.hasSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }
  /**
   * @description: 图表头部工具栏事件
   * @param {IMenuItem} menuItem
   * @return {*}
   */
  handleMenuToolsSelect(menuItem: IMenuItem) {
    switch (menuItem.id) {
      case 'save': // 保存到仪表盘
        this.handleCollectChart();
        break;
      case 'screenshot': // 保存到本地
        setTimeout(() => {
          this.handleStoreImage(this.panel.title || '测试');
        }, 300);
        break;
      case 'fullscreen': {
        // 大图检索
        let copyPanel: IPanelModel = JSON.parse(JSON.stringify(this.panel));
        // eslint-disable-next-line no-case-declarations
        const variablesService = new VariablesService({
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables
        });
        copyPanel = variablesService.transformVariables(copyPanel);
        copyPanel.targets.forEach((t, tIndex) => {
          const queryConfigs = this.panel.targets[tIndex].data.query_configs;
          t.data.query_configs.forEach((q, qIndex) => {
            q.functions = JSON.parse(JSON.stringify(queryConfigs[qIndex].functions));
          });
        });
        this.handleFullScreen(copyPanel as any, {
          tools: {
            timeRange: this.fullScreenCustomTimeRange
          }
        });
        break;
      }
      case 'set': // 转换Y轴大小
        (this.$refs.baseChart as any)?.handleSetYAxisSetScale(!menuItem.checked);
        break;
      case 'explore': // 跳转数据检索
        this.handleExplore(this.panel, {
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables
        });
        break;
      case 'strategy': // 新增策略
        this.handleAddStrategy(this.panel, null, this.viewOptions, true);
        break;
      default:
        break;
    }
  }
  handleSetThreholds(series = []) {
    const markLine = series?.find?.(item => item.thresholds);
    const thresholdList = markLine?.thresholds?.map?.(item => item.yAxis) || [];
    const max = Math.max(...thresholdList);
    return {
      canScale: thresholdList.length > 0 && thresholdList.every((set: number) => set > 0),
      minThreshold: Math.min(...thresholdList),
      maxThreshold: max + max * 0.1 // 防止阈值最大值过大时title显示不全
    };
  }
  createMarkArea() {
    const anomalyPoints = this.panel?.recommend_info?.anomaly_points || [];
    if (anomalyPoints.length === 0) return {};
    return {
      silent: true,
      show: true,
      data: anomalyPoints.map(item => [
        {
          xAxis: item[0],
          y: 'max',
          itemStyle: {
            color: '#f7b1b180',
            borderWidth: 1,
            borderColor: '#f7b1b180',
            shadowColor: '#f7b1b180',
            borderType: 'solid',
            shadowBlur: 0
          }
        },
        {
          xAxis: item[1] || 'max',
          y: '0%',
          itemStyle: {
            color: '#f7b1b180',
            borderWidth: 1,
            borderColor: '#f7b1b180',
            shadowColor: '#f7b1b180',
            borderType: 'solid',
            shadowBlur: 0
          }
        }
      ]),
      opacity: 0.1
    };
  }
  /** 阈值线 */
  createdMarkLine(thresholdLine: any[]) {
    const thresholdLineResult = thresholdLine.map((item: any) => ({
      ...item,
      label: {
        show: true,
        formatter() {
          return '';
        }
      }
    }));
    return {
      symbol: [],
      label: {
        show: true,
        position: 'insideStartTop'
      },
      lineStyle: {
        color: '#FD9C9C',
        type: 'dashed',
        distance: 3,
        width: 1
      },
      emphasis: {
        label: {
          show: true,
          formatter(v: any) {
            return `${v.name || ''}: ${v.value}`;
          }
        }
      },
      data: thresholdLineResult
    };
  }
  /** 踩和赞接口更新 */
  metricRecommendationFeedback(feedback: string) {
    metricRecommendationFeedback({
      bk_biz_id: this.panel.targets?.[0]?.data?.bk_biz_id || this.panel.bk_biz_id,
      alert_metric_id: this.panel.recommend_info.src_metric_id,
      feedback,
      recommendation_metric_id: this.panel.id,
      recommendation_metric_class: this.panel.recommend_info.class
    })
      .then(res => {
        this.panel.feedback = res?.feedback || {};
      })
      .catch(() => {});
  }
  /** 推荐理由 */
  get reasons() {
    return this.panel?.recommend_info?.reasons || [];
  }
  /** 指标推荐理由 */
  getCustomSlot() {
    const len = this.reasons?.length;
    if (!this.panel.id || !len) {
      return;
    }

    return (
      <span class='aiops-correlation-reason'>
        {this.reasons.map(reasons => (
          <span
            v-bk-overflow-tips
            class={[reasons.indexOf('异常') > -1 ? 'err-reason' : '']}
          >
            {reasons}
          </span>
        ))}
      </span>
    );
  }
  /** 纬度下钻分值 */
  getDimensionDrillDownRightRender() {
    if (!this.panel.id) {
      return;
    }
    return (
      <span class='aiops-dimension-drill-down-right'>
        {this.$t('异常分值')}：<font>{this.panel.anomaly_score}</font>
      </span>
    );
  }

  @Watch('selectActive')
  handleChangeSelectActive() {
    const startTimeRange = JSON.stringify(this.dataZoomTimeRange.timeRange);
    const cacheTimeRang = JSON.stringify(this.cacheTimeRang);
    if (this.inited && startTimeRange !== cacheTimeRang) {
      this.getPanelData();
    }
  }
  @Watch('dataZoomTimeRange.timeRange')
  handleChangeDataZoom(val) {
    if (
      (this.enableThreshold && this.selectActive === ETabNames.index) ||
      (!this.enableThreshold && this.selectActive === ETabNames.dimension)
    ) {
      return;
    }
    const [startTime, endTime] = val;
    this.getPanelData(startTime, endTime);
  }
  /** 缩放等 */
  dataZoom(startTime: string, endTime: string) {
    /** 查看大图不需要触发联动 */
    if (this.needLegend) {
      this.getPanelData(startTime, endTime);
      return;
    }
    if (startTime && endTime) {
      this.dataZoomTimeRange.timeRange = [startTime, endTime];
    } else {
      this.dataZoomTimeRange.timeRange = [];
    }
    this.isCustomTimeRange && this.$emit('dataZoom', startTime, endTime);
  }
  /** 赞和踩 */
  handleActiveLink(type, e) {
    e.preventDefault();
    e.stopPropagation();
    if (this.panel.feedback.self === type) {
      return;
    }
    this.panel.feedback.self = type;
    this.metricRecommendationFeedback(type);
  }
  /** 自定义subtitle */
  getSubTitle() {
    const subTitleRight = this.isCorrelationMetrics
      ? this.getCorrelationMetricsRightRender
      : this.getDimensionDrillDownRightRender;
    return (
      <div class='sub-title-custom'>
        {this.isCorrelationMetrics ? (
          this.getCustomSlot()
        ) : (
          <span class='sub-title-text'>{this.panel.subTitle || ''}</span>
        )}
        {subTitleRight()}
      </div>
    );
  }
  /** 赞和踩dom */
  getCorrelationMetricsRightRender() {
    if (!this.panel.id) {
      return;
    }
    const { self = '', good = 0, bad = 0 } = this.panel.feedback || {};
    const activeGood = self === EEvaluation.good;
    const activeBad = self === EEvaluation.bad;
    return (
      <div class='aiops-correlation-link-position'>
        <span class='aiops-correlation-link'>
          <span
            class={{ active: activeGood }}
            onClick={this.handleActiveLink.bind(this, EEvaluation.good)}
          >
            <i class={['icon-monitor', activeGood ? 'icon-mc-like-filled' : 'icon-mc-like']}></i>
            {good || 0}
          </span>
          <span
            class={{ active: activeBad }}
            onClick={this.handleActiveLink.bind(this, EEvaluation.bad)}
          >
            <i class={['icon-monitor', activeBad ? 'icon-mc-unlike-filled' : 'icon-mc-unlike']}></i>
            {bad || 0}
          </span>
        </span>
      </div>
    );
  }
  /** 阻止默认行为 */
  handleStop(event) {
    event.stopPropagation();
    event.preventDefault();
  }
  handleMouseover() {
    // 上报事件hover tips 日志
    this.reportEventLog?.('event_detail_tips');
  }
  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='aiops-dimension-lint time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            {...{
              scopedSlots: {
                subTitle: () => this.getSubTitle()
              }
            }}
            customArea={this.isCorrelationMetrics}
            title={this.panel.title}
            showTitleIcon={false}
            showMore={this.showHeaderMoreTool}
            draging={this.panel.draging}
            metrics={this.metrics}
            menuList={['screenshot', 'fullscreen', 'explore', 'strategy']}
            subtitle={this.panel.subTitle || ''}
            descrition={this.panel.descrition}
            isInstant={this.panel.instant}
            showAddMetric={false}
            showMenuAddMetric={true}
            onAlarmClick={this.handleAlarmClick}
            onMenuClick={this.handleMenuToolsSelect}
            onSelectChild={this.handleSelectChildMenu}
            onMetricClick={this.handleMetricClick}
            onAllMetricClick={this.handleAllMetricClick}
            onUpdateDragging={() => this.panel.updateDraging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`aiops-dimension-lint-content time-series-content`}>
            <div
              class='chart-instance'
              ref='chart'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  height={this.height}
                  width={this.width}
                  showRestore={this.showRestore}
                  options={this.options}
                  groupId={this.panel.dashboardId}
                  onMouseover={this.handleMouseover}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                />
              )}
            </div>
            {this.needLegend && legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    onSelectLegend={this.handleSelectLegend}
                    legendData={this.legendData}
                  />
                ) : (
                  <ListLegend
                    onSelectLegend={this.handleSelectLegend}
                    legendData={this.legendData}
                  />
                )}
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
