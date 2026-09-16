/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { type PropType, defineComponent, nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';
import { MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from 'monitor-ui/chart-plugins/utils/axis';

import BaseEchart from '@/plugins/base-echart';

import type { IChatSeries } from './chat-result-typing';
import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './chat-result-chart.scss';

/** 会话气泡里只放小图，高度固定，宽度跟着面板走 */
const CHART_HEIGHT = 120;

export default defineComponent({
  name: 'ChatResultChart',
  props: {
    series: {
      type: Array as PropType<IChatSeries[]>,
      default: () => [],
    },
  },
  setup(props) {
    const chartContainer = shallowRef<HTMLDivElement>();
    const baseEchartRef = shallowRef<{ resize?: () => void }>();
    const width = shallowRef(352);
    const options = shallowRef<MonitorEchartOptions>({});

    let observer: ResizeObserver | null = null;

    const setOptions = () => {
      const { maxSeriesCount, maxXInterval } = getSeriesMaxInterval(props.series);
      const xInterval = getTimeSeriesXInterval(maxXInterval, width.value, maxSeriesCount);
      options.value = deepmerge(
        deepClone(MONITOR_LINE_OPTIONS),
        {
          grid: { top: 12, right: 8, bottom: 20, left: 40 },
          toolbox: [],
          xAxis: {
            type: 'time',
            splitNumber: 3,
            axisLabel: {
              formatter: (value: number) => dayjs.tz(value).format('HH:mm'),
              hideOverlap: true,
            },
            ...xInterval,
          },
          yAxis: {
            splitNumber: 3,
            splitLine: {
              lineStyle: { color: '#F0F1F5', type: 'solid' },
            },
          },
          series: props.series.map(item => ({
            type: 'line' as const,
            name: item.name,
            // 存的是 [value, timestamp]，echarts 要 [timestamp, value]
            data: item.datapoints.map(point => [point[1], point[0]]),
            symbol: 'none',
            z: 6,
            color: item.color,
            lineStyle: { color: item.color, width: 1.5 },
          })),
        },
        { arrayMerge: (_, newArr) => newArr }
      );
    };

    watch(() => props.series, setOptions, { immediate: true });

    onMounted(async () => {
      if (!chartContainer.value) return;
      observer = new ResizeObserver(entries => {
        const nextWidth = entries[0]?.contentRect?.width;
        if (!nextWidth || Math.abs(nextWidth - width.value) < 1) return;
        width.value = nextWidth;
        setOptions();
        baseEchartRef.value?.resize?.();
      });
      observer.observe(chartContainer.value);
      width.value = chartContainer.value.getBoundingClientRect().width || width.value;
      setOptions();
      // echarts 初始化时容器高度还没算出来，布局稳定后补一次 resize，否则画布只有 1px 高
      await nextTick();
      baseEchartRef.value?.resize?.();
    });

    onBeforeUnmount(() => {
      observer?.disconnect();
      observer = null;
    });

    return {
      chartContainer,
      baseEchartRef,
      width,
      options,
    };
  },
  render() {
    return (
      <div
        ref='chartContainer'
        class='chat-result-chart'
      >
        {/* BaseEchart 自身只有 min-height，实际高度靠这层父容器撑 */}
        <div
          style={{ height: `${CHART_HEIGHT}px` }}
          class='chat-result-chart-content'
        >
          <BaseEchart
            ref='baseEchartRef'
            width={this.width}
            height={CHART_HEIGHT}
            options={this.options}
          />
        </div>
        <div class='chat-result-chart-legend'>
          {this.series.map(item => (
            <span
              key={item.name}
              class='legend-item'
            >
              <span
                style={{ background: item.color }}
                class='legend-dot'
              />
              {item.name}
            </span>
          ))}
        </div>
      </div>
    );
  },
});
