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

import type { MetricDetailV2 } from '../typings';
import type {
  ICommonVariableModel,
  IConditionVariableModel,
  IConstantVariableModel,
  IDimensionValueVariableModel,
  IDimensionVariableModel,
  IFunctionVariableModel,
  IMethodVariableModel,
  IVariableModel,
  VariableTypeEnumType,
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
    this.id = config.id || random(5);
  }

  abstract get data(): Required<IVariableModel>;
}

export class ConditionVariableModel extends VariableBase {
  dimensionOption = [];
  /** 关联指标 */
  metric: MetricDetailV2 = null;
  value: IConditionVariableModel['value'] = [];
  constructor(config: IConditionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.value = config.value || [];
    this.dimensionOption = config.dimensionOption || ['all'];
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.CONDITION,
      name: this.name,
      alias: this.alias,
      desc: this.desc,
      metric: this.metric,
      dimensionOption: this.dimensionOption,
      value: this.value,
    };
  }
  /** 维度列表 */
  get dimensionList() {
    return this.metric.dimensions;
  }
  /** 可选维度列表映射 */
  get dimensionOptionsMap() {
    return this.isAllDimensionOptions
      ? this.dimensionList
      : this.dimensionList.filter(item => this.dimensionOption.includes(item.id));
  }
  get isAllDimensionOptions() {
    return this.dimensionOption.includes('all');
  }
}

export class ConstantVariableModel extends VariableBase {
  value = '';
  constructor(config: IConstantVariableModel) {
    super(config);
    this.value = config.value || '';
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.CONSTANT,
      name: this.name,
      alias: this.alias,
      desc: this.desc,
      value: this.value,
    };
  }
}

export class DimensionValueVariableModel extends VariableBase {
  /** 关联指标 */
  metric: MetricDetailV2 = null;
  /** 关联维度 */
  relationDimension = '';
  value = '';
  constructor(config: IDimensionValueVariableModel) {
    super(config);
    this.metric = config.metric;
    this.relationDimension = config.relationDimension || '';
    this.value = config.value || '';
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.DIMENSION_VALUE,
      name: this.name,
      alias: this.alias,
      desc: this.desc,
      metric: this.metric,
      value: this.value,
      relationDimension: this.relationDimension,
    };
  }
}

export class DimensionVariableModel extends VariableBase {
  /** 可选维度 */
  dimensionOption = [];
  metric: MetricDetailV2 = null;
  value = '';

  constructor(config: IDimensionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.dimensionOption = config.dimensionOption || ['all'];
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.isAllDimensionOptions ? this.dimensionList[0].id : this.dimensionOption[0];
    }
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.DIMENSION,
      name: this.name,
      alias: this.alias,
      desc: this.desc,
      metric: this.metric,
      dimensionOption: this.dimensionOption,
      value: this.value,
    };
  }
  /** 维度列表 */
  get dimensionList() {
    return this.metric.dimensions;
  }
  /** 可选维度列表映射 */
  get dimensionOptionsMap() {
    return this.isAllDimensionOptions
      ? this.dimensionList
      : this.dimensionList.filter(item => this.dimensionOption.includes(item.id));
  }
  get isAllDimensionOptions() {
    return this.dimensionOption.includes('all');
  }

  get valueMap() {
    return this.dimensionList.find(item => item.id === this.value);
  }
}

export class FunctionVariableModel extends VariableBase {
  value = null;
  constructor(config: IFunctionVariableModel) {
    super(config);
    this.value = config.value || null;
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.FUNCTION,
      name: this.name,
      alias: this.alias,
      desc: this.desc,
      value: this.value,
    };
  }
}

export class MethodVariableModel extends VariableBase {
  metric: MetricDetailV2 = null;
  value = '';
  constructor(config: IMethodVariableModel) {
    super(config);
    this.value = config.value || 'SUM';
    this.metric = config.metric;
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.METHOD,
      name: this.name,
      alias: this.alias,
      metric: this.metric,
      desc: this.desc,
      value: this.value,
    };
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
