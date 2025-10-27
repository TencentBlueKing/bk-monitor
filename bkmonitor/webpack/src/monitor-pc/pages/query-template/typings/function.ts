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

// 函数接口
export interface FunctionItem {
  /** 函数分类 */
  category: string;
  /** 函数描述 */
  description: string;
  /** 函数ID */
  id: string;
  /** 是否忽略单位 */
  ignore_unit: boolean;
  /** 函数名称 */
  name: string;
  /** 函数参数 */
  params: FunctionParam[];
  /** 位置 */
  position: number;
  /** 是否支持表达式 */
  support_expression: boolean;
  /** 是否时间聚合 */
  time_aggregation: boolean;
  /** 是否支持维度 */
  with_dimensions: boolean;
}

// 函数列表类型
export type FunctionList = MetricFunction[];

// 函数参数接口
export interface FunctionParam {
  /** 默认值 */
  default?: number | string;
  /** 参数描述 */
  description: string;
  /** 参数ID */
  id: string;
  /** 参数名称 */
  name: string;
  /** 是否必需 */
  required: boolean;
  /** 可选值列表 */
  shortlist?: (number | string)[];
  /** 参数类型 */
  type: string;
}

// 函数分类接口
export interface MetricFunction {
  /** 子函数列表 */
  children: FunctionItem[];
  /** 分类描述 */
  description: string;
  /** 分类ID */
  id: string;
  /** 分类名称 */
  name: string;
}
