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
export type FieldItem = {
  field_type: string;
  field_name: string;
  field_alias: string;
  is_display: boolean;
  is_editable: boolean;
  tag: string;
  origin_field: string;
  es_doc_values: boolean;
  is_analyzed: boolean;
  is_virtual_obj_node: boolean;
  field_operator: string[]; // 使用 `any[]` 可以存储任意类型的数组，如果有特定类型可以进一步细化
  is_built_in: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars: string;
  description: string;
  filterVisible: boolean;
  query_alias: string;
};

/**
 * 格式化层级结构
 * @param field
 */
export const formatHierarchy = (fieldList: Partial<FieldItem>[]) => {
  const result: Partial<FieldItem>[] = [];
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
const buildNewField = (field: Partial<FieldItem>, fieldName: string) => {
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
