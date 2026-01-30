/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, provide, shallowRef, toRef } from 'vue';

import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import { type TimeRangeType, DEFAULT_TIME_RANGE } from '../../../../../components/time-range/utils';
import MonitorCharts from './echarts/monitor-charts';

import './dimension-chart.scss';
export default defineComponent({
  name: 'DimensionChart',
  props: {
    /** 下钻维度 */
    groupBy: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 下钻过滤条件 */
    filterBy: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 图表需要请求的数据的开始时间 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
    /** 是否展示复位按钮 */
    showRestore: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['dataZoomChange', 'restore'],
  setup(props) {
    /** 面板数据配置 */
    const panel = shallowRef(new PanelModel({}));

    provide('timeRange', toRef(props, 'timeRange'));

    return { panel };
  },
  render() {
    return (
      <div class='alarm-dimension-chart'>
        <MonitorCharts
          panel={this.panel}
          showRestore={this.showRestore}
          onDataZoomChange={(timeRange: [number, number]) => this.$emit('dataZoomChange', timeRange)}
          onRestore={() => this.$emit('restore')}
        />
      </div>
    );
  },
});
