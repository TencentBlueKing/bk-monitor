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

// Percentage Bar api 数据定义

// text 为普通文本展示 link 为可跳转链接
export type BarLabelType = 'link' | 'text';
export interface IPercentageBarData {
  // 指标数据
  metrics?: [];
  // 更多数据的跳转链接
  more_data_url: string;
  // 图例名称
  name: string;
  // 数据
  series: IPercentageBarSeriesItem[];
}
export interface IPercentageBarSeriesItem {
  key?: string;
  // 名称
  name: string;
  target?: LinkItemTarget;
  // total
  total?: number;
  // 类型
  type?: BarLabelType;
  // 单位
  unit?: number;
  url?: string;
  // 值
  value: number;
}

// self 为内部框架跳转  blank为新开窗口跳转 event 触发本地事件
export type LinkItemTarget = 'blank' | 'event' | 'self';
