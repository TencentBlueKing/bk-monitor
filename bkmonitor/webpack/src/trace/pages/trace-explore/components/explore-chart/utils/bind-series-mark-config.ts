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

import type { IMarkAreaConfig, IMarkLineConfig, IMarkPointConfig, IMarkTimeRange, IThreshold } from '../types';

/**
 * 处理阈值线
 * @param thresholds 阈值配置数组
 */
export const handleSetThresholdLine = (thresholds: IThreshold[]): IMarkLineConfig | undefined => {
  if (!thresholds?.length) return undefined;
  return {
    symbol: [],
    label: {
      show: true,
      position: 'insideStartTop',
      color: '#EA3636',
      fontSize: 12,
      backgroundColor: 'transparent',
    },
    lineStyle: {
      color: '#FD9C9C',
      type: 'dashed',
      distance: 3,
      width: 1,
    },
    emphasis: {
      label: {
        show: true,
        formatter: (v: any) => `${v.name || ''}(${v.value})`,
      },
    },
    data: thresholds.map(item => ({
      ...item,
      label: {
        show: true,
        formatter: () => '',
      },
    })),
  };
};

/**
 * 处理阈值区域数据
 * @param thresholds 阈值配置数组
 */
const handleSetThresholdAreaData = (thresholds: IThreshold[]) => {
  const threshold = thresholds.filter(item => item.method && !['eq', 'neq'].includes(item.method));
  const openInterval = ['gte', 'gt'];
  const closedInterval = ['lte', 'lt'];
  const data: any[] = [];

  for (let index = 0; index < threshold.length; index++) {
    const current = threshold[index];
    const nextThreshold = threshold[index + 1];
    let yAxis: number | string | undefined;

    if (
      openInterval.includes(current.method!) &&
      nextThreshold?.condition === 'and' &&
      closedInterval.includes(nextThreshold.method!) &&
      nextThreshold.yAxis >= current.yAxis
    ) {
      yAxis = nextThreshold.yAxis;
      index += 1;
    } else if (openInterval.includes(current.method!)) {
      yAxis = 'max';
    } else if (closedInterval.includes(current.method!)) {
      yAxis = current.yAxis < 0 ? current.yAxis : 0;
    }

    if (yAxis !== undefined) {
      data.push([{ ...current }, { yAxis, y: yAxis === 'max' ? '0%' : '' }]);
    }
  }
  return data;
};

/**
 * @description 处理阈值区域
 * @param thresholds 阈值配置数组
 */
export const handleSetThresholdArea = (thresholds: IThreshold[]): IMarkAreaConfig | undefined => {
  if (!thresholds?.length) return undefined;
  const data = handleSetThresholdAreaData(thresholds);
  if (!data.length) return undefined;
  return {
    silent: true,
    label: {
      show: false,
    },
    itemStyle: {
      color: 'rgba(255, 157, 157, 0.1)',
      borderWidth: 0,
    },
    data,
  };
};

/**
 * @description 处理时间范围标记区域
 * @param markTimeRange 时间范围数组
 */
export const handleSetMarkTimeRange = (markTimeRange: IMarkTimeRange[]): IMarkAreaConfig | undefined => {
  if (!markTimeRange?.length) return undefined;
  return {
    silent: true,
    show: true,
    data: markTimeRange.map(item => [
      {
        xAxis: String(item.from),
        itemStyle: {
          color: item.color || '#FFF5EC',
          borderWidth: 0,
        },
      },
      {
        xAxis: item?.to ? String(item.to) : 'max',
        itemStyle: {
          color: item.color || '#FFF5EC',
          borderWidth: 0,
        },
      },
    ]),
    z: 1,
  };
};

/**
 * @description 处理单个数据点的 markPoints，返回匹配的 markPoint 数据数组
 * @param markPoints markPoints 数组，支持多种格式
 * @param point 当前数据点 [value, timestamp]
 */
const handleSetMarkPointsForPoint = (markPoints: any[], point: [number, number]) => {
  const [value, timestamp] = point;
  const result: { xAxis: string; yAxis: number }[] = [];
  const filteredMarkPoints = markPoints?.filter(
    (mp: any) => mp[1] === timestamp || mp === timestamp || mp?.value === timestamp
  );
  if (filteredMarkPoints?.length) {
    for (const mp of filteredMarkPoints) {
      if (typeof mp === 'object' && mp !== null && !Array.isArray(mp)) {
        // 如果 markPoint 是对象格式，使用默认值合并自定义属性
        result.push({
          xAxis: String(timestamp),
          yAxis: value,
          ...(mp as any),
        });
      } else if (Array.isArray(mp) && mp.length >= 2) {
        // 如果是数组格式 [yAxis, xAxis]，使用数组中的值
        result.push({
          xAxis: String(mp[1]),
          yAxis: mp[0],
        });
      } else {
        // 如果是值格式，使用默认 yAxis
        result.push({
          xAxis: String(timestamp),
          yAxis: value,
        });
      }
    }
  }
  return result;
};

/**
 * @description 处理 markPoints，返回 markPoint 配置
 * @param markPoints markPoints 数组
 * @param datapoints 数据点数组 [value, timestamp][]
 */
export const handleSetMarkPoints = (
  markPoints: any[] | undefined,
  datapoints: [number, number][]
): IMarkPointConfig | undefined => {
  if (!markPoints?.length) return undefined;

  const data: { xAxis: string; yAxis: number }[] = [];
  for (const point of datapoints) {
    data.push(...handleSetMarkPointsForPoint(markPoints, point));
  }

  if (!data.length) return undefined;

  return {
    symbol: 'circle',
    symbolSize: 6,
    z: 10,
    label: {
      show: false,
    },
    itemStyle: {
      color: '#EA3636',
    },
    data,
  };
};
