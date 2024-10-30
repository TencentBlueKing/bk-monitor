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
import { type PropType, defineComponent, watch } from 'vue';
import { ref, reactive, computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button } from 'bkui-vue';

import ProfilingGraph from '../../../plugins/charts/profiling-graph/profiling-graph';
import ComparisonChart from './comparison-chart';
import TrendChart from './trend-chart';

import type { IQueryParams } from '../../../typings/trace';
import type { DataTypeItem, RetrievalFormData } from '../typings/profiling-retrieval';

import './profiling-retrieval-view.scss';

export default defineComponent({
  name: 'ProfilingRetrievalView',
  props: {
    dataType: {
      type: String,
      default: 'cpu',
    },
    dataTypeList: {
      type: Array as PropType<DataTypeItem[]>,
      default: () => [],
    },
    formData: {
      type: Object as PropType<RetrievalFormData>,
      required: true,
    },
    queryParams: {
      type: Object as PropType<IQueryParams>,
      required: true,
    },
  },
  emits: ['update:dataType', 'comparisonDateChange'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const comparisonPosition = reactive([]);
    const trendChartData = ref([]);
    /** 图表时间范围 */
    const chartTime = reactive({
      start: 0,
      end: 0,
      mid: 0,
    });
    /**
     * 获取trend图表数据
     * @param data 图表数据
     */
    function handleChartData(data) {
      trendChartData.value = data;
      if (data.length) {
        const len = data[0].datapoints.length;
        chartTime.start = data[0].datapoints[0][1];
        chartTime.end = data[0].datapoints[len - 1][1];
        chartTime.mid = chartTime.start + (chartTime.end - chartTime.start) / 2;
        setDefaultDate();
      }
    }

    const trendQueryParams = computed(() => {
      const {
        filter_labels: { start, end, ...filterLabels },
        diff_filter_labels: { start: diffStart, end: diffEnd, ...diffFilterLabels },
        ...rest
      } = props.queryParams;

      return {
        ...rest,
        filter_labels: filterLabels,
        diff_filter_labels: diffFilterLabels,
      };
    });

    watch(
      () => props.formData.dateComparison.enable,
      val => {
        if (!val) {
          comparisonPosition.splice(0);
        } else {
          setDefaultDate();
        }
      }
    );

    /**
     * 设置对比项默认框选时间
     */
    function setDefaultDate() {
      if (!trendChartData.value.length || !props.formData.dateComparison.enable) return;
      comparisonPosition[0] = [chartTime.start, chartTime.mid];
      comparisonPosition[1] = [chartTime.mid, chartTime.end];
      handleComparisonDateChange();
    }

    function handleBrushEnd(data, type) {
      if (type === 'search') {
        comparisonPosition[0] = data;
      } else {
        comparisonPosition[1] = data;
      }
      handleComparisonDateChange();
    }

    function handleComparisonDateChange() {
      emit('comparisonDateChange', {
        enable: props.formData.dateComparison.enable,
        start: comparisonPosition[0]?.[0],
        end: comparisonPosition[0]?.[1],
        diffStart: comparisonPosition[1]?.[0],
        diffEnd: comparisonPosition[1]?.[1],
      });
    }

    return {
      t,
      trendChartData,
      trendQueryParams,
      comparisonPosition,
      handleChartData,
      handleBrushEnd,
    };
  },
  render() {
    return (
      <div class='profiling-retrieval-view-component'>
        <div class='data-type'>
          {this.$t('数据类型')}
          <Button.ButtonGroup
            class='data-type-list'
            size='small'
          >
            {this.dataTypeList.map(item => {
              return (
                <Button
                  key={item.key}
                  selected={item.key === this.dataType}
                  onClick={() => {
                    this.$emit('update:dataType', item.key);
                  }}
                >
                  {item.name}
                </Button>
              );
            })}
          </Button.ButtonGroup>
        </div>
        <TrendChart
          comparisonDate={this.comparisonPosition}
          queryParams={this.trendQueryParams}
          onChartData={this.handleChartData}
        />

        {this.formData.dateComparison.enable && (
          <div class='date-comparison-view'>
            <div class='comparison-chart-card'>
              <div class='title'>{this.t('查询项')}</div>
              <div class='chart-wrap'>
                <ComparisonChart
                  colorIndex={0}
                  comparisonDate={this.comparisonPosition[0]}
                  data={this.trendChartData[0]}
                  title={this.t('查询项')}
                  onBrushEnd={val => this.handleBrushEnd(val, 'search')}
                />
              </div>
            </div>
            <div class='comparison-chart-card'>
              <div class='title'>{this.t('对比项')}</div>
              <div class='chart-wrap'>
                <ComparisonChart
                  colorIndex={1}
                  comparisonDate={this.comparisonPosition[1]}
                  data={this.trendChartData[1]}
                  title={this.t('对比项')}
                  onBrushEnd={val => this.handleBrushEnd(val, 'comparison')}
                />
              </div>
            </div>
          </div>
        )}

        <div class='profiling-graph-view-content'>
          <ProfilingGraph queryParams={this.queryParams} />
        </div>
      </div>
    );
  },
});
