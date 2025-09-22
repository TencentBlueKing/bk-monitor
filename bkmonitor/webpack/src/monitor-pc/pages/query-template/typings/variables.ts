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

import type { VariableTypeEnum } from '../constants';
import type { GetEnumTypeTool } from './constants';
import type { MetricDetailV2 } from './metric';
import type { AggCondition, AggFunction } from './query-config';

export interface ICommonVariableModel<T extends VariableTypeEnumType> {
  alias?: string;
  description?: string;
  id?: string;
  isValueEditable?: boolean;
  name: string;
  type: T;
}

export type IConditionVariableModel = ICommonVariableModel<typeof VariableTypeEnum.CONDITIONS> & {
  defaultValue?: AggCondition[];
  metric: MetricDetailV2;
  /** 可选维度 */
  options?: string[];
  value?: AggCondition[];
};

export type IConstantVariableModel = ICommonVariableModel<typeof VariableTypeEnum.CONSTANTS> & {
  defaultValue?: string;
  value?: string;
};

export type IDimensionValueVariableModel = ICommonVariableModel<typeof VariableTypeEnum.TAG_VALUES> & {
  defaultValue?: string[];
  metric: MetricDetailV2;
  /** 关联维度 */
  related_tag: string;
  value?: string[];
};

export type IDimensionVariableModel = ICommonVariableModel<typeof VariableTypeEnum.GROUP_BY> & {
  defaultValue?: string[];
  metric: MetricDetailV2;
  /** 可选维度 */
  options?: string[];
  value?: string[];
};

export type IFunctionVariableModel = ICommonVariableModel<
  typeof VariableTypeEnum.EXPRESSION_FUNCTIONS | typeof VariableTypeEnum.FUNCTIONS
> & {
  defaultValue?: AggFunction[];
  value?: AggFunction[];
};

export type IMethodVariableModel = ICommonVariableModel<typeof VariableTypeEnum.METHOD> & {
  defaultValue?: string;
  value?: string;
};

export type IVariableData = IVariableModel & { variableName: string };

export interface IVariableFormEvents {
  onAliasChange: (val: string) => void;
  onDefaultValueChange: (val: any) => void;
  onDescChange: (val: string) => void;
  onNameChange: (val: string) => void;
  onOptionsChange: (val: string[]) => void;
  onValueChange: (val: any) => void;
}

export type IVariableModel =
  | IConditionVariableModel
  | IConstantVariableModel
  | IDimensionValueVariableModel
  | IDimensionVariableModel
  | IFunctionVariableModel
  | IMethodVariableModel;

/** 变量提交参数结构 */
export type IVariableSubmitParams = {
  alias: string;
  config: {
    default: any;
    options?: string[];
    related_metrics?: {
      metric_field: string;
      metric_id: string;
    }[];
    related_tag?: string;
  };
  description: string;
  name: string;
  type: VariableTypeEnumType;
};

export type VariableTypeEnumType = GetEnumTypeTool<typeof VariableTypeEnum>;
