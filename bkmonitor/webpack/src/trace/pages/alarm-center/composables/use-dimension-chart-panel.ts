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

import { type MaybeRef, computed, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import { transformDataKey } from 'monitor-common/utils';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants/charts';
import { type IDataQuery, PanelModel } from 'monitor-ui/chart-plugins/typings';

import { DEFAULT_TIME_RANGE } from '../../../components/time-range/utils';

import type { IGraphPanel } from '../typings';
import type { DateValue } from '@blueking/date-picker';

export interface UseDimensionChartPanelOptions {
  /** 告警ID */
  alertId?: MaybeRef<string>;
  /** 业务ID */
  bizId?: MaybeRef<number>;
  /** 默认时间范围 */
  defaultTimeRange?: MaybeRef<DateValue>;
  /** 查询配置 */
  graphPanel?: MaybeRef<IGraphPanel>;
  /** 下钻维度 */
  groupBy?: MaybeRef<string[]>;
  /** 下钻过滤条件 */
  where?: any;
}

/**
 * @function useDimensionChartPanel 告警维度分析图表面板hook
 * @description 组装 维度分析 监控图表面板绘制所需 panel 配置数据
 * @param {UseDimensionChartPanelOptions} options 维度分析图表面板hook选项
 */
export const useDimensionChartPanel = (options: UseDimensionChartPanelOptions) => {
  const { alertId, bizId, defaultTimeRange, where, graphPanel, groupBy } = options;
  /** 图表执行 dataZoom 框线缩放后的时间范围 */
  const dataZoomTimeRange = shallowRef(null);
  /** 视图所使用的时间范围 */
  const viewerTimeRange = computed(() => get(dataZoomTimeRange) ?? get(defaultTimeRange) ?? DEFAULT_TIME_RANGE);
  /** 维度图表 panel 配置数据 */
  const panel = computed<PanelModel>(() => {
    if (!get(alertId) || !get(graphPanel) || !get(groupBy)?.length) return null;

    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { query_configs, expression } = get(graphPanel).targets?.[0]?.data ?? {};
    let queryConfigs = query_configs ?? [];

    if (queryConfigs?.length) {
      queryConfigs = transformDataKey(queryConfigs, true);
      queryConfigs = queryConfigs.map(config => ({
        ...config,
        group_by: get(groupBy) ?? [],
        filter_dict: get(where)?.length
          ? {
              drill_filter: get(where).reduce((prev, cur) => {
                prev[cur.key] = cur.value;
                return prev;
              }, {}),
            }
          : {},
      }));
    }

    return new PanelModel({
      title: get(graphPanel).title || '',
      subTitle: get(graphPanel).subTitle || '',
      gridPos: { x: 16, y: 16, w: 8, h: 4 },
      id: 'alarm-trend-chart',
      type: 'graph',
      targets: [
        {
          datasource: 'time_series',
          dataType: 'time_series',
          api: 'alert_v2.alertGraphQuery',
          data: {
            expression,
            bk_biz_id: get(bizId),
            id: get(alertId),
            query_configs: queryConfigs,
          },
        },
      ],
    });
  });

  /**
   * @description: 格式化series别名
   * @param {any} item series数据
   */
  const formatSeriesAlias = item => {
    if (!get(groupBy)?.length) return item.target;
    if (get(groupBy)?.length === 1) return item.dimensions[get(groupBy)[0]];
    return get(groupBy)
      .map(key => `${key}=${item.dimensions[key]}`)
      .join('|');
  };

  /**
   * @description: 格式化图表数据
   * @param {any} data 图表接口返回的series数据
   */
  const formatterChartData = (data, target: IDataQuery) => {
    return {
      ...data,
      query_config: data?.query_config || target.data,
      series: data.series.map(item => {
        return {
          ...item,
          thresholds: [],
          markPoints: [],
          markTimeRange: [],
          alias: formatSeriesAlias(item),
        };
      }),
    };
  };

  /**
   * @description: 格式化图表options配置
   * @param {any} options echarts配置项
   */
  const formatterOptions = (options: any) => {
    options.color = COLOR_LIST;
    options.grid.right = 20;

    // 为x轴添加刻度线
    Object.assign(options.xAxis[0], {
      boundaryGap: false,
      axisTick: { show: true, alignWithLabel: true },
      axisLine: { show: true },
      splitLine: { show: true },
      axisLabel: { ...options.xAxis[0].axisLabel, align: 'center', showMinLabel: true, showMaxLabel: true },
    });
    // 为y轴添加刻度线
    for (const item of options.yAxis) {
      Object.assign(item, {
        axisTick: { show: true },
        axisLine: { show: true },
        splitLine: { show: true },
      });
    }
    // 添加右侧y轴边框线
    options.yAxis.push({
      show: true,
      position: 'right',
      axisTick: { show: false },
      axisLine: { show: true },
      axisLabel: { show: false },
      splitLine: { show: false },
      z: 3,
    });
    return options;
  };

  /**
   * @description 数据时间范围 值改变后回调
   * @param {[number, number]} e 时间范围
   */
  const handleDataZoomTimeRangeChange = (e?: [number, number]) => {
    if (!e?.[0] || !e?.[1]) {
      dataZoomTimeRange.value = null;
      return;
    }
    dataZoomTimeRange.value = e;
  };

  return {
    panel,
    viewerTimeRange,
    showRestore: dataZoomTimeRange,
    formatterChartData,
    formatterOptions,
    handleDataZoomTimeRangeChange,
    handleChartRestore: () => handleDataZoomTimeRangeChange(),
  };
};
