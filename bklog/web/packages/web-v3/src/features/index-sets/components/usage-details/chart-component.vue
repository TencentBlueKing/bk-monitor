<!--
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
-->

<template>
  <div
    class="chart-container"
  >
    <div class="chart-header">
      <div class="title">{{ type }}</div>
      <t-button :variant="(true) ? 'text' : ('base')"
        v-if="type === $t('检索耗时统计') && retrieveTimeGuide"
        style="font-size: var(--bklog-font-body, 12px)"
        
        @click="goToGuide"
      >
        {{ $t('耗时优化指引 >') }}
      </t-button>
    </div>
    <div class="chart-canvas-container collection-detail-chart-body">
      <div
        ref="chartRef"
        class="chart-canvas"
        :style="{ visibility: loading || failed || isEmpty ? 'hidden' : 'visible' }"
      ></div>
      <div v-if="loading" class="collection-detail-chart-state is-skeleton" role="status" :aria-label="$t('加载中')">
        <div v-if="skeletonType === 'pie'" class="usage-chart-pie-skeleton" aria-hidden="true" />
        <chart-skeleton v-else :type="skeletonType" :height="168" />
      </div>
      <div
        v-else-if="failed || isEmpty"
        class="collection-detail-chart-state"
      >
        <empty-status :empty-type="failed ? '500' : 'empty'" @operation="$emit('retry')" />
      </div>
    </div>
  </div>
</template>

<script>
import ChartSkeleton from '@/app/skeleton/chart-skeleton';
import '@/features/index-sets/log-collection/collection-item/manage-collection/detail-states.scss';
import { observeChartColors, readChartColors } from '@/features/index-sets/log-collection/collection-item/manage-collection/data-status/chart-colors';
  import EmptyStatus from '@/shared/ui/empty-status/index';
  import i18n from '@/platform/i18n/i18n';
  import * as echarts from 'echarts';

  const defaultOption = {
    grid: {
      x: 20,
      y: 10,
      x2: 20,
      y2: 30,
      left: '2%', // 与容器左侧的距离
      containLabel: true,
    },
  };

  export default {
    components: {
      ChartSkeleton,
      EmptyStatus,
    },
    emits: ['retry'],
    props: {
      failed: Boolean,
      skeletonType: {
        type: String,
        default: 'line',
        validator: value => ['line', 'bar', 'pie'].includes(value),
      },
      type: {
        type: String,
        required: true,
        validator: val => {
          return [i18n.t('使用次数趋势'), i18n.t('用户使用频次'), i18n.t('检索耗时统计')].includes(val);
        },
      },
      loading: {
        type: Boolean,
        default: true,
      },
      chartData: {
        type: Object,
        default: null,
      },
    },
    data() {
      return {
        isEmpty: false,
        retrieveTimeGuide: window.RETRIEVE_TIME_OPTIMIZE_GUIDE_URL,
      };
    },
    watch: {
      chartData: {
        handler(val) {
          this.updateChart(val);
        },
        immediate: true,
      },
    },
    mounted() {
      const canvas = this.$refs.chartRef;
      let frame;
      this.resizeChart = () => {
        if (frame !== undefined) return;
        frame = requestAnimationFrame(() => {
          frame = undefined;
          if (canvas.clientWidth && canvas.clientHeight && this.instance && !this.instance.isDisposed()) {
            this.instance.resize();
          }
        });
      };

      const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(this.resizeChart);
      if (observer) observer.observe(canvas);
      else window.addEventListener('resize', this.resizeChart);
      const stopChartColors = observeChartColors(canvas, () => this.instance, this.skeletonType !== 'pie');
      this.stopChartResize = () => {
        stopChartColors();
        observer?.disconnect();
        window.removeEventListener('resize', this.resizeChart);
        if (frame !== undefined) cancelAnimationFrame(frame);
      };
    },
    beforeUnmount() {
      this.instance?.dispose();
      this.stopChartResize?.();
    },
    methods: {
      updateChart(chartData) {
        if (!chartData?.values?.length || chartData.values.every(item => item === 0)) {
          if (this.instance && !this.instance.isDisposed()) {
            this.instance.dispose();
          }
          this.isEmpty = true;
          return;
        }

        this.isEmpty = false;
        if (!this.instance || this.instance.isDisposed()) {
          this.instance = echarts.init(this.$refs.chartRef);
        }
        switch (this.type) {
          case this.$t('使用次数趋势'):
            this.setLineChart({
              labels: chartData.labels.map(item => {
                const date = new Date(item);
                const mm = `0${date.getMonth() + 1}`.slice(-2);
                const dd = `0${date.getDate()}`.slice(-2);
                return mm + dd;
              }),
              values: chartData.values,
            });
            break;
          case this.$t('用户使用频次'):
            this.setBarChart(chartData);
            break;
          case this.$t('检索耗时统计'):
            this.setPieChart(chartData);
        }
      },
      // 折线图 使用次数趋势
      setLineChart(chartData) {
        const themeColors = readChartColors(this.$refs.chartRef);
        this.instance.setOption(
          Object.assign({}, defaultOption, {
            textStyle: { color: themeColors.text },
            xAxis: {
              data: chartData.labels,
              axisTick: {
                alignWithLabel: true,
              },
              axisLabel: {
                align: 'center',
              },
              axisLine: {
                lineStyle: {
                  color: themeColors.axis,
                },
              },
            },
            yAxis: {
              type: 'value',
              axisTick: {
                show: false,
              },
              axisLine: {
                show: false,
              },
              splitLine: {
                lineStyle: {
                  color: themeColors.axis,
                  type: 'dashed',
                },
              },
            },
            series: [
              {
                data: chartData.values,
                type: 'line',
                symbol: 'none',
                itemStyle: {
                  color: themeColors.series,
                },
              },
            ],
            tooltip: {
              ...themeColors.tooltip,
              trigger: 'axis',
              axisPointer: {
                type: 'line',
                axis: 'auto',
              },
            },
          }),
        );
      },
      // 柱状图 用户使用频次
      setBarChart(chartData) {
        const themeColors = readChartColors(this.$refs.chartRef);
        this.instance.setOption(
          Object.assign({}, defaultOption, {
            textStyle: { color: themeColors.text },
            xAxis: {
              type: 'category',
              data: chartData.labels,
              axisTick: {
                alignWithLabel: true,
              },
              axisLabel: {
                align: 'center',
              },
              axisLine: {
                lineStyle: {
                  color: themeColors.axis,
                },
              },
            },
            yAxis: {
              type: 'value',
              axisTick: {
                show: false,
              },
              axisLine: {
                show: false,
              },
              splitLine: {
                lineStyle: {
                  color: themeColors.axis,
                  type: 'dashed',
                },
              },
            },
            series: [
              {
                data: chartData.values,
                type: 'bar',
                barMaxWidth: 24,
                itemStyle: {
                  color: themeColors.series,
                },
              },
            ],
            tooltip: {
              ...themeColors.tooltip,
              trigger: 'item',
            },
          }),
        );
      },
      // 饼图，检索耗时统计
      setPieChart(chartData) {
        const themeColors = readChartColors(this.$refs.chartRef);
        const colors = ['#B568FF', '#3BCE95', '#339DFF'];
        const newChartData = chartData.values
          .map((value, index) => ({
            value,
            name: chartData.labels[index],
            itemStyle: {
              color: colors[index],
            },
          }))
          .filter(item => Boolean(item.value));
        this.instance.setOption(
          Object.assign({}, defaultOption, {
            textStyle: { color: themeColors.text },
            tooltip: {
              ...themeColors.tooltip,
              trigger: 'item',
              formatter: '{b} <br/>{a} {d}%',
            },
            legend: {
              textStyle: { color: themeColors.text },
              orient: 'vertical',
              left: 'left',
              top: 'middle',
            },
            series: [
              {
                name: this.$t('占比'),
                type: 'pie',
                radius: '50%',
                data: newChartData,
                emphasis: {
                  itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.5)',
                  },
                },
              },
            ],
          }),
        );
      },
      goToGuide() {
        window.open(this.retrieveTimeGuide, '_blank', 'noopener,noreferrer');
      },
    },
  };
</script>

<style lang="scss" scoped>
  .chart-canvas-container {
    position: relative;

    .chart-canvas {
      width: 100%;
      height: 100%;
    }


  }
</style>
