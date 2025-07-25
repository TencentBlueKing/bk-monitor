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
import { type Ref, computed, defineComponent, inject, onMounted, ref, watch } from 'vue';

import dayjs from 'dayjs';
import { alertGraphQuery } from 'monitor-api/modules/alert';
import { transformDataKey } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import FailureChart from './failure-chart';

export const createAutoTimeRange = (
  startTime: number,
  endTime: number,
  interval = 60
): { endTime: string; startTime: string } => {
  const INTERVAL_5 = 5 * interval * 1000;
  const INTERVAL_1440 = 1440 * interval * 1000;
  const INTERVAL_60 = 60 * interval * 1000;
  let newStartTime = startTime * 1000;
  let newEndTime = endTime ? endTime * 1000 : +new Date();
  newEndTime = Math.min(newEndTime + INTERVAL_5, newStartTime + INTERVAL_1440);
  let diff = INTERVAL_1440 - (newEndTime - newStartTime);
  if (diff < INTERVAL_5) {
    diff = INTERVAL_5;
  } else if (diff > INTERVAL_60) {
    diff = INTERVAL_60;
  }
  newStartTime -= diff;
  const result = {
    startTime: dayjs.tz(newStartTime).format('YYYY-MM-DD HH:mm:ss'),
    endTime: dayjs.tz(newEndTime).format('YYYY-MM-DD HH:mm:ss'),
  };
  return result;
};
export default defineComponent({
  name: 'FailureAlarmChart',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    detail: {
      type: Object,
      default: () => ({}),
      required: true,
    },
    groupId: {
      type: String,
      default: '',
    },
  },
  emits: ['successLoad'],
  setup(props, { emit }) {
    const monitorEchartRef = ref(null);
    const { t } = useI18n();
    const dataZoomTimeRange = inject<Ref>('dataZoomTimeRange');
    const bkBizId = ref(null);

    const noGraphCode = ref([3314003, 3314004, 3308005]);
    const chart = ref({
      width: 0,
      colors: ['#FDB980'],
      first: true,
      key: 0,
      renderChart: true,
      selectForFetch: true,
      observeIntersection: true,
      emptyText: t('暂无数据'),
      title: '',
      subtitle: '',
      chartType: 'line',
    });
    const hasTraceSeries = ref(false);
    const zoomFlag = ref(false);
    const traceInfoTimeRange = ref({});
    const errorMsg = ref('');
    watch(
      () => props.detail,
      () => {
        bkBizId.value = props.detail.bk_biz_id;
      },
      { immediate: true }
    );

    watch(
      () => dataZoomTimeRange.value,
      newVal => {
        const { startTime, endTime } = newVal;
        if (zoomFlag.value) {
          zoomFlag.value = false;
          return;
        }
        monitorEchartRef.value?.handleSeriesData(startTime, endTime);
      },
      { immediate: true }
    );

    const chartOption = computed(() => {
      return {
        tool: { list: ['screenshot', 'set', ...(chart.value.chartType === 'bar' ? [] : ['area', 'explore'])] },
      };
    });
    /** 缩放等 */
    const dataZoom = timeRang => {
      zoomFlag.value = true;
      dataZoomTimeRange.value.timeRange = timeRang || [];
    };
    const handleBuildLegend = (alia, compareData = {}) => {
      if (!alia) return alia;
      let alias = alia;
      Object.keys(compareData).forEach(key => {
        const val = compareData[key] || {};
        if (key === 'time_offset') {
          if (val && alias.match(/\$time_offset/g)) {
            const timeMatch = val.match(/(-?\d+)(\w+)/);
            const hasMatch = timeMatch && timeMatch.length > 2;
            alias = alias.replace(
              /\$time_offset/g,
              hasMatch
                ? dayjs.tz().add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
                : val.replace('current', t('当前'))
            );
          }
        } else if (typeof val === 'object') {
          Object.keys(val)
            .sort((a, b) => b.length - a.length)
            .forEach(valKey => {
              const variate = `$${key}_${valKey}`;
              alias = alias.replace(new RegExp(`\\${variate}`, 'g'), val[valKey]);
            });
        } else {
          alias = alias.replace(`$${key}`, val);
        }
      });
      while (/\|\s*\|/g.test(alias)) {
        alias = alias.replace(/\|\s*\|/g, '|');
      }
      return alias.replace(/\|$/g, '');
    };

    const handleGetSeriesData = async (startTime = '', endTime = '', range = false) => {
      const { graph_panel } = props.detail;
      const params: any = {
        bk_biz_id: props.detail.bk_biz_id,
        id: props.detail.id,
      };
      if (range && startTime && endTime) {
        params.start_time = dayjs.tz(startTime).unix();
        params.end_time = dayjs.tz(endTime).unix();
      }
      if (graph_panel) {
        const [{ data: queryConfig, alias }] = graph_panel.targets;
        chart.value.title = graph_panel.title || '';
        chart.value.subtitle = graph_panel.subTitle || '';
        chart.value.chartType = graph_panel.type === 'bar' ? 'bar' : 'line';
        if (queryConfig.extendMetricFields?.some(item => item.includes('is_anomaly'))) {
          queryConfig.function = { ...queryConfig.function, max_point_number: 0 };
        }
        const chartQueryConfig = transformDataKey(queryConfig, true);
        errorMsg.value = '';
        const res = await alertGraphQuery(
          { ...chartQueryConfig, ...params },
          { needRes: true, needMessage: false }
        ).catch(err => {
          if (err && noGraphCode.value.includes(err.code)) {
            chart.value.selectForFetch = false;
            chart.value.observeIntersection = false;
            chart.value.emptyText = err.message;
          }
          errorMsg.value = err.message || err.msg;
        });
        chart.value.first = false;
        const { severity } = props.detail;
        const series = res?.data?.series || [];
        const traceSeries = res?.data?.trace_series || [];
        hasTraceSeries.value = !!traceSeries.length && chart.value.chartType === 'line';
        // const algorithmValue = algorithmList?.find(item => item?.level === level)?.algorithmConfig?.sensitivityValue
        // 异常检测图表转换

        if (chartQueryConfig?.extend_fields?.intelligent_detect?.result_table_id && series.length) {
          const chartSeries = series.find(
            item => item?.metric?.metric_field === 'value' && item?.time_offset === 'current'
          );
          if (!chartSeries) return [];
          // 智能异常检测算法 边界画图设置
          const { dimensions } = chartSeries;
          const coverList = [];
          const algorithm2Level = {
            1: 15,
            2: 14,
            3: 13,
          };
          const upBoundary =
            series
              ?.find(
                item =>
                  item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                  item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                  item.metric.metric_field === 'upper_bound'
              )
              ?.datapoints?.map(item => [item[1], item[0]]) || [];
          const lowBoundary =
            series
              ?.find(
                item =>
                  item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                  item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                  item.metric.metric_field === 'lower_bound'
              )
              ?.datapoints.map(item => [item[1], item[0]]) || [];
          const coverData = series?.find(
            item =>
              item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
              item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
              item.metric.metric_field === 'is_anomaly'
          )?.datapoints;
          if (coverData?.length) {
            coverList.push({
              data: coverData.map((item, index) => [
                chartSeries?.datapoints[index][1],
                item[0] > 0 ? chartSeries?.datapoints[index][0] : null,
              ]),
              color: '#ea3636',
              z: algorithm2Level[severity] + 10,
              name: `${severity}-cover`,
            });
          }
          const allData = series
            .filter(item => item?.metric?.metric_field === 'value')
            .map(({ target, datapoints, ...setData }) => {
              const item = {
                datapoints,
                ...setData,
                target:
                  handleBuildLegend(alias, {
                    ...setData,
                    tag: setData.dimensions,
                    metric: setData.metric,
                    // formula: params.method,
                    ...params,
                  }) || target,
              };
              if (setData.time_offset === 'current') {
                return {
                  ...item,
                  boundary: [
                    {
                      upBoundary,
                      lowBoundary,
                      color: '#e6e6e6',
                      stack: `${severity}-boundary-${item.target}`,
                      z: algorithm2Level[severity],
                    },
                  ],
                  coverSeries: coverList.map(set => ({ ...set, name: `${set.name}-${item.target}` })),
                };
              }
              return item;
            });

          return allData;
        }
        const result = series.map(({ target, datapoints, ...setData }) => ({
          datapoints,
          ...setData,
          target:
            handleBuildLegend(alias, {
              ...setData,
              tag: setData.dimensions,
              metric: setData.metric,
              // formula: params.method,
              ...params,
            }) || target,
        }));
        if (hasTraceSeries.value) {
          const interval = props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
          const { startTime, endTime } = createAutoTimeRange(props.detail.begin_time, props.detail.end_time, interval);
          traceInfoTimeRange.value = {
            start_time: dayjs.tz(startTime).unix(),
            end_time: dayjs.tz(endTime).unix(),
          };
          /* 需要降低trace散点图的密度 */
          const allMaxMinTimeStamp = [];
          const viewWidth = document.querySelector('.series-view-container').clientWidth;
          series.forEach(s => {
            if (s.datapoints.length) {
              allMaxMinTimeStamp.push(s.datapoints[0][1]);
              allMaxMinTimeStamp.push(s.datapoints[s.datapoints.length - 1][1]);
            }
          });
          traceSeries.forEach(t => {
            const timeIndex = t.columns.findIndex(name => name === 'bk_trace_timestamp');
            const valueIndex = t.columns.findIndex(name => name === 'bk_trace_value');
            /* 过滤时间戳与值为空的数据 */
            const dataPoints = t.data_points.filter(item => !!item[timeIndex] && typeof item[valueIndex] === 'number');
            if (dataPoints.length) {
              allMaxMinTimeStamp.push(dataPoints[0][timeIndex]);
              allMaxMinTimeStamp.push(dataPoints[dataPoints.length - 1][timeIndex]);
            }
          });
          const allMaxMinTimeStampSort = allMaxMinTimeStamp.sort((a, b) => a - b);
          const minTimeStamp = allMaxMinTimeStampSort[0];
          const maxTimeStamp = allMaxMinTimeStampSort[allMaxMinTimeStampSort.length - 1];
          /* 一个像素点占用多少ms */
          const poinitMs = (maxTimeStamp - minTimeStamp) / viewWidth;
          /* 一个散点占用的ms */
          const traceMaxPointMs = poinitMs * 8;
          const traceReduceDensityFn = (data: any[][], timeIndex: number, valueIndex: number) => {
            const temp = [];
            data.forEach(d => {
              const tempStamp = d[timeIndex];
              const tempValue = d[valueIndex];
              if (temp.length) {
                if (
                  tempStamp - temp[temp.length - 1][timeIndex] > traceMaxPointMs ||
                  (tempStamp === temp[temp.length - 1][timeIndex] && tempValue !== temp[temp.length - 1][valueIndex])
                ) {
                  temp.push(d);
                }
              } else {
                temp.push(d);
              }
            });
            return temp;
          };
          traceSeries.forEach(item => {
            const valueIndex = item.columns.findIndex(name => name === 'bk_trace_value');
            const timeIndex = item.columns.findIndex(name => name === 'bk_trace_timestamp');
            /* 过滤时间戳与值为空的数据 */
            const dataPointsFilter = item.data_points.filter(
              item => !!item[timeIndex] && typeof item[valueIndex] === 'number'
            );
            const datapoints = traceReduceDensityFn(dataPointsFilter, timeIndex, valueIndex);
            result.push({
              ...item,
              data_points: datapoints,
              datapoints: datapoints.map(d => [d[valueIndex], d[timeIndex]]),
              type: 'scatter',
            });
          });
        }
        return result;
      }
      return [];
    };
    /** 跳转数据检索 */
    const handleToDataRetrieval = () => {
      const targets = props.detail.graph_panel?.targets;
      if (targets) {
        const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
          props.detail.bk_biz_id
        }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`;
        window.open(url, '__blank');
      }
    };
    onMounted(() => {
      handleGetSeriesData();
    });
    const handleSuccessLoad = () => {
      emit('successLoad');
    };
    return {
      t,
      chartOption,
      errorMsg,
      chart,
      traceInfoTimeRange,
      hasTraceSeries,
      dataZoom,
      handleGetSeriesData,
      handleToDataRetrieval,
      monitorEchartRef,
      handleSuccessLoad,
    };
  },
  render() {
    return (
      <FailureChart
        key={this.$props.detail?.id}
        ref='monitorEchartRef'
        height={220}
        chart-type={this.chart.chartType}
        curBizId={this.$props.detail?.bk_biz_id}
        detail={this.$props.detail}
        empty-text={this.errorMsg?.length ? this.t('查询数据错误') : this.t('无数据')}
        errorMsg={this.errorMsg}
        getSeriesData={this.handleGetSeriesData}
        groupId={this.$props.groupId}
        hasTraceInfo={this.hasTraceSeries}
        options={this.chartOption}
        subtitle={this.chart.subtitle}
        title={this.chart.title}
        traceInfoTimeRange={this.traceInfoTimeRange}
        onData-zoom={this.dataZoom}
        onExport-data-retrieval={this.handleToDataRetrieval}
        // onExportSataRetrieval={this.handleToDataRetrieval}
        onSuccessLoad={this.handleSuccessLoad}
      />
    );
  },
});
