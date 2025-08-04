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
// import { Component as tsc } from 'vue-tsx-support';
import { Component, Ref, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/cancel';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { type ILogUrlParams, findRight, transformLogUrlQuery } from 'monitor-pc/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { COLOR_LIST, COLOR_LIST_BAR, MONITOR_LINE_OPTIONS } from '../../constants';
import { queryConfigTransform } from '../../utils';
import { VariablesService } from '../../utils/variable';
import BaseEchart from '../monitor-base-echart';
import { LineChart } from '../time-series/time-series';

import type { ICurPoint, IViewOptions, PanelModel } from '../../typings';

import '../time-series/time-series.scss';
import './time-series-forecast.scss';

@Component
export default class TimeSeriesForecast extends LineChart {
  @Ref() baseChart: InstanceType<typeof BaseEchart>;

  minBase = 0;

  curPoint: ICurPoint = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 };

  /** Y轴最小值 */
  yAxisMin = 0;

  /** 绘制中间分割线 */
  createPredictLineFn: () => void = null;

  /** 预测时长 返回小时数 */
  get duration(): number {
    const oneDay = 24 * 60 * 60;
    const oneHour = 60 * 60;
    return (this.panel.options?.time_series_forecast?.duration || oneDay) / oneHour;
  }
  get localLegendData() {
    const includesList = ['_result_', 'predict'];
    return this.legendData.reduce((total, item) => {
      const need = includesList.includes(item.metricField);
      if (need) {
        item.alias = `${item.name === 'predict' ? '' : item.name}${this.$tc(
          item.metricField === '_result_' ? '当前值' : '预测值'
        )}`;
        total.push(item);
      }
      return total;
    }, []);
  }

  @Debounce(100)
  @Watch('width')
  handleWidthChange() {
    this.createPredictLineFn();
  }

  /** 阈值线 */
  createMarkLine(item) {
    if (item.metric_field !== '_result_') return {};
    return this.panel.options?.time_series_forecast?.markLine || {};
  }
  /** 区域标记 */
  createMarkArea(item) {
    if (item.metric_field !== '_result_') return {};
    /** 阈值区域 */
    const thresholdsMarkArea = this.panel.options?.time_series_forecast?.markArea || {};
    let alertMarkArea = {};
    /** 告警区域 */
    if (false && item.markTimeRange?.length) {
      const [{ from, to }] = item.markTimeRange;
      alertMarkArea = this.handleSetThresholdBand([{ from, to }]);
    }
    const result = deepmerge(alertMarkArea, thresholdsMarkArea);
    return { ...result, z: 10 };
  }
  handleSetThresholds() {
    const { markLine } = this.panel?.options?.time_series_forecast || {};
    const thresholdList = markLine?.data?.map?.(item => item.yAxis) || [];
    const max = Math.max(...thresholdList);
    return {
      canScale: thresholdList.length > 0 && thresholdList.every((set: number) => set > 0),
      minThreshold: Math.min(...thresholdList),
      maxThreshold: max + max * 0.1, // 防止阈值最大值过大时title显示不全
    };
  }
  /**
   * @description: 获取图表数据
   * @param {*}
   * @return {*}
   */
  @Debounce(200)
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
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.t('加载中...');
    try {
      this.unregisterObserver();
      const series = [];
      const metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const promiseList = [];
      const timeShiftList = ['', ...this.timeOffset];
      const variablesService = new VariablesService(this.viewOptions);
      timeShiftList.forEach(time_shift => {
        const list = this.panel.targets.map(item => {
          const timeRange = item.options?.time_series_forecast?.forecast_time_range;
          const noResult = item.options?.time_series_forecast?.no_result;
          return (this as any).$api[item.apiModule]
            [item.apiFunc](
              {
                ...variablesService.transformVariables(item.data, {
                  ...this.viewOptions.filters,
                  ...(this.viewOptions.filters?.current_target || {}),
                  ...this.viewOptions,
                  ...this.viewOptions.variables,
                  time_shift,
                }),
                ...params,
                ...(timeRange
                  ? {
                      start_time: timeRange[0],
                      end_time: timeRange[1],
                    }
                  : {}),
              },
              {
                cancelToken: new CancelToken((cb: () => void) => this.cancelTokens.push(cb)),
                needMessage: false,
              }
            )
            .then(res => {
              metrics.push(...res.metrics);
              let itemSeries = res.series;
              if (noResult) {
                itemSeries = itemSeries.filter(ser => ser.metric_field !== '_result_');
              }
              series.push(
                ...itemSeries.map(set => ({
                  ...set,
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
      });
      const completed = await Promise.all(promiseList)
        .then(() => true)
        .catch(err => {
          console.error(err);
          this.emptyText = window.i18n.t('出错了');
          return false;
        });
      if (series.length) {
        const resultPoints = series.find(item => item.metric_field === '_result_')?.datapoints || [];
        if (resultPoints.length > 1) {
          if (resultPoints[0][0] === null) {
            resultPoints.splice(0, 1);
          }
        }
        const formatterFunc = this.handleSetFormatterFunc(resultPoints);
        const seriesResult = (this.handleGetOrecastSeriesData(series) || []).reduce((total, item) => {
          /** 数据去重 */
          const isExist = total.some(set => set.metric_field === item.metric_field);
          if (!isExist) total.push(item);
          return total;
        }, []);
        const predictSeries = seriesResult.find(item => item.metric_field === 'predict');

        const formatterFuncPredict = this.handleSetFormatterFunc(
          predictSeries?.datapoints?.filter?.(item => item[0] ?? false) || []
        );
        let seriesList = this.handleTransformSeries(
          seriesResult.map(item => {
            /** 绘制预测区域的过度效果 */
            if (item.metric_field === 'predict') {
              this.createPredictLineFn = this.createPredictLine.bind(this, deepClone(item));
              this.createPredictLineFn();
            }
            return {
              id: item.metric_field,
              name: item.name,
              cursor: 'auto',
              color: this.handleColor(item),
              xAxisIndex: item.metric_field === '_result_' ? 0 : 1,
              data: item.datapoints.reduce((pre: any, cur: any) => (pre.push(cur.reverse()), pre), []),
              stack: item.stack || random(10),
              unit: item.unit,
              metricField: item.metric_field,
              markLine: item.metric_field !== 'predict' ? this.createMarkLine(item) : {},
              markArea: this.createMarkArea(item),
              markPoint:
                item.metric_field !== 'predict'
                  ? this.createMarkPointData(item, series)
                  : this.createMarkOptionPredict(item),
              z: 1,
            } as any;
          })
        );
        /** 处理上下边界 */
        const boundarySeries = this.handleBoundaryList(seriesResult[0], seriesResult).flat(Number.POSITIVE_INFINITY);
        if (boundarySeries) {
          const lineSeriesList = seriesList
            .map((item: any) => ({ ...item, z: 6 }))
            .filter(item => ['_result_', 'predict'].includes(item.metricField));
          seriesList = [...lineSeriesList, ...boundarySeries];
        }
        seriesList = seriesList.map((item: any) => ({
          ...item,
          minBase: this.minBase,
          emphasis: {
            focus: 'none',
          },
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
        // 1、echarts animation 配置会影响数量大时的图表性能 掉帧
        // 2、echarts animation配置为false时 对于有孤立点不连续的图表无法放大 并且 hover的点放大效果会潇洒 (貌似echarts bug)
        // 所以此处折中设置 在有孤立点情况下进行开启animation 连续的情况不开启
        const hasShowSymbol = seriesList.some(item => item.showSymbol);
        if (hasShowSymbol) {
          seriesList.forEach(item => {
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
          });
        }
        const predictStartFirstPoint = seriesList
          .find(item => item.metricField === 'predict')
          ?.data?.find(item => {
            const value = Array.isArray(item) ? item : item.value;
            return value[1] ?? false;
          });

        const predictStartTime = Array.isArray(predictStartFirstPoint)
          ? predictStartFirstPoint[0]
          : predictStartFirstPoint?.value[0];
        const resultEndTimePoint = findRight(
          seriesList.find(item => item.metricField === '_result_')?.data || [],
          item => {
            const value = Array.isArray(item) ? item : item.value;
            return !!value[1];
          }
        );
        const resultEndTime = resultEndTimePoint?.value?.[0];
        // const { canScale, minThreshold } = this.handleSetThresholds();
        const { canScale, minThreshold, maxThreshold } = this.handleSetThresholds();

        const chartBaseOptions = MONITOR_LINE_OPTIONS;

        const echartOptions = deepmerge(
          deepClone(chartBaseOptions),
          this.panel.options?.time_series?.echart_option || {},
          { arrayMerge: (_, newArr) => newArr }
        );
        this.options = Object.freeze(
          deepmerge(echartOptions, {
            animation: hasShowSymbol,
            color: this.panel.options?.time_series?.type === 'bar' ? COLOR_LIST_BAR : COLOR_LIST,
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
                  : (v: number) => this.handleYAxisLabelFormatter(v - this.minBase),
              },
              splitNumber: this.height < 120 ? 2 : 4,
              minInterval: 1,
              scale: this.height < 120 ? false : canScale,
              // max: v => v.max * 1.1
              max: v => Math.max(v.max, +maxThreshold),
              min: v => {
                this.yAxisMin = Math.min(v.min, +minThreshold);
                return this.yAxisMin;
              },
            },
            xAxis: [
              {
                type: 'time',
                boundaryGap: false,
                axisTick: {
                  show: false,
                },
                axisLine: {
                  show: false,
                  lineStyle: {
                    color: '#ccd6eb',
                    width: 1,
                    type: 'solid',
                  },
                },
                axisLabel: {
                  fontSize: 12,
                  color: '#979BA5',
                  showMinLabel: false,
                  showMaxLabel: false,
                  align: 'left',
                  formatter: (v: number) => {
                    if (v > (resultEndTime || endTime * 1000)) return '';
                    return formatterFunc(v);
                  },
                },
                splitLine: {
                  show: false,
                },
                minInterval: 5 * 60 * 1000,
                splitNumber: Math.ceil(this.width / 2 / 80),
                scale: true,
              },
              {
                show: true,
                type: 'time',
                boundaryGap: false,
                axisTick: {
                  show: false,
                },
                axisLine: {
                  show: false,
                  lineStyle: {
                    color: '#ccd6eb',
                    width: 1,
                    type: 'solid',
                  },
                },
                axisLabel: {
                  fontSize: 12,
                  color: '#979BA5',
                  showMinLabel: false,
                  showMaxLabel: false,
                  align: 'left',
                  formatter: (v: number) => {
                    if (v < predictStartTime) return '';
                    return formatterFuncPredict?.(v);
                  },
                },
                splitLine: {
                  show: false,
                },
                minInterval: 5 * 60 * 1000,
                splitNumber: Math.ceil(this.width / 2 / 80),
                scale: true,
                position: 'bottom',
              },
            ],
            markArea: {
              z: 100,
            },
            markLine: {
              z: 100,
            },
            markPoint: {
              z: 100,
            },
            tooltip: {
              formatter: this.handleSetTooltip,
            },
            series: seriesList,
          })
        );
        this.metrics = metrics || [];
        this.initialized = true;
        this.empty = false;
        if (!this.hasSetEvent) {
          setTimeout(this.handleSetLegendEvent, 300);
          this.hasSetEvent = true;
        }
      } else if (completed) {
        this.emptyText = window.i18n.t('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.t('出错了');
      console.error(e);
    }
    this.cancelTokens = [];
    this.handleLoadingChange(false);
  }

  // 设置tooltip
  handleSetTooltip(params) {
    if (!this.showChartHeader) return undefined;
    if (!params || params.length < 1 || params.every(item => item.value[1] === null)) {
      this.curPoint = {
        color: '',
        name: '',
        seriesIndex: -1,
        dataIndex: -1,
        xAxis: '',
        yAxis: '',
      };
      return;
    }
    const curAxis = params.find(item => item.value?.[1] !== null);
    const pointTime = dayjs.tz(curAxis.axisValue).format('YYYY-MM-DD HH:mm:ss');
    const data = params
      .map(item => ({ color: item.color, seriesName: item.seriesName, value: item.value[1] }))
      .sort((a, b) => Math.abs(a.value - +this.curPoint.yAxis) - Math.abs(b.value - +this.curPoint.yAxis));
    const list = params.filter(item => !item.seriesName.match(/-no-tips$/));
    const liHtmlList = list
      .sort((a, b) => b.value[1] - a.value[1])
      .map(item => {
        let markColor = 'color: #fafbfd;';
        if (data[0].value === item.value[1]) {
          markColor = 'color: #fff;font-weight: bold;';
          this.curPoint = {
            color: item.color,
            name: item.seriesName,
            seriesIndex: item.seriesIndex,
            dataIndex: item.dataIndex,
            xAxis: item.value[0],
            yAxis: item.value[1],
          };
        }
        if (item.value[1] === null) return '';
        const curSeries: any = this.options.series[item.seriesIndex];
        const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
        const minBase = curSeries.minBase || 0;
        const precision = curSeries.unit !== 'none' && +curSeries.precision < 1 ? 2 : +curSeries.precision;
        const valueObj = unitFormatter(item.value[1] - minBase, precision);
        return `<li class="tooltips-content-item">
                <span class="item-series"
                 style="background-color:${item.color};">
                </span>
                <span class="item-name" style="${markColor}">${
                  curSeries.name === 'predict' ? '' : curSeries.name
                }${this.$tc(curSeries.metricField === '_result_' ? '当前值' : '预测值')}:</span>
                <span class="item-value" style="${markColor}">
                ${valueObj.text} ${valueObj.suffix || ''}</span>
                </li>`;
      });
    if (liHtmlList?.length < 1) return '';
    return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
            <ul class="tooltips-content">
                ${liHtmlList?.join('')}
            </ul>
            </div>`;
  }

  /** 处理图表上下边界的数据 */
  handleBoundaryList(item, series) {
    const currentDimensions = item.dimensions;
    const getDimStr = dim => `${dim.bk_target_ip}-${dim.bk_target_cloud_id}`;
    const currentDimStr = getDimStr(currentDimensions);
    const lowerBound = series.find(ser => ser.alias === 'lower_bound' && getDimStr(ser.dimensions) === currentDimStr);
    const upperBound = series.find(ser => ser.alias === 'upper_bound' && getDimStr(ser.dimensions) === currentDimStr);
    if (!lowerBound || !upperBound) return [];
    const boundaryList = [];
    const level = 1;
    const algorithm2Level = {
      1: 5,
      2: 4,
      3: 3,
    };
    boundaryList.push({
      upBoundary: upperBound.datapoints,
      lowBoundary: lowerBound.datapoints,
      color: '#e6e6e6',
      type: 'line',
      stack: `boundary-${level}`,
      z: algorithm2Level[level],
    });
    // 上下边界处理
    if (boundaryList?.length) {
      boundaryList.forEach((item: any) => {
        const base = -item.lowBoundary.reduce(
          (min: number, val: any) => (val[1] !== null ? Math.floor(Math.min(min, val[1])) : min),
          Number.POSITIVE_INFINITY
        );
        this.minBase = Math.max(base, this.minBase);
      });
      const boundarySeries = boundaryList.map((item: any) => this.createBoundarySeries(item, this.minBase));
      return boundarySeries;
    }
  }

  /**
   * 生成预测区域数据
   * @param item 线数据
   * @param base 基数
   * @returns
   */
  createBoundarySeries(item: any, base: number) {
    const result = [
      {
        name: `lower-${item.stack}-no-tips`,
        type: 'line',
        data: item.lowBoundary.map((item: any) => [item[0], item[1] === null ? null : item[1] + base]),
        lineStyle: {
          opacity: 0,
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4,
        xAxisIndex: 1,
      },
      {
        name: `upper-${item.stack}-no-tips`,
        type: 'line',
        data: item.upBoundary.map((set: any, index: number) => [
          set[0],
          set[1] === null ? null : set[1] - item.lowBoundary[index][1],
        ]),
        lineStyle: {
          opacity: 0,
        },
        areaStyle: {
          color: 'blue',
          opacity: 0.1,
        },
        stack: item.stack,
        symbol: 'none',
        z: item.z || 4,
        xAxisIndex: 1,
      },
    ];
    return result;
  }

  /**
   * 处理得到预测图表的所需数据
   * @param series 图表接口响应的数据
   */
  handleGetOrecastSeriesData(series: any[]) {
    let name = '';
    /** 预测线、上下界限线 */
    const needTransform = ['predict', 'upper_bound', 'lower_bound'];
    const result = series.reduce((total, item, index) => {
      /** 没有维度时候只有一个目标的数据 */
      const isNoDimensions = JSON.stringify(item.dimensions) === '{}';
      if (!index) name = item.name;
      if (isNoDimensions || item.name === name) {
        if (needTransform.includes(item.metric_field)) {
          const targetPoint = findRight(item.datapoints, point => !!point[0]);
          if (targetPoint) {
            const pointsObj = JSON.parse(targetPoint[0].replace(/NaN/g, 'null'));
            item.datapoints = targetPoint ? Object.entries(pointsObj).map(set => [+set[1], +set[0]]) : [];
          } else {
            item.datapoints = [];
          }
          if (item.datapoints.length > this.duration) {
            item.datapoints.length = this.duration;
          }
          item.datapoints = this.handleCreateNullPoint(item.datapoints);
        } else {
          item.datapoints = this.handleCreateNullPoint(item.datapoints, 'append');
        }
        total.push(item);
      }
      return total;
    }, []);
    return result;
  }

  /**
   * 根据现有数据往前或者往后补充空的数据 [time, null]
   * @param points 图表数据点
   * @param type 'preend': 往前加， 'append': 往后加
   * @returns points
   */
  handleCreateNullPoint(points, type: 'append' | 'preend' = 'preend') {
    const leng = points.length;
    const isPre = type === 'preend';
    if (leng >= 2) {
      const interval = points[1][1] - points[0][1];
      const nullPoints = [];
      let i = leng;
      const startPoint = isPre ? points[0] : points[leng - 1];
      const startTime = startPoint[1];
      let curTime = startTime;
      while (i) {
        const point = [null, isPre ? curTime - interval : curTime + interval];
        curTime = point[1];
        isPre ? nullPoints.unshift(point) : nullPoints.push(point);
        i -= 1;
      }
      return isPre ? [...nullPoints, ...points] : [...points, ...nullPoints];
    }
    return points;
  }
  /**
   * 绘制时序预测开始的渐变过度效果
   * @param item 预测线的线数据
   * @returns
   */
  createPredictLine(item) {
    const point = item.datapoints.find(point => !!point[0]);
    const lineX = point?.[1];
    const lineY = point?.[0];
    setTimeout(() => {
      try {
        const instance = this.baseChart?.instance;
        /** 预测线第一个点的坐标 单位: px */
        const [x] = instance.convertToPixel({ seriesId: item.metric_field }, [lineX, lineY]);
        /** 底部坐标 */
        const [, y2] = instance.convertToPixel({ seriesId: item.metric_field }, [lineX, this.yAxisMin || 0]);
        /** 渐变区域宽度 */
        const rectWidth = 4;
        /** 生成渐变图片 */
        const canvas = document.createElement('canvas');
        canvas.width = rectWidth;
        canvas.height = y2;
        const ctx = canvas.getContext('2d');
        /** 设置渐变色 */
        const gradient = ctx.createLinearGradient(0, 0, rectWidth, 0);
        gradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
        gradient.addColorStop(0.8, 'rgba(0, 0, 0, 0.1)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0.2)');
        // 填充色为渐变色
        ctx.fillStyle = gradient;
        // 绘制实心矩形
        ctx.fillRect(0, 0, rectWidth, y2);
        const png = canvas.toDataURL('image/png');

        instance.setOption({
          graphic: [
            {
              type: 'image',
              z: 5,
              left: x - rectWidth,
              top: 0,
              style: {
                image: png,
              },
            },
          ],
        });
      } catch (error) {
        console.error(error);
      }
    }, 200);
  }

  /**
   * 生成预测线的告警点
   * @param item 预测series
   * @returns markPoint数据
   */
  createMarkOptionPredict(item) {
    const data = [];
    !!item.markPoints?.length &&
      data.push(
        ...item.markPoints.map(item => ({
          xAxis: item[1],
          yAxis: item[0],
          symbolSize: 12,
        }))
      );
    /** 事件中心告警开始点 */
    const markPoint = {
      data,
      zlevel: 0,
      symbol: 'circle',
      symbolSize: 6,
      z: 10,
      label: {
        show: false,
      },
      itemStyle: {
        color: '#ea3636',
      },
    };
    return markPoint;
  }
  /**
   * 获取时序预测对应线条的颜色
   * @param item 线数据
   * @returns
   */
  handleColor(item) {
    const key = item.metric_field;
    const colorMap = {
      _result_: '#74C9A6',
      predict: '#3A84FF',
      upper_bound: '#A3C5FD',
      lower_bound: '#A3C5FD',
    };
    return colorMap[key];
  }

  /**
   * @description: 跳转到检索
   * @param {PanelModel} panel
   * @return {*}
   */
  handleExplore(panel: PanelModel, scopedVars: IViewOptions & Record<string, any>) {
    const targets: PanelModel['targets'] = JSON.parse(JSON.stringify(panel.targets)).slice(0, 1);
    const variablesService = new VariablesService(scopedVars);
    targets.forEach(target => {
      target.data.query_configs =
        target?.data?.query_configs.map(queryConfig =>
          queryConfigTransform(variablesService.transformVariables(queryConfig), scopedVars)
        ) || [];
    });
    /** 判断跳转日志检索 */
    const isLog = targets.some(item =>
      item.data.query_configs.some(set => set.data_source_label === 'bk_log_search' && set.data_type_label === 'log')
    );
    if (isLog) {
      const [startTime, endTime] = this.timeRange;
      const queryConfig = targets[0].data.query_configs[0];
      const retrieveParams: ILogUrlParams = {
        // 检索参数
        bizId: `${this.$store.getters.bizId}`,
        keyword: queryConfig.query_string, // 搜索关键字
        addition: queryConfig.where || [],
        start_time: startTime,
        end_time: endTime,
        time_range: 'customized',
      };
      const indexSetId = queryConfig.index_set_id;

      const queryStr = transformLogUrlQuery(retrieveParams);
      const url = `${this.$store.getters.bkLogSearchUrl}#/retrieve/${indexSetId}${queryStr}`;
      window.open(url);
    } else {
      window.open(
        `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(
          JSON.stringify(targets)
        )}&from=${this.timeRange[0]}&to=${this.timeRange[1]}`
      );
    }
  }

  render() {
    const { legend } = this.panel?.options || {};
    return (
      <div class='time-series-forecast time-series'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            dragging={this.panel.dragging}
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
            onUpdateDragging={() => this.panel.updateDragging(false)}
          />
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.initialized && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  options={this.options}
                  onDataZoom={this.dataZoom}
                  onDblClick={this.handleDblClick}
                />
              )}
            </div>
            {legend?.displayMode !== 'hidden' && (
              <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
                {legend?.displayMode === 'table' ? (
                  <TableLegend
                    // onSelectLegend={this.handleSelectLegend}
                    legendData={this.localLegendData}
                  />
                ) : (
                  <ListLegend
                    // onSelectLegend={this.handleSelectLegend}
                    legendData={this.localLegendData}
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
