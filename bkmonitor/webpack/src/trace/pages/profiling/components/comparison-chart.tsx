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
import { defineComponent } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import BaseEchart from '../../../plugins/base-echart';

import './comparison-chart.scss';

export default defineComponent({
  name: 'ComparisonChart',
  props: {
    data: {
      type: Object,
      default: () => null,
    },
    title: {
      type: String,
      default: '',
    },
    colorIndex: {
      type: Number,
    },
  },
  emits: ['brushEnd'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const defaultOptions = {
      xAxis: {
        type: 'time',
        axisLine: {
          lineStyle: {
            color: '#F0F1F5',
          },
        },
        axisLabel: {
          color: '#979BA5',
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          show: false,
        },
      },
      yAxis: {
        type: 'value',
        axisTick: {
          show: false,
        },
        axisLabel: {
          formatter: (v: any) => {
            if (props.data.unit !== 'none') {
              const obj = getValueFormat(props.data.unit)(v, 0);
              return obj.text + (obj.suffix || '');
            }
            return v;
          },
        },
        splitNumber: 4,
        minInterval: 1,
        position: 'left',
      },
      toolbox: {
        showTitle: false,
        itemSize: 0,
        feature: {
          brush: {},
        },
      },
      brush: {
        xAxisIndex: 'all',
        brushLink: 'all',
        toolbox: ['lineX', 'clear'],
        brushStyle: {
          color: ['rgba(58, 132, 255, 0.1)', 'rgba(255, 86, 86, 0.1)'][props.colorIndex],
        },
        outOfBrush: {
          colorAlpha: 0.1,
        },
      },
      series: [],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(54,58,67,.88)',
        borderWidth: 0,
      },
      grid: {
        left: 16,
        top: 10,
        right: 40,
        bottom: 10,
        containLabel: true,
      },
    };

    const options = computed(() => {
      return {
        ...defaultOptions,
        series: [
          {
            name: props.title,
            type: 'line',
            data: props.data?.datapoints?.map(item => [item[1], item[0]]) || [],
            showSymbol: false,
            unitFormatter:
              props.data.unit !== 'none' ? getValueFormat(props.data.unit || '') : (v: any) => ({ text: v }),
            precision: 2,
          },
        ],
      };
    });

    function handleBrushEnd(val) {
      console.log(val);
      emit('brushEnd', val);
    }

    return {
      t,
      options,
      handleBrushEnd,
    };
  },
  render() {
    if (!this.data) return <div class='empty-chart'>{this.t('查无数据')}</div>;

    return (
      <BaseEchart
        options={this.options}
        onBrushEnd={this.handleBrushEnd}
      />
    );
  },
});
