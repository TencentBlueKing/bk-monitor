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

import { random } from 'monitor-common/utils';

import { VariableTypeEnum } from '../constants';

import type { MetricDetail } from '../components/type/query-config';
import type { VariableTypeEnumType } from '../typings';
import type { IDimensionVariableModel, IMethodVariableModel } from '../typings';
import type {
  ICommonVariableModel,
  IConditionVariableModel,
  IConstantVariableModel,
  IDimensionValueVariableModel,
  IFunctionVariableModel,
  IVariableModel,
} from '../typings/variables';

export type VariableModelType =
  | ConditionVariableModel
  | ConstantVariableModel
  | DimensionValueVariableModel
  | DimensionVariableModel
  | FunctionVariableModel
  | MethodVariableModel;

abstract class VariableBase {
  alias = '';
  desc = '';
  id = '';
  name = '';
  type: VariableTypeEnumType;
  abstract value: any;
  constructor(config: ICommonVariableModel<VariableTypeEnumType>) {
    this.name = config.name;
    this.alias = config.alias;
    this.desc = config.desc;
    this.type = config.type;
    this.id = random(5);
  }
}

export class ConditionVariableModel extends VariableBase {
  dimensionOption = [];
  /** 关联指标 */
  metric: MetricDetail = null;
  value: IConditionVariableModel['value'] = [];
  constructor(config: IConditionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.value = config.value || [];
    this.dimensionOption = config.dimensionOption || ['all'];
  }
}

export class ConstantVariableModel extends VariableBase {
  value = '';
  constructor(config: IConstantVariableModel) {
    super(config);
    this.value = config.value || '';
  }
}

export class DimensionValueVariableModel extends VariableBase {
  /** 关联指标 */
  metric: MetricDetail = null;
  /** 关联维度 */
  relationDimension = '';
  value = '';
  constructor(config: IDimensionValueVariableModel) {
    super(config);
    this.metric = config.metric;
    this.relationDimension = config.relationDimension || '';
    this.value = config.value || '';
  }
}

export class DimensionVariableModel extends VariableBase {
  dimensionOption = [];
  metric: MetricDetail = null;
  value = '';
  constructor(config: IDimensionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.dimensionOption = config.dimensionOption || ['all'];
    this.value = config.value || '';
  }
}

export class FunctionVariableModel extends VariableBase {
  value = null;
  constructor(config: IFunctionVariableModel) {
    super(config);
    this.value = config.value || null;
  }
}

export class MethodVariableModel extends VariableBase {
  metric: MetricDetail = null;
  value = '';
  constructor(config: IMethodVariableModel) {
    super(config);
    this.value = config.value || '';
    this.metric = config.metric;
  }
}

export function getVariableModel(config: IVariableModel): VariableModelType {
  switch (config.type) {
    case VariableTypeEnum.METHOD:
      return new MethodVariableModel(config);
    case VariableTypeEnum.DIMENSION:
      return new DimensionVariableModel(config);
    case VariableTypeEnum.DIMENSION_VALUE:
      return new DimensionValueVariableModel(config);
    case VariableTypeEnum.FUNCTION:
      return new FunctionVariableModel(config);
    case VariableTypeEnum.CONDITION:
      return new ConditionVariableModel(config);
    case VariableTypeEnum.CONSTANT:
      return new ConstantVariableModel(config);
  }
}
