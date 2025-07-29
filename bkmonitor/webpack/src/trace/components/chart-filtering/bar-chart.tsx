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
  type PropType,
  type WatchStopHandle,
  defineComponent,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { type MonitorEchartOptions, echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';

export const BarChartProps = {
  // echart 配置
  options: {
    type: Object as PropType<MonitorEchartOptions>,
    required: true,
  },
  // 当前滑动选择的时间范围
  selectedRange: {
    type: Array as PropType<number[]>,
    required: true,
  },
};

export default defineComponent({
  name: 'BarChart',
  props: BarChartProps,
  setup(props) {
    // 当前图表配置取消监听函数
    let unwatchOptions: null | WatchStopHandle = null;
    const chartRef = ref<HTMLDivElement>();
    // echarts 实例
    const instance = shallowRef<echarts.ECharts>();

    onMounted(() => {
      initChart();
      addListener(chartRef.value!, handleResize);
    });
    onBeforeUnmount(() => {
      destroy();
      removeListener(chartRef.value!, handleResize);
    });

    // echarts 实例销毁
    function destroy() {
      instance.value = undefined;
    }
    // 初始化echart
    function initChart() {
      if (!instance.value) {
        instance.value = echarts.init(chartRef.value!);
        instance.value.setOption({
          ...(props.options || {}),
        });
        initPropsWatcher();
      }
    }
    // 初始化Props监听
    function initPropsWatcher() {
      unwatchOptions = watch(
        () => props.selectedRange,
        () => {
          initChart();
          if (instance.value) {
            initChart();
            instance.value.setOption({
              ...(props.options || {}),
            });
          }
        },
        { deep: true }
      );
    }
    /** 监听resize */
    function handleResize() {
      instance.value?.resize({
        silent: true,
      });
    }

    return { chartRef, unwatchOptions };
  },
  render() {
    return (
      <div
        ref='chartRef'
        style='height:56px'
        class='bar-chart'
      />
    );
  },
});
