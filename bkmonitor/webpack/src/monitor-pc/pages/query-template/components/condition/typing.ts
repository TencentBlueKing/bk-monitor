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
import type { ECondition, EMethod } from '../../../../components/retrieval-filter/utils';

export enum EFieldType {
  all = 'all',
  custom_operator = 'custom_operator', // 自定义操作列 之站位不提供内容
  date = 'date',
  integer = 'integer',
  keyword = 'keyword',
  text = 'text',
  variable = 'variable',
}

export interface IFieldItem {
  /* 字段别名 */
  alias: string;
  /* 字段名 */
  field: string;
  /* 是否含有可选项选项 */
  isEnableOptions: boolean;
  /* 包含的method */
  methods: IValue[];
  type?: EFieldType;
}

/* 可选数据格式 */
export interface IFilterField {
  alias: string;
  is_dimensions?: boolean;
  is_option_enabled: boolean; // 是否可自定选项
  name: string;
  type: EFieldType;
  supported_operations: {
    alias: string;
    options?: {
      label: string;
      name: string;
    };
    value: EMethod;
  }[]; // 支持的操作
}

export interface IFilterItem {
  condition: { id: ECondition; name: string };
  hide?: boolean;
  isSetting?: boolean; // 是否是设置项
  key: { id: string; name: string };
  method: { id: EMethod | string; name: string };
  value: { id: string; name: string }[];
  options?: {
    is_wildcard?: boolean;
    isVariable?: boolean;
  };
}

interface IValue {
  id: string;
  name: string;
}
