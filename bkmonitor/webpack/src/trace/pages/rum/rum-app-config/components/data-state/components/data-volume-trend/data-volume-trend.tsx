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

import { type PropType, defineComponent, provide, toRef } from 'vue';

import EmptyStatus from '../../../../../../../components/empty-status/empty-status';
import { DEFAULT_TIME_RANGE } from '../../../../../../../components/time-range/utils';
import AlarmMetricsDashboard from '../../../../../../alarm-center/components/alarm-metrics-dashboard/alarm-metrics-dashboard';

import type { TimeRangeType } from '../../../../../../../components/time-range/utils';
import type { IDataQuery } from '../../../../../../../plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './data-volume-trend.scss';

/** 图表格式化数据 */
interface IChartData {
  [key: string]: any;
  query_config?: IDataQuery[];
  series: IChartSeriesItem[];
}

/** 图表数据项 */
interface IChartSeriesItem {
  [key: string]: any;
  alias?: string;
  target: string;
}

/** 图表默认列数 */
const DEFAULT_GRID_COL = 2;

export default defineComponent({
  name: 'DataVolumeTrend',
  props: {
    /** 图表面板配置列表 */
    dashboardPanels: {
      type: Array as PropType<IPanelModel[]>,
      default: () => [],
    },
    /** 数据加载中状态 */
    loading: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
    /** 时间范围 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
  },
  setup(props) {
    /** 注入时间范围给图表组件使用 */
    provide('timeRange', toRef(props, 'timeRange'));

    /**
     * @description 格式化图表数据
     */
    const formatterData = (data: IChartData, target: IDataQuery) => {
      return {
        ...data,
        query_config: data?.query_config || target.data,
        series: data.series.map(item => ({
          ...item,
          alias: item.target,
        })),
      };
    };

    /** 渲染骨架屏 */
    const renderSkeleton = () => (
      <div class='data-volume-trend-skeleton'>
        {['minute-data', 'daily-data'].map(key => (
          <div
            key={key}
            class='data-volume-trend-skeleton-item skeleton-element'
          />
        ))}
      </div>
    );

    /** 渲染空状态 */
    const renderEmpty = () => (
      <div class='data-volume-trend-empty'>
        <EmptyStatus type='empty' />
      </div>
    );

    /** 渲染数据面板 */
    const renderDashboard = () => (
      <div class='data-volume-trend-content'>
        <AlarmMetricsDashboard
          class='data-volume-trend-dashboard'
          customOptions={{
            formatterData,
          }}
          gridCol={DEFAULT_GRID_COL}
          panelModels={props.dashboardPanels}
          showHeader={false}
        />
      </div>
    );
    return { renderSkeleton, renderEmpty, renderDashboard };
  },
  render() {
    return (
      <div class='data-volume-trend'>
        {this.loading
          ? this.renderSkeleton()
          : this.dashboardPanels.length === 0
            ? this.renderEmpty()
            : this.renderDashboard()}
      </div>
    );
  },
});
