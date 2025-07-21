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
    v-bkloading="{ isLoading: false }"
    :class="['monitor-echarts-container', { 'is-fold': isFold }]"
    data-test-id="retrieve_div_generalTrendEcharts"
  >
    <chart-title
      ref="chartTitle"
      :is-fold="isFold"
      :loading="isLoading || !finishPolling"
      :menu-list="chartOptions.tool.list"
      :title="$t('总趋势')"
      @menu-click="handleMoreToolItemSet"
      @toggle-expand="toggleExpand"
    >
    </chart-title>
    <MonitorEcharts
      v-if="isRenderChart"
      ref="chartRef"
      v-show="!isFold && !isLoading"
      style="padding: 0 24px"
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
    <div
      v-if="!isEmptyChart && !isFold"
      v-en-style="'left: 110px'"
      class="converge-cycle-old"
    >
      <span>{{ $t('汇聚周期') }}</span>
      <bk-select
        style="width: 80px"
        ext-cls="select-custom"
        v-model="chartInterval"
        :clearable="false"
        behavior="simplicity"
        data-test-id="generalTrendEcharts_div_selectCycle"
        size="small"
        @change="handleIntervalChange"
      >
        <bk-option
          v-for="option in intervalArr"
          :id="option.id"
          :key="option.id"
          :name="option.name"
        >
        </bk-option>
      </bk-select>
    </div>
  </div>
</template>

<script>
import ChartTitle from '@/components/monitor-echarts/components/chart-title-old.vue';
import MonitorEcharts from '@/components/monitor-echarts/monitor-echarts-new';
import indexSetSearchMixin from '@/mixins/indexSet-search-mixin';
import axios from 'axios';
import { debounce } from 'throttle-debounce';
import { mapGetters } from 'vuex';

const CancelToken = axios.CancelToken;

export default {
  components: {
    MonitorEcharts,
    ChartTitle,
  },
  mixins: [indexSetSearchMixin],
  props: {
    retrieveParams: {
      type: Object,
      required: true,
    },
    datePickerValue: {
      type: Array,
      default: () => [],
    },
    indexSetItem: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      timeRange: [],
      timer: null,
      isFold: localStorage.getItem('chartIsFold') === 'true',
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
      infoTotal: 0,
      infoTotalNumLoading: false,
      infoTotalNumError: false,
    };
  },
  computed: {
    chartKey() {
      this.getInterval();
      return this.$store.state.retrieve.chartKey;
    },
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch',
      bkBizId: 'bkBizId',
    }),
    totalNumShow() {
      if (this.infoTotal > 0) {
        return this.infoTotal;
      }
      return this.totalCount;
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
          isFront = !(scenarioIdWhiteList?.includes(scenarioID) && fieldAnalysisConfig?.includes(Number(this.bkBizId)));
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
        this.localAddition = this.retrieveParams.addition;
        this.$refs.chartRef?.handleCloseTimer();
        !this.isFrontStatistics && this.getInfoTotalNum();
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
    'retrieveParams.interval'(newVal) {
      this.chartInterval = newVal;
    },
  },
  created() {
    this.handleLogChartCancel = debounce(300, this.logChartCancel);
  },
  mounted() {
    window.bus.$on('openChartLoading', this.openChartLoading);
    this.chartInterval = this.retrieveParams.interval;
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
    // 汇聚周期改变
    handleIntervalChange() {
      // this.getInterval();
      // this.finishPolling = true;
      // this.$refs.chartRef.handleCloseTimer();
      // this.totalCount = 0;
      // setTimeout(() => {
      //   this.finishPolling = false;
      //   this.isStart = false;
      //   this.$refs.chartRef.handleChangeInterval();
      // }, 500);
      this.$store.commit('retrieve/updateChartKey');
    },
    // 需要更新图表数据
    async getSeriesData(startTime, endTime) {
      if (startTime && endTime) {
        this.timeRange = [startTime, endTime];
        this.finishPolling = false;
        this.isStart = false;
        !this.isFrontStatistics && this.getInfoTotalNum();
        this.totalCount = 0;
        // 框选时间范围
        window.bus.$emit('changeTimeByChart', [startTime, endTime], 'customized');
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
          addition: this.localAddition,
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
            }
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
      const { cacheDatePickerValue, cacheTimeRange } = this.$store.state.retrieve;

      if (this.timeRange.length) {
        this.timeRange = [];
        setTimeout(() => {
          window.bus.$emit('changeTimeByChart', cacheDatePickerValue, cacheTimeRange);
          this.finishPolling = true;
          this.totalCount = 0;
          !this.isFrontStatistics && this.getInfoTotalNum();
          this.$refs.chartRef.handleCloseTimer();
          setTimeout(() => {
            this.finishPolling = false;
            this.isStart = false;
            this.$store.commit('retrieve/updateChartKey');
          }, 100);
        }, 100);
      }
    },
    toggleExpand(isFold) {
      this.isFold = isFold;
      localStorage.setItem('chartIsFold', isFold);
      this.$refs.chartRef.handleToggleExpand(isFold);
    },
    handleMoreToolItemSet(event) {
      this.$refs.chartRef.handleMoreToolItemSet(event);
    },
    handleChartLoading(isLoading) {
      this.isLoading = isLoading;
    },
    getInfoTotalNum() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.infoTotalNumLoading = true;
        this.infoTotalNumError = false;
        this.infoTotal = 0;
        this.$http
          .request(
            'retrieve/fieldStatisticsTotal',
            {
              data: {
                ...this.retrieveParams,
                index_set_ids: this.isUnionSearch ? this.unionIndexList : [this.$route.params.indexId],
              },
            },
            {
              cancelToken: new CancelToken(c => {
                this.infoTotalCancel = c;
              }),
            }
          )
          .then(res => {
            const { data, code } = res;
            if (code === 0) this.infoTotal = data.total_count;
          })
          .catch(() => {
            this.infoTotalNumError = true;
          })
          .finally(() => {
            this.infoTotalNumLoading = false;
          });
      }, 0);
    },
  },
};
</script>

<style lang="scss">
  .monitor-echarts-container {
    position: relative;
    // height: 160px;
    overflow: hidden;
    background-color: #fff;

    &.is-fold {
      height: 60px;
    }

    :deep(.echart-legend) {
      display: flex;
      justify-content: center;
    }

    .converge-cycle-old {
      position: absolute;
      top: 17px;
      left: 80px;
      display: inline-block;
      margin-left: 24px;
      font-size: 12px;
      color: #4d4f56;

      .select-custom {
        display: inline-block;
        margin-left: 5px;
        vertical-align: middle;
      }
    }

    .chart-empty {
      position: absolute;
      top: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      background: #fff;

      .icon-chart {
        width: 38px;
        height: 38px;
        fill: #dcdee6;
      }

      .text {
        font-size: 14px;
        color: #979ba5;
      }
    }

    .title-wrapper {
      padding: 14px 24px 0;
    }

    .monitor-echart-wrap {
      // height: 116px;
      padding-top: 0;
      padding-bottom: 0;

      .chart-wrapper {
        /* stylelint-disable-next-line declaration-no-important */
        min-height: 116px !important;

        /* stylelint-disable-next-line declaration-no-important */
        max-height: 116px !important;
      }
    }
  }
</style>
