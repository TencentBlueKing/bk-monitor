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

import { defineComponent, shallowRef, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';
import { MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';

import BaseEchart from '../../../plugins/base-echart';
import { useChartResize } from '../../../plugins/hooks';

import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './dimension-echarts.scss';

export default defineComponent({
  name: 'DimensionEcharts',
  props: {
    colorList: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    seriesType: {
      type: String as PropType<'bar' | 'line'>,
      default: 'line',
    },
    data: {
      type: Array as PropType<any[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const chartContainer = shallowRef();
    const width = shallowRef(370);
    const height = shallowRef(136);
    const baseEchartRef = shallowRef();
    const options = shallowRef<MonitorEchartOptions>({});

    useChartResize(chartContainer, chartContainer, width, height);

    watch(
      () => props.data,
      () => {
        setOptions();
      },
      { immediate: true }
    );

    function setOptions() {
      const series = props.data.map(item => ({
        type: props.seriesType,
        name: item.name,
        data: item.data,
        symbol: 'none',
        z: 6,
      }));

      options.value = deepmerge(
        deepClone(MONITOR_LINE_OPTIONS),
        {
          series,
          toolbox: [],
          color: props.colorList,
          yAxis: {
            splitLine: {
              lineStyle: {
                color: '#F0F1F5',
                type: 'solid',
              },
            },
            splitNumber: 5,
          },
        },
        { arrayMerge: (_, newArr) => newArr }
      );
    }

    return {
      t,
      chartContainer,
      width,
      height,
      baseEchartRef,
      options,
    };
  },
  render() {
    return (
      <div
        ref='chartContainer'
        class='trace-explore-dimension-echarts-e'
      >
        {this.data.length ? (
          <BaseEchart
            ref='baseEchartRef'
            width={this.width}
            height={this.height}
            options={this.options}
          />
        ) : (
          <div class='empty-chart'>{this.t('查无数据')}</div>
        )}
      </div>
    );
  },
});
