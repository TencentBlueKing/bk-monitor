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

import type { IItem } from '../threshold/threshold-select';
import type { BoundType } from './alarm-threshold-select';

export enum EFormItemValueType {
  array = 'array',
  number = 'number',
  string = 'string',
}

export interface IFormDataItem {
  behavior?: IBehavior;
  boundType?: BoundType; // 告警阈值类型
  clearable?: boolean;
  default?: any;
  description?: string;
  disabled?: boolean;
  errorDisplayType?: errorDisplayType;
  field: string;
  hoverOptionId?: string;
  isAdvanced?: boolean; // 是否隐藏参数组件，但是要提交默认值给后台
  label: string;
  max?: number;
  methodList?: IItem[];
  min?: number;
  multiple?: boolean;
  options?: ISelectOptionItem[];
  placeholder?: string;
  required?: boolean;
  separator?: string; // 多选的分隔符
  type: FormItemType;
  unit?: string;
  unitId?: number; // 单位换倍数
  unitOption?: IUnitOptionItem[]; // 单位可选值
  value: any;
  valueType?: TValueType;
  width?: number;
  onChange?: (item: FormItem) => void;
}
export interface ISelectOptionItem {
  default?: boolean; // 是否为默认
  detail?: Record<string, any>; // 模型数据详情
  id: string;
  loading?: boolean; // 数据加在状态
  name: string;
}
export interface IUnitOptionItem {
  id: number;
  name: string;
}

type errorDisplayType = 'normal' | 'tooltips';

type FormItemType =
  | 'ai-level'
  | 'alarm-thresholds'
  | 'input-unit'
  | 'model-select'
  | 'number'
  | 'range'
  | 'select'
  | 'string'
  | 'switch'
  | 'tag-input'
  | 'thresholds';

type IBehavior = 'normal' | 'simplicity';

type TValueType = EFormItemValueType.array | EFormItemValueType.number | EFormItemValueType.string;
/** 时序预测表单组件数据结构 */
export class FormItem {
  static createFormItemData(data, valueDisplay?: Record<string, any>) {
    const { args } = data;
    const formItemList: FormItem[] = args.map(item => {
      const {
        variable_alias,
        variable_name,
        default_value,
        value_type,
        description,
        properties: {
          input_type,
          allowed_values_map,
          max,
          min,
          placeholder,
          allow_modified,
          multiple,
          separator,
          is_advanced,
          is_required,
        },
      } = item;
      const res: IFormDataItem = {
        label: variable_alias,
        field: variable_name,
        value: valueDisplay?.[variable_name] ?? default_value,
        default: default_value,
        type: ['double', 'int'].includes(input_type) ? 'number' : input_type,
        options:
          allowed_values_map?.map?.(item => ({
            id: item.allowed_value,
            name: item.allowed_alias,
          })) || [],
        min,
        max,
        placeholder,
        disabled: !(allow_modified ?? true),
        multiple: multiple ?? false,
        valueType: ['double', 'int'].includes(value_type) ? EFormItemValueType.number : EFormItemValueType.string,
        description,
        separator: separator ?? '',
        isAdvanced: is_advanced ?? false,
        required: is_required ?? false,
      };
      return new FormItem(res);
    });
    return formItemList;
  } // 表单label

  static handleValueType(item: FormItem) {
    const { valueType, value } = item;
    const localValue = value;
    switch (valueType) {
      case EFormItemValueType.number:
        return Number(localValue);
      case EFormItemValueType.string:
        return String(localValue);
      case EFormItemValueType.array:
        return Array.isArray(localValue) ? localValue : [];
      default:
        return localValue;
    }
  } // 提交字段
  behavior?: IBehavior; // 值
  boundType?: BoundType; // 默认值
  clearable?: boolean; // 表单组件类型
  default?: any = ''; // 下拉可选项数据
  description?: string; // 最小值
  disabled?: boolean; // 最大值
  errorDisplayType?: errorDisplayType; // 阈值单位
  field = ''; // 阈值方法列表
  hoverOptionId?: string = null; // 组件的样式模式
  isAdvanced?: boolean; // 是否必选
  label = ''; /** 组件值更新回调 */
  max?: number; // 提示
  methodList?: IItem[]; // 禁用
  min?: number; // 是否可以多选
  multiple?: boolean; // 接口所需类型
  onChange?: (item: FormItem) => void; // 是否可清除
  options: ISelectOptionItem[] = []; // hover选项的id
  placeholder?: string; // 组件宽度
  required?: boolean; // 单位可选值
  separator?: string; // 单位换倍数
  type: FormItemType = 'string'; // 表单描述
  unit?: string; // 告警阈值类型
  unitId?: number; // 表单项错误提示的方式
  unitOption?: IUnitOptionItem[]; // 是否隐藏参数组件，但是要提交默认值给后台
  value: any = ''; // 多选的分隔符

  valueType?: TValueType;
  /**
   * 根据模型接口数据生成表单所需数据
   * @param data 接口数据
   * @param valueDisplay 回填的value值
   * @returns Array<bk-form-item>
   */
  width?: number;
  /**
   * 根据模型参数接口的所需类型进行转换
   * @param valueType 数据所需类型
   * @param value 值
   * @returns 转换后的值
   */
  constructor(data: IFormDataItem) {
    if (data) {
      this.label = data.label ?? '';
      this.field = data.field ?? '';
      this.value = data.value ?? '';
      this.default = data.default;
      this.type = data.type ?? 'string';
      this.options = data.options ?? [];
      this.min = data.min;
      this.max = data.max;
      this.unit = data.unit ?? '';
      this.methodList = data.methodList;
      this.behavior = data.behavior ?? 'normal';
      this.required = data.required ?? false;
      this.onChange = data.onChange;
      this.placeholder = data.placeholder;
      this.disabled = data.disabled;
      this.multiple = data.multiple;
      this.valueType = data.valueType;
      this.clearable = data.clearable ?? true;
      this.width = data.width;
      this.unitOption = data.unitOption ?? [];
      this.unitId = data.unitId ?? 1;
      this.description = data.description ?? '';
      this.boundType = data.boundType ?? 'middle';
      this.errorDisplayType = data.errorDisplayType ?? 'normal';
      this.isAdvanced = data.isAdvanced ?? false;
      this.separator = data.separator ?? '';
    }
  }
}

/** 获取模型描述信息 */
export const handleCreateModelOptionsDetail = (item: any, interval: number) => ({
  name: item.name,
  releaseId: item.latest_release_id,
  description: {
    dataLength: {
      value: item.ts_depend,
      isMatch: true,
    },
    frequency: {
      value: item.ts_freq,
      isMatch: item.ts_freq === 0 ? true : interval === item.ts_freq.value,
    },
    message: {
      value: item.description,
      isMatch: true,
    },
  },
  instruction: item.instruction || '',
});
