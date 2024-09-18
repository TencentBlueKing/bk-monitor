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
    ref="chartContainer"
    v-bkloading="{ isLoading: isLoading }"
    :class="['monitor-echarts-container', { 'is-fold': isFold }]"
    data-test-id="retrieve_div_generalTrendEcharts"
  >
    <chart-title
      ref="chartTitle"
      :is-empty-chart="isEmptyChart"
      :is-fold="isFold"
      :loading="isLoading || !finishPolling"
      :menu-list="chartOptions.tool.list"
      :title="$t('总趋势')"
      :total-count="totalNumShow"
      @interval-change="handleChangeInterval"
      @menu-click="handleMoreToolItemSet"
      @toggle-expand="toggleExpand"
    >
    </chart-title>
    <MonitorEcharts
      v-if="isRenderChart"
      ref="chartRef"
      v-show="!isFold && !isLoading"
      :get-series-data="getSeriesData"
      :is-fold="isFold"
      :key="chartKey"
      :line-width="2"
      :options="chartOptions"
      :title="$t('总趋势')"
      chart-type="bar"
      @chart-loading="handleChartLoading"
      @dblclick="handleDbClick"
    />
    <div
      v-if="isEmptyChart && !isFold"
      class="chart-empty"
    >
      <svg
        width="256"
        height="256"
        class="icon-chart"
        version="1.1"
        viewBox="0 0 1024 1024"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="M128 160h64v640h704v64H128z"></path>
        <path d="M307.2 636.8l-44.8-44.8 220.8-220.8 137.6 134.4 227.2-227.2 44.8 44.8-272 272-137.6-134.4z"></path>
      </svg>
      <span class="text">{{ $t('暂无数据') }}</span>
    </div>
  </div>
</template>

<script>
  import ChartTitle from '@/components/monitor-echarts/components/chart-title-new.vue';
  import MonitorEcharts from '@/components/monitor-echarts/monitor-echarts-new';
  import { handleTransformToTimestamp } from '@/components/time-range/utils';
  import indexSetSearchMixin from '@/mixins/indexSet-search-mixin';
  import axios from 'axios';
  import { debounce } from 'throttle-debounce';
  // import { nextTick } from 'vue';
  import { mapGetters, mapState } from 'vuex';

  const CancelToken = axios.CancelToken;

  export default {
    components: {
      MonitorEcharts,
      ChartTitle,
    },
    mixins: [indexSetSearchMixin],
    data() {
      return {
        timeRange: [],
        timer: null,
        isFold: false,
        intervalArr: [
          { id: 'auto', name: 'auto' },
          { id: '1m', name: '1 min' },
          { id: '5m', name: '5 min' },
          { id: '1h', name: '1 h' },
          { id: '1d', name: '1d' },
        ],
        chartOptions: {
          tool: {
            list: ['screenshot'],
          },
          animation: false,
          useUTC: false,
          xAxis: {
            axisLine: {
              show: true,
              lineStyle: {
                color: '#666',
              },
            },
            axisLabel: {
              align: 'center',
            },
            axisTick: {
              show: true,
            },
          },
          yAxis: {
            axisLine: {
              show: true,
              lineStyle: {
                color: '#666',
                type: 'dashed',
              },
            },
          },
        },
        isLoading: false,
        isRenderChart: false,
        isEmptyChart: true,
        optionData: [],
        totalCount: 0,
        localAddition: [],
      };
    },
    computed: {
      indexSetItem() {
        return this.$store.state.indexItem.items[0];
      },
      datePickerValue() {
        return this.$store.state.indexItem.datePickerValue;
      },
      chartKey() {
        this.getInterval();
        return this.$store.state.retrieve.chartKey;
      },
      ...mapState({
        searchTotal: 'searchTotal',
      }),
      ...mapGetters({
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
        bkBizId: 'bkBizId',
        retrieveParams: 'retrieveParams',
      }),
      totalNumShow() {
        return !!this.searchTotal ? this.searchTotal : this.totalCount;
      },
      /** 未开启白名单时 是否由前端来统计总数 */
      isFrontStatistics() {
        let isFront = true;
        const { field_analysis_config: fieldAnalysisToggle } = window.FEATURE_TOGGLE;
        switch (fieldAnalysisToggle) {
          case 'on':
            isFront = false;
            break;
          case 'off':
            isFront = true;
            break;
          default:
            const { scenario_id_white_list: scenarioIdWhiteList } = window.FIELD_ANALYSIS_CONFIG;
            const { field_analysis_config: fieldAnalysisConfig } = window.FEATURE_TOGGLE_WHITE_LIST;
            const scenarioID = this.indexSetItem?.scenario_id;
            isFront = !(
              scenarioIdWhiteList?.includes(scenarioID) && fieldAnalysisConfig?.includes(Number(this.bkBizId))
            );
            break;
        }
        return isFront;
      },
      // chartInterval() {
      //   return this.retrieveParams.interval;
      // },
    },
    watch: {
      chartKey: {
        handler() {
          this.handleLogChartCancel();
          this.$refs.chartRef?.handleCloseTimer();
          this.totalCount = 0;
          this.isRenderChart = true;
          this.isLoading = false;
          this.finishPolling = false;
          this.isStart = false;
        },
      },
      totalNumShow(newVal) {
        this.$emit('change-total-count', newVal);
      },
      finishPolling(newVal) {
        this.$emit('change-queue-res', newVal);
      },
      searchTotal(newVal) {
        this.$emit('change-queue-res', !!newVal);
      },
    },
    created() {
      this.handleLogChartCancel = debounce(300, this.logChartCancel);
      this.isFold = JSON.parse(localStorage.getItem('chartIsFold') || 'false');
      this.$nextTick(() => {
        this.$emit('toggle-change', !this.isFold, this.$refs.chartContainer?.offsetHeight);
      });
      if (this.isFold) this.$store.commit('retrieve/updateChartKey');
    },
    mounted() {
      window.bus.$on('openChartLoading', this.openChartLoading);
    },
    beforeUnmount() {
      window.bus.$on('openChartLoading', this.openChartLoading);
    },
    methods: {
      /** 图表请求中断函数 */
      logChartCancel() {},
      /** info数据中断函数 */
      infoTotalCancel() {},
      openChartLoading() {
        this.isLoading = true;
      },
      // 需要更新图表数据
      async getSeriesData(startTime, endTime) {
        if (startTime && endTime) {
          this.timeRange = [startTime, endTime];
          this.finishPolling = false;
          this.isStart = false;
          this.totalCount = 0;
          // 框选时间范围
          this.changeTimeByChart([startTime, endTime]);
          return;
        }

        // 轮循结束
        if (this.finishPolling) return;

        const { startTimeStamp, endTimeStamp } = this.getRealTimeRange();
        // 请求间隔时间
        this.requestInterval = this.isStart
          ? this.requestInterval
          : this.handleRequestSplit(startTimeStamp, endTimeStamp);
        if (!this.isStart) {
          this.isEmptyChart = false;

          // 获取坐标分片间隔
          this.handleIntervalSplit(startTimeStamp, endTimeStamp);

          // 获取分片起止时间
          const curStartTimestamp = this.getIntegerTime(startTimeStamp);
          const curEndTimestamp = this.getIntegerTime(endTimeStamp);

          // 获取分片结果数组
          this.optionData = this.getTimeRange(curStartTimestamp, curEndTimestamp);

          this.pollingEndTime = endTimeStamp;
          this.pollingStartTime = this.pollingEndTime - this.requestInterval;

          if (this.pollingStartTime < startTimeStamp || this.requestInterval === 0) {
            this.pollingStartTime = startTimeStamp;
            // 轮询结束
            this.finishPolling = true;
          }
          this.isStart = true;
        } else {
          this.pollingEndTime = this.pollingStartTime;
          this.pollingStartTime = this.pollingStartTime - this.requestInterval;

          if (this.pollingStartTime < this.retrieveParams.start_time) {
            this.pollingStartTime = this.retrieveParams.start_time;
          }
        }

        if (
          (!this.isUnionSearch && !!this.$route.params?.indexId) ||
          (this.isUnionSearch && this.unionIndexList?.length)
        ) {
          // 从检索切到其他页面时 表格初始化的时候路由中indexID可能拿不到 拿不到 则不请求图表
          const urlStr = this.isUnionSearch ? 'unionSearch/unionDateHistogram' : 'retrieve/getLogChartList';
          const queryData = {
            ...this.retrieveParams,
            time_range: 'customized',
            interval: this.interval,
            // 每次轮循的起始时间
            start_time: this.pollingStartTime,
            end_time: this.pollingEndTime,
          };
          if (this.isUnionSearch) {
            Object.assign(queryData, {
              index_set_ids: this.unionIndexList,
            });
          }
          const res = await this.$http
            .request(
              urlStr,
              {
                params: { index_set_id: this.$route.params.indexId },
                data: queryData,
              },
              {
                cancelToken: new CancelToken(c => {
                  this.logChartCancel = c;
                }),
              },
            )
            .catch(() => false);
          if (res?.data) {
            const originChartData = res?.data?.aggs?.group_by_histogram?.buckets || [];
            const targetArr = originChartData.map(item => {
              this.totalCount = this.totalCount + item.doc_count;
              return [item.doc_count, item.key];
            });

            if (this.pollingStartTime <= this.retrieveParams.start_time) {
              // 轮询结束
              this.finishPolling = true;
            }

            for (let i = 0; i < targetArr.length; i++) {
              for (let j = 0; j < this.optionData.length; j++) {
                if (this.optionData[j][1] === targetArr[i][1] && targetArr[i][0] > 0) {
                  // 根据请求结果匹配对应时间下数量叠加
                  this.optionData[j][0] = this.optionData[j][0] + targetArr[i][0];
                }
              }
            }
          } else {
            this.finishPolling = true;
          }
        } else {
          this.finishPolling = true;
        }
        return [
          {
            datapoints: this.optionData,
            target: '',
            isFinish: this.finishPolling,
          },
        ];
      },
      // 双击回到初始化时间范围
      handleDbClick() {
        const { cacheDatePickerValue } = this.$store.state.retrieve;

        if (this.timeRange.length) {
          this.timeRange = [];
          setTimeout(() => {
            this.$refs.chartRef.handleCloseTimer();
            this.totalCount = 0;
            this.finishPolling = false;
            this.isStart = false;
            this.changeTimeByChart(cacheDatePickerValue);
          }, 100);
        }
      },
      toggleExpand(isFold) {
        this.isFold = isFold;
        localStorage.setItem('chartIsFold', isFold);
        this.$refs.chartRef?.handleToggleExpand(isFold);
        this.$nextTick(() => {
          this.$emit('toggle-change', !isFold, this.$refs.chartContainer?.offsetHeight);
        });
      },
      async changeTimeByChart(datePickerValue) {
        const tempList = handleTransformToTimestamp(datePickerValue);
        this.$store.commit('updateIndexItemParams', {
          datePickerValue,
          start_time: tempList[0],
          end_time: tempList[1],
        });
        this.$store.commit('updateIsSetDefaultTableColumn', false);
        await this.$store.dispatch('requestIndexSetFieldInfo');
        this.$store.dispatch('requestIndexSetQuery');
      },
      handleMoreToolItemSet(event) {
        this.$refs.chartRef.handleMoreToolItemSet(event);
      },
      handleChangeInterval(v) {
        this.chartInterval = v;
      },
      handleChartLoading(isLoading) {
        this.isLoading = isLoading;
      },
    },
  };
</script>

<style scoped lang="scss">
  @import './index.scss';
</style>
