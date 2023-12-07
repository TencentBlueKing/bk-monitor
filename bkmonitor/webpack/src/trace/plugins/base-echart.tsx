/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
  defineComponent,
  onActivated,
  onBeforeUnmount,
  onMounted,
  PropType,
  ref,
  shallowRef,
  watch,
  WatchStopHandle
} from 'vue';
import dayjs from 'dayjs';
import type { EChartOption, ECharts } from 'echarts';
import * as echarts from 'echarts';

import './base-echart.scss';

const MOUSE_EVENTS = ['click', 'dblclick', 'mouseover', 'mouseout', 'mousedown', 'mouseup', 'globalout'];
export const BaseChartProps = {
  // 视图高度
  height: {
    type: Number,
    required: true
  },
  // 视图宽度 默认撑满父级
  width: Number,
  // echart 配置
  options: {
    type: Object as PropType<EChartOption>,
    required: true
  },
  // echarts图表实例分组id
  groupId: {
    type: String,
    default: ''
  }
};
export default defineComponent({
  name: 'BaseEchart',
  props: BaseChartProps,
  emits: [...MOUSE_EVENTS, 'dataZoom', 'dblClick'],
  setup(props, { emit }) {
    const chartRef = ref<HTMLDivElement>();
    // 当前图表配置
    let curChartOption: EChartOption | null = null;
    // echarts 实例
    const instance = shallowRef<ECharts>();
    // 当前图表配置取消监听函数
    let unwatchOptions: WatchStopHandle | null = null;
    // dblclick模拟 间隔
    const clickTimer = ref(0);
    // 当前视图是否hover
    const isMouseOver = ref(false);
    // hover视图上 当前对应最近点数据
    const curPoint = ref({ xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 });
    // tooltips大小 [width, height]
    let tooltipSize: number[] = [];
    let tableToolSize = 0;
    const tooltip = {
      axisPointer: {
        type: 'cross',
        axis: 'auto',
        label: {
          show: false,
          formatter: (params: any) => {
            if (params.axisDimension === 'y') {
              curPoint.value.yAxis = params.value;
            } else {
              curPoint.value.xAxis = params.value;
              curPoint.value.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
            }
          }
        },
        crossStyle: {
          color: 'transparent',
          opacity: 0,
          width: 0
        }
      },
      appendToBody: true,
      formatter: (p: any) => handleSetTooltip(p),
      position: (pos: (string | number)[], params: any, dom: any, rect: any, size: any) => {
        const { contentSize } = size;
        const chartRect = chartRef.value!.getBoundingClientRect();
        const posRect = {
          x: chartRect.x + +pos[0],
          y: chartRect.y + +pos[1]
        };
        const position = {
          left: 0,
          top: 0
        };
        const canSetBootom = window.innerHeight - posRect.y - contentSize[1];
        if (canSetBootom > 0) {
          position.top = +pos[1] - Math.min(20, canSetBootom);
        } else {
          position.top = +pos[1] + canSetBootom - 20;
        }
        const canSetLeft = window.innerWidth - posRect.x - contentSize[0];
        if (canSetLeft > 0) {
          position.left = +pos[0] + Math.min(20, canSetLeft);
        } else {
          position.left = +pos[0] - contentSize[0] - 20;
        }
        if (contentSize[0]) tooltipSize = contentSize;
        return position;
      },
      ...(props.options?.tooltip || {})
    };
    // 高度变化
    watch(
      () => props.height,
      height => {
        if (Number(height) < 200) {
          instance.value?.setOption({
            yAxis: {
              splitNumber: 2,
              scale: false
            }
          });
        }
        instance.value?.resize({
          silent: true
        });
      }
    );
    // 宽度变化
    watch(
      () => props.width,
      width => {
        instance.value?.setOption({
          xAxis: {
            splitNumber: Math.ceil(Number(width) / 150),
            min: 'dataMin'
          }
        });
        instance.value?.resize({
          silent: true
        });
      }
    );

    onMounted(initChart);
    onActivated(resize);
    onBeforeUnmount(destroy);
    // 设置tooltip
    function handleSetTooltip(params: any) {
      if (!isMouseOver.value) return undefined;
      if (!params || params.length < 1 || params.every((item: any) => item.value[1] === null)) {
        curPoint.value = {
          color: '',
          name: '',
          seriesIndex: -1,
          dataIndex: -1,
          xAxis: '',
          yAxis: ''
        };
        return;
      }
      let liHtmls = [];
      let ulStyle = '';
      const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
      if (params[0]?.data?.tooltips) {
        liHtmls.push(params[0].data.tooltips);
      } else {
        const data = params
          .map((item: { color: any; seriesName: any; value: any[] }) => ({
            color: item.color,
            seriesName: item.seriesName,
            value: item.value[1]
          }))
          .sort(
            (a: { value: number }, b: { value: number }) =>
              Math.abs(a.value - +curPoint.value.yAxis) - Math.abs(b.value - +curPoint.value.yAxis)
          );
        const list = params.filter((item: { seriesName: string }) => !item.seriesName.match(/-no-tips$/));
        liHtmls = list
          .sort((a: { value: number[] }, b: { value: number[] }) => b.value[1] - a.value[1])
          .map(
            (item: { value: number[]; color: any; seriesName: any; seriesIndex: string | number; dataIndex: any }) => {
              let markColor = 'color: #fafbfd;';
              if (data[0].value === item.value[1]) {
                markColor = 'color: #fff;font-weight: bold;';
                curPoint.value = {
                  color: item.color,
                  name: item.seriesName,
                  seriesIndex: +item.seriesIndex,
                  dataIndex: item.dataIndex,
                  xAxis: item.value[0] as any,
                  yAxis: item.value[1] as any
                };
              }
              if (item.value[1] === null) return '';
              const curSeries: any = curChartOption!.series?.[+item.seriesIndex];
              const unitFormater = curSeries.unitFormatter || ((v: string) => ({ text: v }));
              const minBase = curSeries.minBase || 0;
              const precision =
                !['none', ''].some(val => val === curSeries.unit) && +curSeries.precision < 1
                  ? 2
                  : +curSeries.precision;
              const valueObj = unitFormater(item.value[1] - minBase, precision);
              return `<li class="tooltips-content-item">
                  <span class="item-series"
                   style="background-color:${item.color};">
                  </span>
                  <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                  <span class="item-value" style="${markColor}">
                  ${valueObj.text} ${valueObj.suffix || ''}</span>
                  </li>`;
            }
          );
        if (liHtmls?.length < 1) return '';
        // 如果超出屏幕高度，则分列展示
        const maxLen = Math.ceil((window.innerHeight - 100) / 20);
        if (list.length > maxLen && tooltipSize) {
          const cols = Math.ceil(list.length / maxLen);
          tableToolSize = tableToolSize ? Math.min(tableToolSize, tooltipSize[0]) : tooltipSize[0];
          ulStyle = `display:flex; flex-wrap:wrap; width: ${5 + cols * tableToolSize}px;`;
        }
      }
      return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
            <ul class="tooltips-content" style="${ulStyle}">
                ${liHtmls?.join('')}
            </ul>
            </div>`;
    }
    // echarts 实例销毁
    function destroy() {
      delegateMethod('dispose');
      instance.value = undefined;
      isMouseOver.value = false;
    }
    // resize
    function resize(options?: echarts.EChartOption) {
      chartRef.value && delegateMethod('resize', options);
    }
    // 初始化echart
    function initChart() {
      if (!instance.value) {
        instance.value = echarts.init(chartRef.value!);
        instance.value.setOption({
          ...props.options,
          tooltip: {
            ...tooltip,
            ...props.options
          } as any
        });
        initPropsWatcher();
        initChartEvent();
        initChartAction();
        curChartOption = instance.value.getOption();
        props.groupId && (instance.value.group = props.groupId);
        instance.value.on('dataZoom', handleDataZoom);
      }
    }
    function handleDataZoom(event: { batch: [any] }) {
      if (isMouseOver.value) {
        const [batch] = event.batch;
        if (instance.value && batch.startValue && batch.endValue) {
          instance.value.dispatchAction({
            type: 'restore'
          });
          const timeFrom = dayjs.tz(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
          const timeTo = dayjs.tz(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
          emit('dataZoom', timeFrom, timeTo);
        }
      } else {
        instance.value?.dispatchAction({
          type: 'restore'
        });
      }
    }
    // 初始化Props监听
    function initPropsWatcher() {
      unwatchOptions = watch(
        () => props.options,
        () => {
          initChart();
          if (instance.value) {
            initChart();
            instance.value.setOption(
              {
                ...(props.options || {}),
                tooltip: {
                  ...tooltip,
                  ...(props.options || {})
                } as any
              },
              { notMerge: true, lazyUpdate: false, silent: true }
            );
            curChartOption = instance.value.getOption();
          }
        },
        { deep: false }
      );
    }
    // 初始化chart Action
    function initChartAction() {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true
      });
    }
    // 初始化chart 事件
    function initChartEvent() {
      MOUSE_EVENTS.forEach(event => {
        instance.value?.on(event, (params: any) => {
          emit(event, params);
        });
      });
    }
    // 派发action
    function dispatchAction(payload: unknown) {
      delegateMethod('dispatchAction', payload);
    }
    // 派发method
    function delegateMethod(name: string, ...args: any) {
      return (instance.value as any)?.[name]?.(...args);
    }
    // 派发get
    function delegateGet(methodName: string) {
      return (instance.value as any)?.[methodName]?.();
    }
    function handleDblClick(e: MouseEvent) {
      e.preventDefault();
      clearTimeout(clickTimer.value);
      emit('dblClick', e);
    }
    function handleClick(e: MouseEvent) {
      clearTimeout(clickTimer.value);
      (clickTimer as any).value = setTimeout(() => {
        emit('click', e);
      }, 300);
    }
    function handleMouseover() {
      isMouseOver.value = true;
    }
    function handleMouseleave() {
      isMouseOver.value = false;
    }
    return {
      chartRef,
      tooltipSize,
      curPoint,
      curChartOption,
      tooltip,
      instance,
      isMouseOver,
      clickTimer,
      initChart,
      unwatchOptions,
      resize,
      initPropsWatcher,
      initChartAction,
      initChartEvent,
      dispatchAction,
      delegateMethod,
      delegateGet,
      handleSetTooltip,
      handleDblClick,
      handleClick,
      handleMouseover,
      handleMouseleave,
      handleDataZoom
    };
  },
  render() {
    return (
      <div
        class='chart-base'
        ref='chartRef'
        style={{ minHeight: `${1}px` }}
        onMouseover={this.handleMouseover}
        onMouseleave={this.handleMouseleave}
        onClick={this.handleClick}
        onDblclick={this.handleDblClick}
      />
    );
  }
});
