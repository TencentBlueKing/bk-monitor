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

import type { VariableTypeEnum } from '../constants';
import type { GetEnumTypeTool } from './constants';
import type { MetricDetailV2 } from './metric';
import type { IFilterItem } from '@/components/retrieval-filter/utils';

export interface ICommonVariableModel<T extends VariableTypeEnumType> {
  alias?: string;
  desc?: string;
  id?: string;
  name: string;
  type: T;
}

export type IConditionVariableModel = {
  /** 可选维度 */
  dimensionOption?: string[];
  metric: MetricDetailV2;
  value?: IFilterItem[];
} & ICommonVariableModel<typeof VariableTypeEnum.CONDITION>;

export type IConstantVariableModel = ICommonVariableModel<typeof VariableTypeEnum.CONSTANT> & {
  value?: string;
};

export type IDimensionValueVariableModel = ICommonVariableModel<typeof VariableTypeEnum.DIMENSION_VALUE> & {
  metric: MetricDetailV2;
  /** 关联维度 */
  relationDimension: string;
  value?: string;
};

export type IDimensionVariableModel = {
  /** 可选维度 */
  dimensionOption?: string[];
  metric: MetricDetailV2;
  value?: string;
} & ICommonVariableModel<typeof VariableTypeEnum.DIMENSION>;

export type IFunctionVariableModel = ICommonVariableModel<typeof VariableTypeEnum.FUNCTION> & {
  value?: any;
};

export type IMethodVariableModel = ICommonVariableModel<typeof VariableTypeEnum.METHOD> & {
  metric: MetricDetailV2;
  value?: string;
};

export type IVariableData = Required<IVariableModel & { variableName: string }>;

export type IVariableModel =
  | IConditionVariableModel
  | IConstantVariableModel
  | IDimensionValueVariableModel
  | IDimensionVariableModel
  | IFunctionVariableModel
  | IMethodVariableModel;

export type VariableTypeEnumType = GetEnumTypeTool<typeof VariableTypeEnum>;
