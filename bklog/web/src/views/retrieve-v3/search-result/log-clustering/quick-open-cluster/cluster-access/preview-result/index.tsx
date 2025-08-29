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

import { defineComponent, ref, watch } from 'vue';
import dayjs from 'dayjs';
import useLocale from '@/hooks/use-locale';
import * as echarts from 'echarts';
import $http from '@/api';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isLeapYear from 'dayjs/plugin/isLeapYear';
import type { Histogram, LogSearchResult } from '@/services/retrieve';
import { type IResponseData } from '@/services/type';

import './index.scss';

export default defineComponent({
  name: 'PreviewResult',
  props: {
    indexSetId: {
      type: String,
      default: '',
    },
    ruleList: {
      type: Array<any>,
      default: () => [],
    },
  },
  setup(props, { emit, expose }) {
    dayjs.extend(weekOfYear);
    dayjs.extend(isLeapYear);
    const { t } = useLocale();

    const chartRef = ref(null);
    const chartInstance = ref();
    const showPreViewContent = ref(false);
    const showWarnTip = ref(false);
    const chartLoading = ref(false);
    const logLoading = ref(false);
    const logDataList = ref<string[]>([]);
    // 都为空不允许提交
    const isRecordEmpty = ref(false);
    const localBuckets = ref<Histogram['aggs']['group_by_histogram']['buckets']>([]);

    watch(showPreViewContent, () => {
      if (showPreViewContent.value) {
        initChart();
      }
    });

    // 获取最近一周的起始和结束时间戳 { start: 第一天00:00, end: 第七天23:59 }
    const getCurrentWeekRange = () => {
      const start = dayjs().subtract(7, 'day').startOf('day').valueOf();
      const end = dayjs().subtract(1, 'day').endOf('day').valueOf();
      return {
        start,
        end,
      };
    };

    const initChart = () => {
      setTimeout(() => {
        if (!chartRef.value) {
          return;
        }
        chartInstance.value?.dispose();
        chartInstance.value = echarts.init(chartRef.value);
        updateChart(localBuckets.value);
      });
    };

    const getLast7Days = (format = 'M-D') => {
      return Array.from({ length: 7 }, (_, i) =>
        dayjs()
          .subtract(i + 1, 'day')
          .format(format),
      ).reverse();
    };

    const updateChart = (buckets: Histogram['aggs']['group_by_histogram']['buckets']) => {
      const isEmpty = buckets.length === 0;
      const xAxisData = isEmpty ? getLast7Days() : buckets.map(item => item.key_as_string.split(' ')[0]);
      const yAxisData = isEmpty ? Array(7).fill(0) : buckets.map(item => item.doc_count);

      chartInstance.value.setOption({
        animation: false, // 关闭所有动画
        grid: {
          top: 12,
          right: 0,
          bottom: 0,
          left: 0,
          containLabel: true, // 确保坐标轴标签不被裁剪（标签计入图表区域）
        },
        title: {},
        tooltip: {},
        legend: {},
        xAxis: {
          data: xAxisData,
          axisTick: { show: false },
          axisLabel: {
            textStyle: {
              color: '#979BA5',
            },
          },
          axisLine: {
            lineStyle: {
              color: '#F0F1F5',
              width: 1,
            },
          },
        },
        yAxis: {
          axisLabel: {
            textStyle: {
              color: '#979BA5',
            },
          },
          splitLine: {
            show: true,
            lineStyle: {
              color: '#F0F1F5',
              width: 1,
              type: 'line',
            },
          },
          interval: isEmpty ? 1000 : null,
          min: isEmpty ? 0 : null, // 全零时固定为 0
          max: isEmpty ? 3000 : null, // 全零时设置上限
        },
        series: [
          {
            type: 'bar',
            barWidth: 32,
            itemStyle: {
              color: '#A3B1CC',
            },
            data: yAxisData,
          },
        ],
      });
    };

    const generateQueryData = () => {
      const { start, end } = getCurrentWeekRange();
      const addition = props.ruleList.map(item => ({
        field: item.field_name,
        operator: item.op,
        value: item.value,
        condition: item.logic_operator,
      }));

      return {
        keyword: '*',
        start_time: start,
        end_time: end,
        addition,
        interval: '1d',
      };
    };

    const fetchChartData = async () => {
      try {
        chartLoading.value = true;
        // 用传聚类字段
        const res = (await $http.request('retrieve/getLogChartList', {
          params: { index_set_id: props.indexSetId },
          data: generateQueryData(),
        })) as IResponseData<Histogram>;
        localBuckets.value = res.data.aggs?.group_by_histogram?.buckets || [];
        updateChart(localBuckets.value);
      } catch (e) {
        console.error(e);
      } finally {
        chartLoading.value = false;
      }
    };

    const fetchLogList = async () => {
      try {
        logLoading.value = true;
        const res = (await $http.request('retrieve/getLogTableList', {
          params: { index_set_id: props.indexSetId },
          data: generateQueryData(),
        })) as IResponseData<LogSearchResult>;
        logDataList.value = res.data.list.map(item => item.log);
      } catch (e) {
        console.error(e);
      } finally {
        logLoading.value = false;
      }
    };

    const handleClickPreview = () => {
      emit('preview-success');
      showWarnTip.value = false;
      showPreViewContent.value = true;
      initChart();
      Promise.all([fetchChartData(), fetchLogList()]).then(() => {
        if (!localBuckets.value.length && !logDataList.value.length) {
          isRecordEmpty.value = true;
          emit('record-empty', true);
        } else {
          isRecordEmpty.value = false;
          emit('record-empty', false);
        }
      });
    };

    const setWarn = (isWarn: boolean) => {
      if (!chartInstance.value) {
        return;
      }
      showWarnTip.value = isWarn;
      initChart();
    };

    expose({ setWarn });

    return () => (
      <div class='preview-result-main'>
        {showWarnTip.value && <div class='warn-mask'></div>}
        <div class='operate-main'>
          <bk-button
            theme='primary'
            style='width: 88px'
            outline
            on-click={handleClickPreview}
          >
            {t('预览')}
          </bk-button>
          {showPreViewContent.value && (
            <div class='preview-tip'>
              {showWarnTip.value ? (
                <log-icon
                  class='warn-icon'
                  type='circle-alert-filled'
                />
              ) : isRecordEmpty.value ? (
                <log-icon
                  class='error-icon'
                  type='circle-alert-filled'
                />
              ) : (
                <log-icon
                  class='check-icon'
                  type='circle-correct-filled'
                />
              )}
              <span class='tip-text'>
                {showWarnTip.value
                  ? t('配置有调整，请重新预览')
                  : isRecordEmpty.value
                    ? t('预览结果无数据，无法提交')
                    : t('预览结果如下')}
              </span>
            </div>
          )}
        </div>
        {showPreViewContent.value && (
          <div class='preview-content'>
            <div class='item-title'>{t('最近 1 周日志趋势')}</div>
            <div v-bkloading={{ isLoading: chartLoading.value }}>
              <div
                class='chart-main'
                ref={chartRef}
              ></div>
            </div>
            <div class='item-title'>{t('最近 10 条日志样例')}</div>
            <div
              class='log-demo-main'
              style={{ borderBottom: logDataList.value.length > 0 ? 'solid 1px #dcdee5' : 'none' }}
              v-bkloading={{ isLoading: logLoading.value }}
            >
              {logDataList.value.length > 0 ? (
                logDataList.value.map((item, index) => (
                  <div class='row-data'>
                    <div class='count-num'>{index + 1}</div>
                    <div class='log-content'>{item}</div>
                  </div>
                ))
              ) : (
                <bk-exception
                  type='empty'
                  scene='part'
                  class='empty-status'
                >
                  <span>{t('暂无数据')}</span>
                </bk-exception>
              )}
            </div>
          </div>
        )}
      </div>
    );
  },
});
