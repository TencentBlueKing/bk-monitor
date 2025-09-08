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
/** biome-ignore-all lint/complexity/noBannedTypes: <explanation> */

import { random } from 'monitor-common/utils';

import { getMethodIdForLowerCase } from '../components/utils/utils';
import { VariableTypeEnum } from '../constants';
import { fetchMetricDetailList } from '../service';
import { getTemplateSrv } from './template/template-srv';
import { getVariableNameInput, isVariableName } from './template/utils';

import type { AggFunction, MetricDetailV2 } from '../typings';
import type {
  ICommonVariableModel,
  IConditionVariableModel,
  IConstantVariableModel,
  IDimensionValueVariableModel,
  IDimensionVariableModel,
  IFunctionVariableModel,
  IMethodVariableModel,
  IVariableData,
  IVariableModel,
  IVariableSubmitParams,
  VariableTypeEnumType,
} from '../typings/variables';
import type { ScopedVars } from './template/types';

export type VariableModelType =
  | ConditionVariableModel
  | ConstantVariableModel
  | DimensionValueVariableModel
  | DimensionVariableModel
  | FunctionVariableModel
  | MethodVariableModel;

export const variableNameReg = /^[\w.]{1,50}$/;

abstract class VariableBase {
  alias = '';
  /** 默认值 */
  abstract defaultValue: any;
  description = '';
  id = '';
  /** value值是否编辑过 */
  isValueEditable = false;
  name = '';
  type: VariableTypeEnumType;
  /** 已选值 */
  abstract value: any;

  constructor(config: ICommonVariableModel<VariableTypeEnumType>) {
    this.name = config.name;
    this.alias = config.alias;
    this.description = config.description;
    this.type = config.type;
    this.id = config.id || random(5);
    this.isValueEditable = config.isValueEditable || false;
  }

  abstract get data(): IVariableData;

  get scopedVars(): ScopedVars {
    return {
      [this.variableName]: {
        value: this.value,
      },
    };
  }
  get variableName(): string {
    if (isVariableName(this.name)) {
      return getVariableNameInput(this.name);
    } else {
      return this.name;
    }
  }
  replace(target: string, format?: Function | string): string {
    return getTemplateSrv().replace(target, this.scopedVars, format);
  }
}

export class ConditionVariableModel extends VariableBase {
  defaultValue: IConditionVariableModel['value'] = [];
  /** 关联指标 */
  metric: MetricDetailV2 = null;
  options = [];
  value: IConditionVariableModel['value'] = [];

  constructor(config: IConditionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.options = config.options || ['all'];
    this.defaultValue = config.defaultValue || [];
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      isValueEditable: this.isValueEditable,
      type: VariableTypeEnum.CONDITIONS,
      name: this.name,
      alias: this.alias,
      description: this.description,
      metric: this.metric,
      options: this.options,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
    };
  }
  /** 维度列表 */
  get dimensionList() {
    return this.metric?.dimensions || [];
  }
  /** 可选维度列表映射 */
  get dimensionOptionsMap() {
    return this.isAllDimensionOptions
      ? this.dimensionList
      : this.dimensionList.filter(item => this.options.includes(item.id));
  }
  get isAllDimensionOptions() {
    return this.options.includes('all');
  }
}

export class ConstantVariableModel extends VariableBase {
  defaultValue = '';
  value = '';
  constructor(config: IConstantVariableModel) {
    super(config);
    this.defaultValue = config.defaultValue || '';
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.CONSTANTS,
      isValueEditable: this.isValueEditable,
      name: this.name,
      alias: this.alias,
      description: this.description,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
    };
  }
}

export class DimensionValueVariableModel extends VariableBase {
  defaultValue = [];
  /** 关联指标 */
  metric: MetricDetailV2 = null;
  /** 关联维度 */
  related_tag = '';
  value = [];
  constructor(config: IDimensionValueVariableModel) {
    super(config);
    this.metric = config.metric;
    this.related_tag = config.related_tag || '';
    this.defaultValue = config.defaultValue || [];
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.TAG_VALUES,
      isValueEditable: this.isValueEditable,
      name: this.name,
      alias: this.alias,
      description: this.description,
      metric: this.metric,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
      related_tag: this.related_tag,
    };
  }
}

export class DimensionVariableModel extends VariableBase {
  defaultValue: string[] = [];
  metric: MetricDetailV2 = null;
  /** 可选维度 */
  options = [];
  value: string[] = [];

  constructor(config: IDimensionVariableModel) {
    super(config);
    this.metric = config.metric;
    this.options = config.options || ['all'];
    this.defaultValue = config.defaultValue || [];
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.GROUP_BY,
      isValueEditable: this.isValueEditable,
      name: this.name,
      alias: this.alias,
      description: this.description,
      metric: this.metric,
      options: this.options,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
    };
  }

  /** 维度列表 */
  get dimensionList() {
    return this.metric?.dimensions || [];
  }

  /** 可选维度列表映射 */
  get dimensionOptionsMap() {
    return this.isAllDimensionOptions
      ? this.dimensionList
      : this.dimensionList.filter(item => this.options.includes(item.id));
  }

  get isAllDimensionOptions() {
    return this.options.includes('all');
  }
}

export class FunctionVariableModel extends VariableBase {
  defaultValue: AggFunction[] = [];
  value: AggFunction[] = [];
  constructor(config: IFunctionVariableModel) {
    super(config);
    this.defaultValue = config.defaultValue || [];
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      type: this.type as typeof VariableTypeEnum.EXPRESSION_FUNCTIONS | typeof VariableTypeEnum.FUNCTIONS,
      isValueEditable: this.isValueEditable,
      name: this.name,
      alias: this.alias,
      description: this.description,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
    };
  }
}

export class MethodVariableModel extends VariableBase {
  defaultValue = '';
  value = '';
  constructor(config: IMethodVariableModel) {
    super(config);
    this.defaultValue = getMethodIdForLowerCase(config.defaultValue) || 'AVG';
    if (config.value) {
      this.value = config.value;
    } else {
      this.value = this.defaultValue;
    }
  }

  get data() {
    return {
      id: this.id,
      type: VariableTypeEnum.METHOD,
      isValueEditable: this.isValueEditable,
      name: this.name,
      alias: this.alias,
      description: this.description,
      value: this.value,
      defaultValue: this.defaultValue,
      variableName: this.variableName,
    };
  }
}

/** 获取创建变量所需参数结构 */
export async function getCreateVariableParams(
  params: IVariableSubmitParams[],
  metricsDetail: MetricDetailV2[] = []
): Promise<IVariableModel[]> {
  /** 需要获取详情的指标id列表 */
  const metricIds = [];
  for (const variable of params) {
    const { related_metrics } = variable.config;
    if (related_metrics) {
      for (const metric of related_metrics) {
        /** 去重且已有指标详情列表中不含有该指标 */
        if (
          !metricIds.find(item => item.metric_id === metric.metric_id) &&
          !metricsDetail.find(item => item.metric_id === metric.metric_id)
        ) {
          metricIds.push(metric);
        }
      }
    }
  }

  /** 指标详情 */
  let metrics = metricsDetail;
  if (metricIds.length) {
    const details = await fetchMetricDetailList(metricIds);
    metrics = metrics.concat(details);
  }

  return params.map(item => {
    const {
      type,
      name,
      alias,
      description,
      config: { default: defaultValue, related_metrics, related_tag, options },
    } = item;

    let metric = null;
    if (related_metrics) {
      const [{ metric_id }] = related_metrics;
      metric = metrics.find(item => item.metric_id === metric_id);
    }

    return {
      name: `\${${name}}`,
      type,
      alias,
      description,
      defaultValue,
      metric,
      related_tag,
      options: options ? (options.length ? options : ['all']) : [],
    };
  });
}

export function getVariableModel(config: IVariableModel): VariableModelType {
  switch (config.type) {
    case VariableTypeEnum.METHOD:
      return new MethodVariableModel(config);
    case VariableTypeEnum.GROUP_BY:
      return new DimensionVariableModel(config);
    case VariableTypeEnum.TAG_VALUES:
      return new DimensionValueVariableModel(config);
    case VariableTypeEnum.FUNCTIONS:
    case VariableTypeEnum.EXPRESSION_FUNCTIONS:
      return new FunctionVariableModel(config);
    case VariableTypeEnum.CONDITIONS:
      return new ConditionVariableModel(config);
    case VariableTypeEnum.CONSTANTS:
      return new ConstantVariableModel(config);
  }
}

/** 获取变量接口提交参数结构 */
export function getVariableSubmitParams(variable: VariableModelType): IVariableSubmitParams {
  const { type, variableName, alias, description, defaultValue } = variable.data;
  let otherConfig = {};
  if (type === VariableTypeEnum.TAG_VALUES) {
    const { related_tag, metric } = variable.data;
    otherConfig = {
      related_metrics: [
        {
          metric_id: metric.metric_id,
          metric_field: metric.metric_field,
        },
      ],
      related_tag: related_tag,
      options: [],
    };
  }
  if (type === VariableTypeEnum.CONDITIONS || type === VariableTypeEnum.GROUP_BY) {
    const { metric } = variable.data;
    otherConfig = {
      related_metrics: [
        {
          metric_id: metric.metric_id,
          metric_field: metric.metric_field,
        },
      ],
      options: (variable as ConditionVariableModel | DimensionVariableModel).isAllDimensionOptions
        ? []
        : (variable as ConditionVariableModel | DimensionVariableModel).options,
    };
  }
  return {
    type,
    name: variableName,
    alias,
    description: description,
    config: {
      default: defaultValue,
      ...otherConfig,
    },
  };
}
