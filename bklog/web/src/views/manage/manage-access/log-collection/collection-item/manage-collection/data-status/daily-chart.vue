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
    v-bkloading="{ isLoading: basicLoading, zIndex: 0 }"
  >
    <div class="chart-header">
      <div class="title">{{ $t('日数据量') }}</div>
      <div class="date-picker">
        <select-date
          :date-picker-value="datePickerValue"
          :time-range.sync="retrieveParams.time_range"
          picker-type="daterange"
          is-daily
          @date-picker-change="fetchChartData"
          @update:date-picker-value="handleDateChange"
        />
        <div
          class="refresh-button"
          @click="fetchChartData"
        >
          <span class="bk-icon icon-refresh"></span>
          <span>{{ $t('刷新') }}</span>
        </div>
      </div>
    </div>
    <div
      ref="chartRef"
      class="chart-canvas-container big-chart"
    ></div>
    <bk-exception
      v-if="isEmpty"
      class="king-exception"
      scene="part"
      type="empty"
    ></bk-exception>
  </div>
</template>

<script>
  import { formatDate } from '@/common/util';
  import dayjs from 'dayjs';
  import * as echarts from 'echarts';
  import { mapGetters } from 'vuex';

  import SelectDate from './select-date';

  export default {
    components: {
      SelectDate,
    },
    data() {
      const currentTime = Date.now();
      const startTime = formatDate(currentTime - 7 * 86400000).slice(0, 10);
      const endTime = formatDate(currentTime).slice(0, 10);

      return {
        isEmpty: false,
        basicLoading: true,
        datePickerValue: [startTime, endTime], // 日期选择器
        retrieveParams: {
          bk_biz_id: this.$store.state.bkBizId,
          keyword: '*',
          time_range: 'custom',
          start_time: startTime, // 时间范围，格式 YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z]
          end_time: endTime,
          host_scopes: {
            modules: [],
            ips: '',
          },
          addition: [],
          begin: 0,
          size: 500,
          interval: '1d',
        },
      };
    },
    computed: {
      ...mapGetters({
        chartSizeNum: 'chartSizeNum',
      }),
      ...mapGetters('collect', ['curCollect']),
    },
    watch: {
      chartSizeNum() {
        this.resizeChart();
      },
    },
    created() {
      this.fetchChartData();
    },
    mounted() {
      let timer = 0;
      this.resizeChart = () => {
        if (!timer) {
          timer = setTimeout(() => {
            timer = 0;
            if (this.instance && !this.instance.isDisposed()) {
              this.instance.resize();
            }
          }, 400);
        }
      };
      window.addEventListener('resize', this.resizeChart);
    },
    beforeUnmount() {
      window.removeEventListener('resize', this.resizeChart);
    },
    methods: {
      // 获取数据
      async fetchChartData() {
        try {
          this.basicLoading = true;
          const res = await this.$http.request('retrieve/getLogChartList', {
            params: { index_set_id: this.curCollect.index_set_id },
            data: Object.assign({}, this.retrieveParams, {
              start_time: `${this.retrieveParams.start_time} 00:00:00`,
              end_time: `${this.retrieveParams.end_time} 23:59:59`,
              addition: this.retrieveParams.addition,
            }),
          });
          const originChartData = res.data.aggs?.group_by_histogram?.buckets || [];
          const chartData = {
            labels: [],
            values: [],
          };
          originChartData.forEach(item => {
            chartData.labels.push(item.key_as_string);
            chartData.values.push(item.doc_count);
          });
          this.updateChart(chartData);
        } catch (e) {
          console.warn(e);
          this.updateChart(null);
        } finally {
          this.basicLoading = false;
        }
      },
      // 初始化图表
      updateChart(chartData) {
        if (!chartData?.values.length) {
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

        this.instance.setOption({
          xAxis: {
            type: 'category',
            data: chartData.labels,
            axisTick: {
              alignWithLabel: true,
            },
            axisLabel: {
              align: 'center',
              formatter(value) {
                return dayjs.tz(value).format('MM-DD');
              },
            },
            axisLine: {
              lineStyle: {
                color: '#DCDEE5',
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
                color: '#DCDEE5',
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
                color: '#339DFF',
              },
            },
          ],
          tooltip: {
            trigger: 'item',
          },
          textStyle: {
            color: '#63656E',
          },
          grid: {
            x: 40,
            y: 10,
            x2: 40,
            y2: 40,
            containLabel: true,
          },
        });
      },

      // 检索参数：日期改变
      handleDateChange(val) {
        this.datePickerValue = val;
        Object.assign(this.retrieveParams, {
          start_time: val[0],
          end_time: val[1],
        });
      },
    },
  };
</script>
