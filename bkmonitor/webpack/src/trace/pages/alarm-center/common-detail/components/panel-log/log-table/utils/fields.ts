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

import type { IFieldInfo } from '../typing';

/**
 * 格式化层级结构
 * @param field
 */
export const formatHierarchy = (fieldList: Partial<IFieldInfo>[]) => {
  const result: Partial<IFieldInfo>[] = [];
  for (const field of fieldList) {
    const splitList = field.field_name.split('.');

    if (splitList.length === 1) {
      result.push(field);
      continue;
    }

    const leftName: string[] = [];

    for (const name of splitList) {
      leftName.push(name);
      const fieldName = leftName.join('.');
      if (result.findIndex(item => item.field_name === fieldName) === -1) {
        result.push(buildNewField(field, fieldName));
      }
    }
  }

  return result;
};
const buildNewField = (field: Partial<IFieldInfo>, fieldName: string) => {
  const isSameName = fieldName === field.field_name;
  const fieldAlias = isSameName ? field.field_alias : fieldName;
  const fieldType = isSameName ? field.field_type : 'object';
  const queryAlias = isSameName ? field.query_alias : fieldName;
  return {
    ...field,
    field_name: fieldName,
    field_alias: fieldAlias,
    is_virtual_obj_node: !isSameName,
    field_type: fieldType,
    query_alias: queryAlias,
  };
};
