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

const handleProp = (item: IDataItem): string => {
  const dimensions = Object.values(item.dimensions || {});
  return dimensions.length > 0 ? dimensions.join(' | ') : item.target;
};

// 提取 handleKey 函数，用于生成键
const handleKey = (child: IDataItem, title: string, index: number, isMergeTable: boolean): string => {
  const baseKey = `${title}${child.time_offset || child.timeOffset || 'current'}`;
  return isMergeTable ? `${baseKey}${index}` : baseKey;
};
const typeArr = {
  max: '最大值',
  min: '最小值',
  latest: '最新值',
  avg: '平均值',
  total: '累计值',
};

// 生成表格底部数据
const generateFooterDataList = (columns: IColumnItem[], isCompareNotDimensions: boolean, isMergeTable: boolean) => {
  const footerDataList = Object.keys(typeArr).map(key => ({
    key,
    time: typeArr[key],
  }));

  const keyMap = new Map();

  // biome-ignore lint/complexity/noForEach: <explanation>
  columns.forEach(item => {
    const title = handleProp(item) || '';

    item.items.forEach((child, index) => {
      const key = isCompareNotDimensions ? child.timeOffset : handleKey(child, title, index, isMergeTable);
      keyMap.set(key, child);
    });
  });

  // biome-ignore lint/complexity/noForEach: <explanation>
  footerDataList.forEach(footer => {
    keyMap.forEach((child, key) => {
      footer[key] = child[footer.key];
      footer[`${key}Time`] = child[`${footer.key}Time`];
    });
  });

  return footerDataList;
};

// 处理表格主体数据
const processTimeData = (
  data: any[],
  timeData: any[],
  compare: string[],
  isCompareNotDimensions: boolean,
  isMergeTable: boolean
) => {
  const processedTimeData = [...timeData];

  // 为时间数据创建一个映射，便于快速查找
  const timeMap = new Map();
  processedTimeData.map(time => {
    timeMap.set(time.date, time);
  });

  const unitMap = new Map();

  data.forEach((item, ind) => {
    const title = isCompareNotDimensions ? '' : handleProp(item) || '';

    item.items.forEach((child, index) => {
      const key = isCompareNotDimensions ? child.time_offset : handleKey(child, title, index, isMergeTable);

      if (!unitMap.has(key)) {
        unitMap.set(key, child.unit);
      }

      // biome-ignore lint/complexity/noForEach: <explanation>
      child.datapoints.forEach(point => {
        const time = timeMap.get(point[1]);
        if (time) {
          time[key] = point[0];
        }
      });
    });

    // biome-ignore lint/complexity/noForEach: <explanation>
    processedTimeData.forEach(time => {
      time.unit = unitMap.get(Object.keys(time).find(key => unitMap.has(key)));

      const first = time[`${title}${compare[0]}${isCompareNotDimensions ? '' : 0}`];
      const second = time[`${title}${compare[1]}${isCompareNotDimensions ? '' : 1}`];
      if (first && second) {
        const data = ((second - first) / first) * 100;
        time[`fluctuation${ind}`] = Number.isFinite(data) ? data : '--';
      } else {
        time[`fluctuation${ind}`] = '--';
      }
    });
  });

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

  // 生成表格底部数据
  const footerDataList = generateFooterDataList(columns, isCompareNotDimensions, isMergeTable);

  // 处理表格主体数据
  const tableData = processTimeData(data, timeData, compare, isCompareNotDimensions, isMergeTable);

  // 发送处理结果回主线程
  self.postMessage({
    tableData,
    footerDataList,
  });
};
