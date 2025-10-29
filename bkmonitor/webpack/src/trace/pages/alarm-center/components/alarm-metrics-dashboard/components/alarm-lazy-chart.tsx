/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
  type PropType,
  defineComponent,
  inject,
  onBeforeUnmount,
  provide,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { get } from '@vueuse/core';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import { DEFAULT_TIME_RANGE } from '../../../../../components/time-range/utils';
import ExploreChart from '../../../../trace-explore/components/explore-chart/explore-chart';

export default defineComponent({
  name: 'AlarmLazyChart',
  props: {
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
    showTitle: {
      type: Boolean,
      default: true,
    },
    formatterData: {
      type: Function as PropType<(val) => any>,
      default: res => res,
    },
    params: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
  },
  emits: ['dataZoomChange', 'durationChange'],
  setup(props, { emit }) {
    /** 视口监听器实例 */
    let intersectionObserverInstance = null;

    /** 根元素实例 */
    const chartContainerRef = useTemplateRef<HTMLElement>('chartContainerRef');

    /** 最终传给图表组件进行渲染的panel配置 */
    const viewerPanel = shallowRef<PanelModel>(new PanelModel({}));
    /** 最终传给图表组件进行请求的 param 参数 */
    const viewerParams = shallowRef<Record<string, any>>({});
    /** 最终传给图表组件进行请求的 timeRange 参数 */
    const viewerTimeRange = shallowRef(DEFAULT_TIME_RANGE);
    /** 最终决定是否立即刷新图表数据 */
    const viewerRefreshImmediate = shallowRef('');
    /** 图表相关配置 是否发生了改变 */
    const hasPanelChange = shallowRef(true);
    /** 根元素容器是否在可视区域 */
    const isInViewport = shallowRef(false);
    /** 数据时间范围，兼容视口懒加载逻辑，对 timeRange 进行拦截 */
    const timeRange = inject('timeRange', DEFAULT_TIME_RANGE);
    /** 是否立即刷新图表数据，兼容视口懒加载逻辑，对 refreshImmediate 进行拦截 */
    const refreshImmediate = inject('refreshImmediate', '');

    provide('timeRange', viewerTimeRange);
    provide('refreshImmediate', viewerRefreshImmediate);

    watch([refreshImmediate, timeRange, props.panel, props.params], () => {
      hasPanelChange.value = true;
      refreshChart();
    });

    watch(
      () => chartContainerRef.value,
      nVal => {
        if (!nVal) {
          return;
        }
        cleanupObserver();
        setupIntersectionObserver();
      },
      { immediate: true, deep: true }
    );

    onBeforeUnmount(() => {
      cleanupObserver();
    });

    /**
     * @description 初始化 IntersectionObserver 视口监听器实例对象
     */
    function setupIntersectionObserver() {
      if (!intersectionObserverInstance) {
        intersectionObserverInstance = new IntersectionObserver(entries => {
          for (const entry of entries) {
            isInViewport.value = entry.isIntersecting;
            refreshChart();
          }
        });
        if (chartContainerRef?.value) intersectionObserverInstance.observe(chartContainerRef?.value);
      }
    }

    /**
     * @description 清理 IntersectionObserver 视口监听器实例对象
     *
     */
    function cleanupObserver() {
      if (intersectionObserverInstance) {
        intersectionObserverInstance.disconnect();
        intersectionObserverInstance = null;
      }
    }

    /**
     * @description 刷新图表相关配置，重新请求图表数据
     */
    function refreshChart() {
      if (!isInViewport.value || !hasPanelChange.value) return;
      viewerPanel.value = props.panel;
      viewerParams.value = props.params;
      viewerTimeRange.value = get(timeRange);
      viewerRefreshImmediate.value = get(refreshImmediate);
      hasPanelChange.value = false;
    }

    /**
     * @description 数据时间间隔 值改变后回调
     * @param timeRange 缩放后的区域数据时间间隔
     */
    function handleDataZoomChange(timeRange: [number, number]) {
      emit('dataZoomChange', timeRange);
    }

    /**
     * @description 接口请求耗时 值改变后回调
     * @param val 请求耗时
     */
    function handleDurationChange(val: number) {
      emit('durationChange', val);
    }

    return {
      viewerPanel,
      viewerParams,
      handleDataZoomChange,
      handleDurationChange,
    };
  },
  render() {
    return (
      <div
        ref='chartContainerRef'
        class='alarm-lazy-chart'
      >
        <ExploreChart
          formatterData={this.formatterData}
          panel={this.viewerPanel}
          params={this.viewerParams}
          showTitle={this.showTitle}
          onDataZoomChange={this.handleDataZoomChange}
          onDurationChange={this.handleDurationChange}
        />
      </div>
    );
  },
});
