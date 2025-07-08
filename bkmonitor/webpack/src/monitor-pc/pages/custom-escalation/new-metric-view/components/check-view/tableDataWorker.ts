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
import type { IColumnItem, IDataItem } from 'monitor-pc/pages/custom-escalation/new-metric-view/type';

const TYPE_ARR = {
  max: '最大值',
  min: '最小值',
  latest: '最新值',
  avg: '平均值',
  total: '累计值',
} as const;

const handleProp = (() => {
  const cache = new Map<string, string>();
  return (item: IDataItem): string => {
    const key = JSON.stringify(item.dimensions);
    if (cache.has(key)) {
      return cache.get(key)!;
    }
    const dimensions = Object.values(item.dimensions || {});
    const result = dimensions.length > 0 ? dimensions.join(' | ') : item.target;
    cache.set(key, result);
    return result;
  };
})();

// 键生成函数
const handleKey = (child: IDataItem, title: string, index: number, isMergeTable: boolean): string => {
  const timeOffset = child.time_offset || child.timeOffset || 'current';
  return isMergeTable ? `${title}${timeOffset}${index}` : `${title}${timeOffset}`;
};

// 表格底部数据生成
const generateFooterDataList = (columns: IColumnItem[], isCompareNotDimensions: boolean, isMergeTable: boolean) => {
  const footerDataList = new Array(Object.keys(TYPE_ARR).length);
  let index = 0;

  for (const [key, value] of Object.entries(TYPE_ARR)) {
    footerDataList[index++] = {
      key,
      time: value,
    };
  }

  const keyMap = new Map<string, IDataItem>();

  for (const item of columns) {
    const title = handleProp(item) || '';

    for (const child of item.items) {
      const key = isCompareNotDimensions
        ? child.timeOffset
        : handleKey(child, title, item.items.indexOf(child), isMergeTable);
      keyMap.set(key, child);
    }
  }

  for (const footer of footerDataList) {
    for (const [key, child] of keyMap) {
      footer[key] = child[footer.key];
      footer[`${key}Time`] = child[`${footer.key}Time`];
    }
  }

  return footerDataList;
};

// 表格主体数据处理
const processTimeData = (
  data: IDataItem[],
  timeData: any[],
  compare: string[],
  isCompareNotDimensions: boolean,
  isMergeTable: boolean
) => {
  const timeMap = new Map<number, any>();
  const processedTimeData = timeData.map(time => {
    timeMap.set(time.date, time);
    return time;
  });

  const unitMap = new Map<string, string>();

  for (const [ind, item] of data.entries()) {
    const title = isCompareNotDimensions ? '' : handleProp(item) || '';

    for (const [index, child] of item.items.entries()) {
      const key = isCompareNotDimensions ? child.time_offset : handleKey(child, title, index, isMergeTable);

      if (!unitMap.has(key)) {
        unitMap.set(key, child.unit);
      }

      // 数据点处理
      for (const point of child.datapoints) {
        const time = timeMap.get(point[1]);
        if (time) {
          time[key] = point[0];
        }
      }
    }

    // 波动率计算
    for (const time of processedTimeData) {
      const firstValidKey = Object.keys(time).find(key => unitMap.has(key));
      time.unit = firstValidKey ? unitMap.get(firstValidKey) : undefined;

      const first = time[`${title}${compare[0]}${isCompareNotDimensions ? '' : 0}`];
      const second = time[`${title}${compare[1]}${isCompareNotDimensions ? '' : 1}`];

      if (first && second) {
        const data = ((second - first) / first) * 100;
        time[`fluctuation${ind}`] = Number.isFinite(data) ? data : '--';
      } else {
        time[`fluctuation${ind}`] = '--';
      }
    }
  }

  return processedTimeData;
};

self.onmessage = (
  e: MessageEvent<{
    data: IDataItem[];
    columns: IColumnItem[];
    compare: string[];
    timeData: IDataItem[];
    isCompareNotDimensions: boolean;
    isMergeTable: boolean;
  }>
) => {
  const { data, columns, compare, timeData, isCompareNotDimensions, isMergeTable } = e.data;

  Promise.all([
    generateFooterDataList(columns, isCompareNotDimensions, isMergeTable),
    processTimeData(data, timeData, compare, isCompareNotDimensions, isMergeTable),
  ]).then(([footerDataList, tableData]) => {
    self.postMessage({
      tableData,
      footerDataList,
      origin,
    });
  });
};
