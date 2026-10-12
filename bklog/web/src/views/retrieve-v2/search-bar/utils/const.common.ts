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

/**
 * 全文检索操作符
 * 这里是固定的，只支持包含操作
 */
export const FulltextOperator = 'contains match phrase';

/**
 * 全文检索时，默认生成的查询数据结构
 * @param value
 * @returns
 */
export const getInputQueryDefaultItem = (value: string[] = []) => {
  return {
    field: '*',
    operator: FulltextOperator,
    isInclude: false,
    value: [...(Array.isArray(value) ? value : [value])],
    relation: 'OR',
    disabled: false,
    hidden_values: [],
  };
};

export const getInputQueryIpSelectItem = value => {
  return {
    field: '_ip-select_',
    operator: '',
    isInclude: false,
    value: [value ?? {}],
    relation: '',
    disabled: false,
    hidden_values: [],
  };
};
/**
 * 字段检索条件配置默认数据结构
 * @returns
 */
export const getFieldConditonItem = () => {
  return {
    field_name: '*',
    field_type: null,
    field_alias: null,
    field_id: null,
    field_operator: [],
    disabled: false,
    hidden_values: [],
  };
};

/**
 * 全文检索操作符字典Key
 */
export const FulltextOperatorKey = '*contains match phrase';

// 需要排除的字段
export const excludesFields = ['__ext', '__module__', ' __set__', '__ipv6__'];

// 无需配置值（Value）的条件列表
export const withoutValueConditionList = ['does not exists', 'exists', 'is false', 'is true'];
