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

import { IItem } from '../threshold/threshold-select';

import { BoundType } from './alarm-threshold-select';

type FormItemType =
  | 'select'
  | 'number'
  | 'string'
  | 'thresholds'
  | 'model-select'
  | 'switch'
  | 'input-unit'
  | 'tag-input'
  | 'range'
  | 'alarm-thresholds'
  | 'ai-level';

export interface ISelectOptionItem {
  id: string;
  name: string;
  default?: boolean; // 是否为默认
  loading?: boolean; // 数据加在状态
  detail?: Record<string, any>; // 模型数据详情
}
export interface IUnitOptionItem {
  id: number;
  name: string;
}
type IBehavior = 'normal' | 'simplicity';

export enum EFormItemValueType {
  string = 'string',
  number = 'number',
  array = 'array'
}

type TValueType = EFormItemValueType.number | EFormItemValueType.string | EFormItemValueType.array;

type errorDisplayType = 'tooltips' | 'normal';

export interface IFormDataItem {
  label: string;
  field: string;
  value: any;
  default?: any;
  type: FormItemType;
  options?: ISelectOptionItem[];
  min?: number;
  max?: number;
  unit?: string;
  methodList?: IItem[];
  behavior?: IBehavior;
  required?: boolean;
  onChange?: (item: FormItem) => void;
  placeholder?: string;
  disabled?: boolean;
  multiple?: boolean;
  valueType?: TValueType;
  clearable?: boolean;
  hoverOptionId?: string;
  width?: number;
  unitOption?: IUnitOptionItem[]; // 单位可选值
  unitId?: number; // 单位换倍数
  description?: string;
  boundType?: BoundType; // 告警阈值类型
  errorDisplayType?: errorDisplayType;
  isAdvanced?: boolean; // 是否隐藏参数组件，但是要提交默认值给后台
  separator?: string; // 多选的分隔符
}
/** 时序预测表单组件数据结构 */
export class FormItem {
  label = ''; // 表单label
  field = ''; // 提交字段
  value: any = ''; // 值
  default?: any = ''; // 默认值
  type: FormItemType = 'string'; // 表单组件类型
  options: ISelectOptionItem[] = []; // 下拉可选项数据
  min?: number; // 最小值
  max?: number; // 最大值
  unit?: string; // 阈值单位
  methodList?: IItem[]; // 阈值方法列表
  behavior?: IBehavior; // 组件的样式模式
  required?: boolean; // 是否必选
  onChange?: (item: FormItem) => void; /** 组件值更新回调 */
  placeholder?: string; // 提示
  disabled?: boolean; // 禁用
  multiple?: boolean; // 是否可以多选
  valueType?: TValueType; // 接口所需类型
  clearable?: boolean; // 是否可清除
  hoverOptionId?: string = null; // hover选项的id
  width?: number; // 组件宽度
  unitOption?: IUnitOptionItem[]; // 单位可选值
  unitId?: number; // 单位换倍数
  description?: string; // 表单描述
  boundType?: BoundType; // 告警阈值类型
  errorDisplayType?: errorDisplayType; // 表单项错误提示的方式
  isAdvanced?: boolean; // 是否隐藏参数组件，但是要提交默认值给后台
  separator?: string; // 多选的分隔符

  constructor(data: IFormDataItem) {
    if (!!data) {
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
  /**
   * 根据模型接口数据生成表单所需数据
   * @param data 接口数据
   * @param valueDisplay 回填的value值
   * @returns Array<bk-form-item>
   */
  // eslint-disable-next-line @typescript-eslint/member-ordering
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
          is_required
        }
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
            name: item.allowed_alias
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
        required: is_required ?? false
      };
      return new FormItem(res);
    });
    return formItemList;
  }
  /**
   * 根据模型参数接口的所需类型进行转换
   * @param valueType 数据所需类型
   * @param value 值
   * @returns 转换后的值
   */
  // eslint-disable-next-line @typescript-eslint/member-ordering
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
  }
}

/** 获取模型描述信息 */
export const handleCreateModelOptionsDetail = (item: any, interval: number) => ({
  name: item.name,
  releaseId: item.latest_release_id,
  description: {
    dataLength: {
      value: item.ts_depend,
      isMatch: true
    },
    frequency: {
      value: item.ts_freq,
      isMatch: item.ts_freq === 0 ? true : interval === item.ts_freq.value
    },
    message: {
      value: item.description,
      isMatch: true
    }
  },
  instruction: item.instruction || ''
});
