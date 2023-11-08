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
import dayjs from 'dayjs';

import { downFile } from '../../utils';

export interface IUnifyQuerySeriesItem {
  datapoints: Array<[number, number]>;
  target: string;
}
/**
 * 根据图表接口响应的数据转换成表格展示的原始数据
 * @param data unify_query响应的series数据
 */
export const transformSrcData = (data: IUnifyQuerySeriesItem[]) => {
  let tableThArr = []; /** 表头数据 */
  let tableTdArr = []; /** 表格数据 */

  tableThArr = data.map(item => item.target); // 原始数据表头
  tableThArr.unshift('time');
  //  原始数据表格数据
  tableTdArr = data[0].datapoints.map(set => [
    {
      value: dayjs.tz(set[1]).format('YYYY-MM-DD HH:mm:ss'),
      originValue: set[1]
    }
  ]);
  data.forEach(item => {
    item.datapoints.forEach((set, index) => {
      tableTdArr[index]?.push({
        max: false,
        min: false,
        value: set[0],
        originValue: set[0]
      });
    });
  });
  // 计算极值
  const maxMinMap = tableThArr.map(() => ({
    max: null,
    min: null
  }));
  tableThArr.forEach((th, index) => {
    if (index > 0) {
      const map = maxMinMap[index];
      map.min = tableTdArr[0][index].value;
      map.max = map.min;
      tableTdArr.forEach(td => {
        const cur = td[index]?.value;
        cur > map.max && cur !== null && (map.max = cur);
        cur < map.min && cur !== null && (map.min = cur);
      });
    }
  });
  tableTdArr.forEach(th => {
    th.forEach((td, i) => {
      if (i > 0) {
        if (maxMinMap[i].max !== null && td.value === maxMinMap[i].max) {
          td.max = true;
          maxMinMap[i].max = null;
        }
        if (maxMinMap[i].min !== null && td.value === maxMinMap[i].min) {
          td.min = true;
          maxMinMap[i].min = null;
        }
        td.min && td.max && (td.max = false);
      }
    });
  });
  return {
    tableThArr,
    tableTdArr
  };
};

export interface IIableTdArrItem {
  value: number;
}
/**
 * 根据表格数据转换成csv字符串
 * @param tableThArr 表头数据
 * @param tableTdArr 表格数据
 */
export const transformTableDataToCsvStr = (tableThArr: string[], tableTdArr: Array<IIableTdArrItem[]>): string => {
  const csvList: string[] = [tableThArr.join(',')];
  tableTdArr.forEach(row => {
    const rowString = row.reduce((str, item, index) => str + (!!index ? ',' : '') + item.value, '');
    csvList.push(rowString);
  });
  const csvString = csvList.join('\n');
  return csvString;
};
/**
 * 根据csv字符串下载csv文件
 * @param csvStr csv字符串
 */
export const downCsvFile = (csvStr: string, name = 'csv-file.csv') => {
  csvStr = `\ufeff${csvStr}`;
  const blob = new Blob([csvStr], { type: 'text/csv,charset=UTF-8' });
  const href = window.URL.createObjectURL(blob);
  downFile(href, name);
};

export const refleshList = [
  // 刷新间隔列表
  {
    name: 'off',
    id: -1
  },
  {
    name: '1m',
    id: 60 * 1000
  },
  {
    name: '5m',
    id: 5 * 60 * 1000
  },
  {
    name: '15m',
    id: 15 * 60 * 1000
  },
  {
    name: '30m',
    id: 30 * 60 * 1000
  },
  {
    name: '1h',
    id: 60 * 60 * 1000
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000
  }
];
