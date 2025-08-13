// 扩展数据
export interface IExtendDataItem {
  // 名称
  name: string;
  // 类型
  type?: string;
  // 单位
  unit?: string;
  // 值
  value: string;
}

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
// china status-map 数据定义
export interface IStatusMapData {
  extend_data: IExtendDataItem[];
  legend: IStatusMapLegendItem[];
  series: IStatusMapSeriesItem[];
}
// 图例数据
export interface IStatusMapLegendItem {
  // 图例名称
  name: string;
  // 状态 4种状态 对应legend显示的4种级别显示
  status: 1 | 2 | 3 | 4;
}
// series
export interface IStatusMapSeriesItem {
  // 省份 或 直辖市 及 南海诸岛名称
  name: string;
  // 状态 4种状态 对应legend显示的4种级别显示
  status: 1 | 2 | 3 | 4;
  // 值
  value: number;
}
