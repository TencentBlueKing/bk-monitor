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
import {
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Loading, Message } from 'bkui-vue';
import dayjs from 'dayjs';
import deepMerge from 'deepmerge';
import { toBlob, toPng } from 'html-to-image';
import { traceListById } from 'monitor-api/modules/apm_trace';
import { copyText, hexToRgbA } from 'monitor-common/utils/utils';
import EchartOptions from 'monitor-ui/monitor-echarts/options/echart-options';
import { type MonitorEchartOptions, echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { debounce } from 'throttle-debounce';

import ChartTitle from '../../components/chart-title';
import CommonLegend from '../../components/common-legend';
import { useChartInfoInject } from '../../hooks/chart';
import { colorList } from './constant';
import TagDisplay from './TagDisplay';

import './failure-chart.scss';

export default defineComponent({
  name: 'FailureChart',
  props: {
    options: Object,
    autoresize: {
      type: Boolean,
      default: true,
    },
    needFullScreen: {
      type: Boolean,
      default: true,
    },
    curBizId: {
      type: String,
      default: '',
    },
    needChild: {
      type: Boolean,
      default: true,
    },
    watchOptionsDeep: {
      type: Boolean,
      default: true,
    },
    setNoData: {
      type: Boolean,
      default: true,
    },
    refreshInterval: {
      type: Number,
      default: 0,
    },
    subtitle: String,
    chartType: {
      type: String,
      default: 'line',
    },
    title: String,
    errorMsg: String,
    series: Object,
    backgroundUrl: String,
    getSeriesData: {
      type: Function,
    },
    getAlarmStatus: Function,
    colors: {
      type: Array,
      default: () => colorList,
    },
    emptyText: String,
    hasTraceInfo: {
      type: Boolean,
      default: false,
    },
    height: {
      type: Number,
      default: 310,
    },
    lineWidth: {
      type: [Number, String],
      default: 1,
    },
    needTools: {
      type: Boolean,
      default: false,
    },
    groupId: String,
    traceInfoTimeRange: {
      type: Object,
      default: () => ({}),
    },
    hasResize: {
      type: Boolean,
      default: false,
    },
    detail: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: [
    'data-zoom',
    'dblclick',
    'click',
    'chart-click',
    'full-screen',
    'export-data-retrieval',
    'add-strategy',
    'collect-chart',
    'on-transform-area',
    'on-yaxis-set-scale',
    'relate-alert',
    'successLoad',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const failureChartWrapRef = ref(null);
    const scatterTipsRef = ref(null);
    const chartRef = ref(null);
    const charWrapRef = ref(null);
    const readonly = inject<Ref>('readonly', null);
    const showRestoreInject = inject<Ref>('showRestore') || ref(false);
    const enableSelectionRestoreAll = inject<Ref>('enableSelectionRestoreAll') || ref(false);
    const handleChartDataZoom = inject<Ref>('handleChartDataZoom') || ref(null);
    const handleRestoreEvent = inject<Ref>('handleRestoreEvent') || ref(null);
    // 定义响应式数据
    const intersectionObserver = ref(null);
    const loading = ref(false);
    const noData = ref(false);
    const timeRange = ref([]);
    const chartTitle = ref('');
    const annotation = ref({ x: 0, y: 0, show: false, title: '', name: '', color: '', list: [] });
    const curValue = ref({ xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1, seriesType: '' });
    const chartSubTitle = ref('');
    const chartOptionInstance = ref(null);
    const hasInitChart = ref(false);
    const refreshIntervalInstance = ref(0);
    const legend = ref({ show: false, list: [] });
    const curChartOption = ref(null);
    let chart = null;
    const localChartHeight = ref(0);
    const clickTimer = ref(null);
    const showTitleTool = ref(false);
    const extendMetricData = ref(null);
    const tooltipSize = ref([]);
    const tableToolSize = ref(0);
    const seriesData = ref([]);
    const showRestore = ref(false);
    const scatterTips = ref({
      show: false,
      top: 100,
      left: 0,
      data: {
        time: '',
        list: [],
        target: {
          color: 'red',
          label: 'CPU: 0.99',
        },
      },
    });

    const drawRecord = reactive({
      lastY: 0,
      moving: false,
    });

    const resizeHandler = ref(null); // 根据具体逻辑定义
    const unwatchOptions = ref(null); // 根据具体逻辑定义
    const unwatchSeries = ref(null); // 根据具体逻辑定义
    const needObserver = ref(true);
    const chartInfo = useChartInfoInject();
    const isRootCause = computed(() => {
      return chartInfo?.is_feedback_root;
    });
    const isRoot = computed(() => {
      return chartInfo?.entity?.is_root;
    });
    // 销毁时的逻辑处理
    onUnmounted(() => {
      if (intersectionObserver.value) {
        intersectionObserver.value.disconnect();
      }
    });
    // 获取seriesData
    const handleSeriesData = async (startTime, endTime) => {
      loading.value = true;
      showRestore.value = props.chartType === 'line' && !enableSelectionRestoreAll.value && !!startTime;
      intersectionObserver.value?.unobserve(failureChartWrapRef.value);
      intersectionObserver.value?.disconnect?.();
      needObserver.value = false;
      try {
        const isRange = startTime && startTime.length > 0 && endTime && endTime.length > 0;
        const data = await props.getSeriesData(startTime, endTime, isRange).catch(() => {
          return [];
        });
        seriesData.value = [...data].map(item => ({
          ...item,
          key: item.target.replace(/\./g, '_'),
        }));
        !chart && initChart();
        if (!isEchartsRender.value || Array.isArray(data)) {
          await handleSetChartData(data);
        } else {
          noData.value = true;
        }
      } catch {
        noData.value = true;
      } finally {
        chartTitle.value = props.title;
        chartSubTitle.value = props.subtitle;
        loading.value = false;
      }
    };
    const dimensionsList = computed(() => {
      return props.detail?.dimensions || [];
    });
    // 默认的tooltip配置
    const defaultOptions = computed(() => {
      if (props.chartType === 'bar' || props.chartType === 'line') {
        return {
          tooltip: {
            className: 'failure-chart-tooltips-box',
            axisPointer: {
              axis: 'auto',
              type: 'cross',
              label: {
                show: false,
                // formatter: params => {
                //   if (props.chartType !== 'line') return;
                //   if (params.axisDimension === 'y') {
                //     curValue.value.yAxis = params.value;
                //   } else {
                //     curValue.value.xAxis = params.value;
                //     curValue.value.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
                //   }
                // },
              },
              crossStyle: {
                opacity: 0,
                width: 0,
                color: 'transparent',
              },
            },
            // formatter: handleSetTooltip,
            appendToBody: true,
            position: (pos, params, dom, rect, size: any) => {
              const { contentSize } = size;
              const chartRect = chartRef.value.getBoundingClientRect();
              const posRect = {
                y: chartRect.y + +pos[1],
                x: chartRect.x + +pos[0],
              };
              const position = {
                top: 0,
                left: 0,
              };
              const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
              if (canSetBottom) {
                position.top = +pos[1] - Math.min(20, canSetBottom);
              } else {
                position.top = +pos[1] + canSetBottom - 20;
              }
              const canSetLeft = window.innerWidth - posRect.x - contentSize[0];
              if (canSetLeft) {
                position.left = +pos[0] + Math.min(20, canSetLeft);
              } else {
                position.left = +pos[0] - contentSize[0] - 20;
              }
              if (contentSize[0]) tooltipSize.value = contentSize;
              return position;
            },
          },
        };
      }
      return {};
    });

    // 结合默认选项和传入选项的chartOption
    const chartOption = computed(() => {
      return deepMerge(
        {
          tooltip: {
            trigger: 'axis',
            triggerOn: 'mousemove|click',
          },
          legend: {
            asTable: false, // 是否转换为table图例
            toTheRight: false, // 图例位置在右侧
            maxHeight: 30, // 图例最大高度 只对toTheRight为false有效
          },
          tool: {
            show: true, // 工具栏是否显示
            moreList: ['explore', 'set', 'strategy', 'area'], // 要显示的多工具栏的配置id 空数组则为不显示
            list: ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'strategy', 'area', 'relate-alert'],
          },
          annotation: {
            show: false, // 是否显示annotation
            list: ['ip', 'process', 'strategy'], // 要显示的anotation配置id 空数组则为不显示
          },
        },
        (props.options || {}) as any,
        {
          arrayMerge: (destinationArray, sourceArray) => sourceArray,
        }
      );
    });

    const chartWrapHeight = computed(() => {
      let height = Number(localChartHeight.value);
      if (chartTitle.value) {
        height -= 36;
      }
      if (props.hasResize) {
        height -= 10;
      }
      return height;
    });

    const chartHeight = computed(() => {
      let height = chartWrapHeight.value;
      if (!chartOption.value.legend.toTheRight && chartOption.value.legend.show) {
        height -= chartOption.value.legend.maxHeight;
      }
      return height;
    });

    const isEchartsRender = computed(() => {
      return !['status', 'text', 'table'].includes(props.chartType);
    });
    // 观察`height`的变化
    watch(
      () => props.height,
      newVal => {
        localChartHeight.value = newVal || 0;
      },
      { immediate: true }
    );

    // 观察`localChartHeight`的变化
    watch(
      () => localChartHeight.value,
      () => {
        if (chart?.resize) {
          chart.resize();
        }
      },
      { immediate: true }
    );
    const onRefreshIntervalChange = newVal => {
      if (refreshIntervalInstance.value) {
        window.clearInterval(refreshIntervalInstance.value);
      }
      if (newVal <= 0 || !props.getSeriesData) return;
      refreshIntervalInstance.value = window.setInterval(() => {
        // 当loading为false且chart存在时，执行某些操作（如更新序列数据）
        if (!loading.value && chart) {
          handleSeriesData();
        }
      }, props.refreshInterval);
    };
    // 观察`refreshInterval`的变化
    watch(
      () => props.refreshInterval,
      newVal => {
        onRefreshIntervalChange(newVal);
      },
      { immediate: true }
    );

    // 观察`series`的变化
    watch(
      () => props.series,
      newVal => {
        handleSetChartData(deepMerge({}, { series: newVal }));
      }
    );
    watch(
      () => showRestoreInject.value,
      newVal => {
        showRestore.value = newVal;
      },
      { immediate: true }
    );

    onMounted(() => {
      if (props.series) {
        initChart();
        handleSetChartData(deepMerge({}, { series: props.series }));
      } else if (chartOption.value?.series?.length) {
        initChart();
        handleSetChartData(deepMerge({}, chartOption.value));
      }
      if (props.getSeriesData) {
        registerObserver();
        intersectionObserver.value?.observe(failureChartWrapRef.value);
      }
    });

    // 使用onActivated替代activated生命周期钩子
    onActivated(() => {
      onRefreshIntervalChange(props.refreshInterval);
      if (props.autoresize && chart?.resize) {
        chart.resize();
      }
    });

    // 使用onDeactivated替代deactivated生命周期钩子
    onDeactivated(() => {
      refreshIntervalInstance.value && window.clearInterval(refreshIntervalInstance.value);
    });

    // 使用onBeforeUnmount替代beforeDestroy生命周期钩子
    onBeforeUnmount(() => {
      timeRange.value = [];
      // 假设unwatchSeries 和 unwatchOptions是两个解除监听的方法
      unwatchSeries.value?.();
      unwatchOptions.value?.();
      if (intersectionObserver.value) {
        intersectionObserver.value.unobserve(failureChartWrapRef.value);
        intersectionObserver.value.disconnect();
      }
      annotation.value.show = false;
      refreshIntervalInstance.value && window.clearInterval(refreshIntervalInstance.value);
    });

    // 使用onUnmounted替代destroyed生命周期钩子
    onUnmounted(() => {
      chart && destroy();
      document.removeEventListener('mousemove', documentMousemove);
      document.removeEventListener('mouseup', documentMouseup);
    });
    // 图表拉伸处理事件
    const documentMousemove = e => {
      drawRecord.moving = true;
      localChartHeight.value += e.clientY - drawRecord.lastY;
      drawRecord.lastY = e.clientY;
    };

    // 拉伸停止处理函数
    const documentMouseup = () => {
      drawRecord.moving = false;
      document.removeEventListener('mousemove', documentMousemove);
      document.removeEventListener('mouseup', documentMouseup);
    };

    // 初始化拉伸处理
    const handleResize = e => {
      drawRecord.lastY = e.clientY;
      document.addEventListener('mousemove', documentMousemove);
      document.addEventListener('mouseup', documentMouseup);
    };
    const initChart = () => {
      chartTitle.value = props.title;
      chartSubTitle.value = props.subtitle;
      if (isEchartsRender.value && chartRef.value) {
        const initializedChart = echarts.init(chartRef.value);
        chart = initializedChart;
        if (props.groupId) {
          chart.group = props.groupId;
        }
        if (props.autoresize) {
          const handler = debounce(300, () => resize());
          resizeHandler.value = async () => {
            await nextTick();
            chartRef.value?.offsetParent !== null && handler();
          };
          addListener(chartRef.value, resizeHandler.value);
          window.addEventListener('resize', handler);
        }
      }
    };
    const registerObserver = () => {
      intersectionObserver.value = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (needObserver.value) {
            if (entry.intersectionRatio > 0) {
              handleSeriesData();
            } else {
              // 解决临界点、慢滑不加载数据问题
              const { top, bottom } = failureChartWrapRef.value.getBoundingClientRect();
              if (top === 0 && bottom === 0) return;
              const { innerHeight } = window;
              const isVisiable = (top > 0 && top <= innerHeight) || (bottom >= 0 && bottom < innerHeight);
              isVisiable && handleSeriesData();
            }
          }
        });
      });
    };
    const handleTransformSeries = data => {
      if (data?.series) {
        return data;
      }
      const mapData = {};
      return {
        series: data?.map(({ datapoints, target, ...item }) => {
          mapData[target] !== undefined ? (mapData[target] += 1) : (mapData[target] = 0);
          return {
            ...item,
            data: datapoints.map(set => (Array.isArray(set) ? set.slice().reverse() : [])),
            name: !mapData[target] ? target : target + mapData[target],
            symbolSize: 6,
            showSymbol: false,
          };
        }),
      };
    };
    const handleSetChartData = data => {
      if (!chart) {
        initChart();
      }
      if (isEchartsRender.value) {
        const series = deepMerge([], data || []);
        const hasSeries =
          (series && series.length > 0 && series.some(item => item?.datapoints?.length)) ||
          (series && Object.hasOwn(series, 'series') && series.series.length);
        noData.value = !hasSeries;
        if (!hasSeries) {
          return;
        }
        const realSeries = Object.hasOwn(series, 'series') ? series.series : series;
        if (props.chartType === 'line' && realSeries[0]?.metric) {
          const [
            {
              metric: { metric_field: metricFiled, extend_data: extendData },
            },
          ] = realSeries;
          // 获取图表的指标信息 多指标情况下不显示
          let hasExtendMetricData = extendData;
          if (extendData) {
            hasExtendMetricData = realSeries.every(item => item?.metric?.metric_field === metricFiled);
          }
          extendMetricData.value = hasExtendMetricData ? extendData : null;
        }
        chartOptionInstance.value = new EchartOptions({
          lineWidth: props.lineWidth,
          chartType: props.chartType,
          colors: props.colors,
          showExtremum: chartOption.value.legend.asTable,
          chartOption: chartOption.value,
        });

        const optionData = chartOptionInstance.value.getOptions(handleTransformSeries(series), {});
        if (['bar', 'line'].includes(props.chartType)) {
          legend.value.show = hasSeries && optionData.legendData.length > 0;
        } else {
          legend.value.show = optionData.options.lengend
            ? Object.hasOwn(optionData.options.lengend, 'show')
              ? optionData.options.lengend.show
              : true
            : false;
        }
        legend.value.list = optionData.legendData || [];
        if (chartOption.value.grid) {
          optionData.options.grid.bottom = (chartOption.value.grid as MonitorEchartOptions['grid']).bottom;
        }
        setTimeout(() => {
          if (chart) {
            let options = deepMerge(optionData.options, defaultOptions.value) as MonitorEchartOptions;
            const width = chartRef.value?.clientWidth;
            if (['line', 'bar'].includes(props.chartType) && width) {
              options = deepMerge(options, {
                xAxis: {
                  splitNumber: Math.ceil(width / 100),
                  min: 'dataMin',
                },
              });
            }
            chart.setOption(options, {
              notMerge: true,
              lazyUpdate: false,
              silent: false,
            });
            if (!hasInitChart.value) {
              hasInitChart.value = true;
              if (optionData.options.toolbox) {
                initChartAction();
                chart.on('dataZoom', async event => {
                  loading.value = true;
                  const [batch] = event.batch;
                  if (batch.startValue && batch.endValue) {
                    const timeFrom = dayjs(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                    let timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
                    if (!showTitleTool.value) {
                      const dataPoints = seriesData.value?.[0]?.datapoints;
                      if (dataPoints?.length) {
                        const maxX = dataPoints[dataPoints.length - 1]?.[1];
                        if (+batch.endValue.toFixed(0) === maxX) {
                          timeTo = dayjs().format('YYYY-MM-DD HH:mm');
                        }
                      }
                    }
                    timeRange.value = [timeFrom, timeTo];
                    if (props.getSeriesData) {
                      chart.dispatchAction({
                        type: 'restore',
                      });
                      if (enableSelectionRestoreAll.value) {
                        handleChartDataZoom.value(JSON.parse(JSON.stringify(timeRange.value)));
                      } else {
                        await handleSeriesData(timeFrom, timeTo);
                      }
                    }
                    emit('data-zoom', timeRange.value);
                  }
                  loading.value = false;
                });
              }
              initChartEvent();
            }
            noData.value = !hasSeries;
            curChartOption.value = Object.freeze(Object.assign({}, chart.getOption()));
          }
        }, 320);
      }
    };
    const handleSetTooltip = params => {
      if (!showTitleTool.value) return undefined;
      if (!params || params.length < 1 || params.every(item => item.value[1] === null)) {
        if (props.chartType === 'line') {
          Object.assign(curValue, {
            color: '',
            name: '',
            seriesIndex: -1,
            dataIndex: -1,
            xAxis: '',
            yAxis: '',
          });
        }
        return;
      }
      const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
      const data = params
        .map(item => ({ color: item.color, seriesName: item.seriesName, value: item.value[1] }))
        .sort((a, b) => Math.abs(a.value - +curValue.value.yAxis) - Math.abs(b.value - +curValue.value.yAxis));
      const list = params.filter(item => !item.seriesName.match(/-no-tips$/));
      const liHtmlList = list
        .slice(0, 50)
        .sort((a, b) => b.value[1] - a.value[1])
        .map(item => {
          let markColor = 'color: #fafbfd;';
          if (data[0].value === item.value[1]) {
            markColor = 'color: #ffffff;font-weight: bold;';
            if (props.chartType === 'line') {
              Object.assign(curValue, {
                color: item.color,
                name: item.seriesName,
                seriesIndex: item.seriesIndex,
                dataIndex: item.dataIndex,
                xAxis: item.value[0],
                yAxis: item.value[1],
                seriesType: params.seriesType,
              });
            }
          }
          if (item.value[1] === null) return '';
          const curSeries = curChartOption.value.series[item.seriesIndex];
          const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
          const minBase = curSeries.minBase || 0;
          const precision = curSeries.unit !== 'none' && +curSeries.precision < 1 ? 2 : +curSeries.precision;
          const valueObj = unitFormatter(item.value[1] - minBase, precision);
          return `<li class="tooltips-content-item">
                        <span class="item-series"
                         style="background-color:${item.color};">
                        </span>
                        <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                        <span class="item-value" style="${markColor}">
                        ${valueObj.text} ${valueObj.suffix || ''}</span>
                        </li>`;
        });
      if (liHtmlList?.length < 1) return '';
      let ulStyle = '';
      const maxLen = Math.ceil((window.innerHeight - 100) / 20);
      if (list.length > maxLen && tooltipSize.value) {
        const cols = Math.ceil(list.length / maxLen);
        tableToolSize.value = tableToolSize.value
          ? Math.min(tableToolSize.value, tooltipSize.value[0])
          : tooltipSize.value[0];
        ulStyle = `display:flex; flex-wrap:wrap; width: ${5 + cols * tableToolSize.value}px;`;
      }
      const hasTrace = params.some(item => item.seriesName === 'bk_trace_value' && item.seriesType === 'scatter');
      if (hasTrace || (props.hasTraceInfo && scatterTips.value.show)) {
        return '';
      }
      return `<div class="monitor-chart-tooltips">
                    <p class="tooltips-header">
                        ${pointTime}
                    </p>
                    <ul class="tooltips-content" style="${ulStyle}">
                        ${liHtmlList?.join('')}
                    </ul>
                    </div>`;
    };
    const handleChartDblClick = () => {
      clearTimeout(clickTimer.value);
      if (timeRange.value.length > 0) {
        timeRange.value = [];
        chart.dispatchAction({
          type: 'restore',
        });
        setTimeout(() => {
          handleSeriesData();
        }, 100);
      }
      emit('dblclick');
    };
    // 复位逻辑
    const handleChartRestore = () => {
      if (enableSelectionRestoreAll.value) {
        handleRestoreEvent.value();
      } else {
        handleChartDblClick();
      }
    };
    const handleMoreToolItemSet = item => {
      switch (item.id) {
        case 'save':
          handleCollectChart();
          break;
        case 'screenshot':
          handleStoreImage();
          break;
        case 'fullscreen':
          handleFullScreen();
          break;
        case 'area':
          handleTransformArea(item.checked);
          break;
        case 'set':
          handleSetYAxisSetScale(!item.checked);
          break;
        case 'explore':
          handleExplore();
          break;
        case 'strategy':
          handleAddStrategy();
          break;
        case 'relate-alert':
          emit('relate-alert');
          break;
        default:
          break;
      }
    };
    const handleSelectChildMenu = data => {
      switch (data.menu.id) {
        case 'more':
          if (data.child.id === 'screenshot') {
            setTimeout(() => {
              handleStoreImage();
            }, 300);
          }
          break;
        default:
          break;
      }
    };
    const handleSetYAxisSetScale = needScale => {
      emit('on-yaxis-set-scale', needScale);
      if (props.chartType === 'line' && chart) {
        const options = chart.getOption();
        chart.setOption({
          ...options,
          yAxis: {
            scale: needScale,
            min: needScale ? 'dataMin' : 0,
          },
        });
      }
    };
    const handleTransformArea = (isArea: boolean) => {
      emit('on-transform-area', isArea);
      if (props.chartType === 'line' && chart) {
        const options = chart.getOption();
        chart.setOption({
          ...options,
          series: options.series.map((item, index) => ({
            ...item,
            areaStyle: {
              color: isArea ? hexToRgbA(props.colors[index % props.colors.length], 0.2) : 'transparent',
            },
          })),
        });
      }
    };
    const setOnlyOneMarkArea = () => {
      const showSeries = [];
      legend.value.list.forEach(l => {
        if (l.show) {
          const serice = seriesData.value.find(s => s.target === l.name);
          showSeries.push({
            ...serice,
            color: l.color,
          });
        }
      });

      const optionData = chartOptionInstance.value.getOptions(handleTransformSeries(showSeries), {});
      chart.setOption(deepMerge(optionData.options, defaultOptions.value), {
        notMerge: true,
        lazyUpdate: false,
        silent: false,
      });
    };

    const handleLegendEvent = ({ actionType, item }) => {
      if (legend.value.list.length < 2) {
        return;
      }
      if (actionType === 'shift-click') {
        item.show = !item.show;
        setOnlyOneMarkArea();
      } else if (actionType === 'click') {
        const hasOtherShow = legend.value.list
          .filter(legendItem => !legendItem.hidden)
          .some(set => set.name !== item.name && set.show);
        legend.value.list.forEach(legend => {
          legend.show = legend.name === item.name || !hasOtherShow;
        });
        setOnlyOneMarkArea();
      }
    };
    const handleStoreImage = async () => {
      const el = failureChartWrapRef.value; // 访问组件根DOM元素
      if (!el) return;

      if (window.navigator?.msSaveOrOpenBlob) {
        toBlob(el)
          .then(blob => window.navigator.msSaveOrOpenBlob(blob, `${props.title}.png`))
          .catch(() => {});
      } else {
        if (props.chartType === 'table') {
          await nextTick();
          const cloneEl = el.cloneNode(true);
          // 这里是对克隆元素的样式调整，省略部分代码...
          const divEl = document.createElement('div');
          divEl.setAttribute('style', 'position: fixed; top: -10000px');
          divEl.appendChild(cloneEl);
          el.appendChild(divEl);
          const width = cloneEl.clientWidth;
          const height = cloneEl.clientHeight;

          toPng(cloneEl, { width, height })
            .then(dataUrl => {
              const tagA = document.createElement('a');
              tagA.download = `${props.title}.png`;
              tagA.href = dataUrl;
              document.body.appendChild(tagA);
              tagA.click();
              tagA.remove();
              divEl.remove();
            })
            .catch(() => {
              divEl.remove();
            });
        } else {
          toPng(el)
            .then(dataUrl => {
              const tagA = document.createElement('a');
              tagA.download = `${props.title}.png`;
              tagA.href = dataUrl;
              document.body.appendChild(tagA);
              tagA.click();
              tagA.remove();
            })
            .catch(e => console.info(e));
        }
      }
    };
    const handleExplore = () => {
      emit('export-data-retrieval');
    };
    const handleAddStrategy = () => {
      emit('add-strategy');
    };
    const handleCharBlur = () => {
      annotation.value.show = false;
    };
    const handleCollectChart = () => {
      emit('collect-chart');
    };
    // 设置全屏
    const handleFullScreen = () => {
      emit('full-screen');
    };
    const resize = (options: MonitorEchartOptions = null) => {
      chartRef.value && delegateMethod('resize', options);
    };
    const dispatchAction = payload => {
      delegateMethod('dispatchAction', payload);
    };
    const delegateMethod = (name, ...args) => {
      return chart[name](...args);
    };
    function initChartAction() {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    }
    const initChartEvent = () => {
      if (props.hasTraceInfo) {
        chart?.on('click', 'series.scatter', e => {
          const chartOptions = chart.getOption();
          scatterTips.value.data.target.color = chartOptions.color[0];
          const labelList = ['bk_trace_id', 'bk_span_id', 'bk_trace_value'];
          const displayNames = {
            bk_trace_id: 'traceID',
            bk_span_id: 'spanID',
            bk_trace_value: 'traceValue',
          };
          const { scatterData } = e.data;
          scatterTips.value.data.list = labelList.map(item => ({
            type: item === labelList[2] ? 'string' : 'link',
            label: displayNames[item] || item,
            content: scatterData[item],
          }));
          scatterTips.value.data.target.label = `${chartOptions.series[0].name}: ${
            scatterData._value || scatterData.metric_value || '--'
          }`;
          scatterTips.value.data.time = dayjs.tz(e.data.value[0]).format('YYYY-MM-DD HH:mm:ss');
          scatterTips.value.top = -9999;
          scatterTips.value.show = true;
          nextTick(() => {
            const chartWidth = charWrapRef.value.clientWidth + 10;
            const scatterTipW = scatterTipsRef.value.clientWidth;
            const { offsetY } = e.event;
            const offsetX = e.event.offsetX + 10;
            const left = chartWidth - offsetX < scatterTipW ? offsetX - scatterTipW - 10 : offsetX + 10;
            const top = offsetY;
            scatterTips.value.left = left;
            scatterTips.value.top = top;
            scatterTips.value.show = true;
            const { series } = chartOptions;
            series.map(item => {
              if (item.type === 'scatter' && item.name === 'bk_trace_value') {
                item.data.map(d => {
                  if (JSON.stringify(d.value) === JSON.stringify(e.data.value)) {
                    d.itemStyle.color = '#699DF4';
                  }
                });
              }
            });
            chart.setOption({
              series,
            });
          });
        });
        chart?.on('mouseover', 'series.scatter', () => {
          chartRef.value.querySelector('canvas').style.cursor = 'pointer';
        });
        chart?.on('mouseout', 'series.scatter', () => {
          chartRef.value.querySelector('canvas').style.removeProperty('cursor');
        });
      }
      chart?.on('click', e => {
        emit('chart-click', e);
      });
    };

    const destroy = () => {
      if (props.autoresize && chartRef.value) {
        removeListener(chartRef.value, resizeHandler.value);
      }
      delegateMethod('dispose');
      chart = null;
    };
    const handleCopy = value => {
      copyText(value); // 假设 copyText 函数已定义并且可以正常工作
      Message({
        theme: 'success',
        message: t('复制成功'),
      });
    };

    /* trace id 跳转 */
    const handleTraceLink = item => {
      if (item.type === 'link' && item.label === 'traceID') {
        const traceId = item.content;
        traceListById({
          bk_biz_id: props.curBizId,
          trace_ids: [traceId],
          ...props.traceInfoTimeRange,
        }).then(data => {
          const url = data?.[0]?.url || '';
          if (url) {
            window.open(`${location.origin}${url}`);
          }
        });
      }
    };
    const handleSuccessLoad = () => {
      emit('successLoad');
    };
    return {
      t,
      showTitleTool,
      chartSubTitle,
      chartTitle,
      chartOption,
      readonly,
      handleMoreToolItemSet,
      handleSelectChildMenu,
      charWrapRef,
      chartWrapHeight,
      chartRef,
      handleCharBlur,
      showRestore,
      handleChartRestore,
      chartHeight,
      legend,
      scatterTips,
      scatterTipsRef,
      noData,
      handleTraceLink,
      handleCopy,
      handleResize,
      handleLegendEvent,
      failureChartWrapRef,
      loading,
      handleSuccessLoad,
      isRootCause,
      isRoot,
      dimensionsList,
    };
  },
  render() {
    return (
      <div
        ref='failureChartWrapRef'
        style={{ 'background-image': this.$props.backgroundUrl }}
        class='failure-chart-wrap'
        onMouseenter={() => (this.showTitleTool = true)}
        onMouseleave={() => (this.showTitleTool = false)}
      >
        {this.$props.title && (
          <div class='echart-header'>
            <ChartTitle
              class='chart-title-wrap'
              v-slots={{
                title: () => (
                  <div class='root-head'>
                    <span class='txt'>{this.$props.title}</span>
                    {(this.isRoot || this.isRootCause) && (
                      <label class={['root', { 'is-root-cause': this.isRootCause }, { 'is-root': this.isRoot }]}>
                        {this.t('根因')}
                      </label>
                    )}
                  </div>
                ),
                subtitle: () => (
                  <div class='sub-head'>
                    <span
                      class='txt'
                      v-bk-tooltips={{
                        content: (
                          <div style={{ 'max-width': '360px' }}>
                            {this.t('指标：')}
                            <br />
                            {this.$props.subtitle}
                          </div>
                        ),
                      }}
                    >
                      {this.$props.subtitle}
                    </span>
                  </div>
                ),
                tagTitle: () => (
                  <div class='tag-head'>
                    <TagDisplay
                      tagsList={this.dimensionsList}
                      tipsName={this.t('维度：')}
                    />
                  </div>
                ),
              }}
              isShowAlarm={true}
              menuList={this.chartOption.tool.list || []}
              showMore={true}
              subtitle={this.$props.subtitle || ''}
              title={this.$props.title}
              onMenuClick={this.handleMoreToolItemSet}
              onSelectChild={this.handleSelectChildMenu}
              onSuccessLoad={this.handleSuccessLoad}
            />
          </div>
        )}
        <Loading
          class='failure-chart-wrap-loading'
          loading={this.loading}
        >
          <div
            ref='charWrapRef'
            style={{
              flexDirection: !this.chartOption.legend.toTheRight ? 'column' : 'row',
              minHeight: `${this.chartWrapHeight}px`,
              maxHeight: `${this.chartWrapHeight}px`,
            }}
            class='chart-wrapper-echarts'
            tabindex='-1'
            onBlur={this.handleCharBlur}
          >
            {!this.noData && (
              <div
                style={{ height: `${this.chartHeight}px` }}
                class='echart-instance-wrap'
              >
                <div
                  ref='chartRef'
                  class='echart-instance'
                />
                {this.showRestore && (
                  <span
                    class='chart-restore'
                    onClick={this.handleChartRestore}
                  >
                    {this.t('复位')}
                  </span>
                )}
              </div>
            )}
            {!this.noData && (
              <div
                style={{
                  maxHeight: `${this.chartOption.legend.toTheRight ? this.chartHeight : this.chartOption.legend.maxHeight}px`,
                }}
                class='echart-legend'
              >
                {this.legend.show && (
                  <CommonLegend
                    legend-data={this.legend.list}
                    legend-type={this.chartOption.legend.asTable ? 'table' : 'common'}
                    to-the-right={this.chartOption.legend.toTheRight}
                    onLegendEvent={this.handleLegendEvent}
                  />
                )}
              </div>
            )}
          </div>
        </Loading>
        {this.noData && <div class='echart-content'>{this.$props.emptyText}</div>}
        {this.scatterTips.show && this.$props.hasTraceInfo && (
          <div
            ref='scatterTipsRef'
            style={{
              left: `${this.scatterTips.left}px`,
              top: `${this.scatterTips.top}px`,
            }}
            class='scatter-tips'
          >
            <div class='time'>{this.scatterTips.data.time}</div>
            <div class='bottom'>
              {this.scatterTips.data.list.map(item => (
                <div
                  key={item.label}
                  class='info-item'
                >
                  <span class='label'>{item.label}: </span>
                  {item.type === 'link' && (
                    <span class='content'>
                      <span
                        class={['link', { pointer: item.label === 'traceID' }]}
                        onClick={() => this.handleTraceLink(item)}
                      >
                        {item.content}
                      </span>
                      <span
                        class='icon-monitor copy icon-mc-copy'
                        onClick={() => this.handleCopy(item.content)}
                      />
                    </span>
                  )}
                  {item.type === 'string' && <span>{item.content}</span>}
                </div>
              ))}
              <span
                style={{ background: this.scatterTips.data.target.color }}
                class='point'
              />
              <span class='label'>{this.scatterTips.data.target.label}</span>
            </div>
          </div>
        )}
        {this.$props.errorMsg && (
          <span
            class='is-error'
            v-bk-tooltips={{
              content: this.$props.errorMsg,
              placement: 'top-start',
              extCls: 'monitor-wrapper-error-tooltip',
              allowHTML: false,
            }}
          />
        )}
        {this.$props.hasResize && (
          <div
            class='chart-resize-line'
            onMousedown={this.handleResize}
          />
        )}
      </div>
    );
  },
});
