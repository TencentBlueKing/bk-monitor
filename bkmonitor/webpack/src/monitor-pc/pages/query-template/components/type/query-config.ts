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

import { MetricDetail as BaseMetricDetail } from '@/pages/strategy-config/strategy-config-set-new/typings';

import type { VariableTypeEnum } from '../../constants';
import type { MetricDetail as TypeMetricDetail } from '@/pages/strategy-config/strategy-config-set-new/typings';

export interface IConditionOptionsItem extends IVariablesItem {
  dimensionType: 'number' | 'string';
  id: string;
  isVariable?: boolean;
}

/* 维度选项 */
export interface IDimensionOptionsItem extends IVariablesItem {
  id: string;
  isVariable?: boolean;
}

/* 函数选项 */
export interface IFunctionOptionsItem extends IVariablesItem {
  children?: IFunctionOptionsItem[];
  description?: string;
  id: string;
  isVariable?: boolean;
  key?: string;
  name: string;
  params?: IFunctionParam[];
  support_expression?: boolean;
}

export interface IFunctionParam {
  default: number | string;
  edit?: boolean;
  id?: string;
  name?: string;
  shortlist: number[] | string[];
  value?: number | string;
}
/** 汇聚方法选项 */
export interface IMethodOptionsItem extends IVariablesItem {
  id: string;
  isVariable?: boolean;
}

export interface IVariablesItem {
  name?: string;
  type?: (typeof VariableTypeEnum)[keyof typeof VariableTypeEnum];
}

export type TMetricDetail = Partial<TypeMetricDetail>;

export class MetricDetail extends BaseMetricDetail {}
