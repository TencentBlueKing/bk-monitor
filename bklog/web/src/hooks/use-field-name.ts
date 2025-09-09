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

import { BK_LOG_STORAGE, FieldInfoItem } from '../store/store.type';

/**
 * 根据字段信息返回别名
 * @param field 字段信息
 * @param store
 * @returns 返回别名，如果没有别名则返回字段名
 */
export const getFieldNameByField = (field, store) => {
  if (store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
    return field.query_alias || field.field_name;
  }

  return field.field_name;
};

export default ({ store }) => {
  /**
   * 根据字段名返回别名
   * @param name  字段名field_name
   * @returns 返回别名，如果没有别名则返回字段名
   */
  const getFieldName = (name: string) => {
    if (store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
      const field = store.state.indexFieldInfo.fields.filter(item => item.field_name === name);
      return field[0]?.query_alias || name;
    }
    return name;
  };

  const mGetFieldNameByField = (field: { field_name: string; query_alias: string }) => {
    return getFieldNameByField(field, store);
  };

  /**
   * 根据字段列表返回别名数组
   * @param fields  字段列表
   * @returns 返回别名数组，如果没有别名则返回字段名
   */
  const getFieldNames = (fields: any) => {
    if (store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
      return fields.map(fieldInfo => fieldInfo.query_alias || fieldInfo.field_name);
    }
    return fields.map(fieldInfo => fieldInfo.field_name);
  };

  /**
   * 根据字段信息返回拼接字段名
   * @param fields  字段信息
   * @returns 返回拼接字段名
   */
  const getConcatenatedFieldName = (fields: any) => {
    const { field_name: id, field_alias: alias, query_alias: query } = fields;
    if (store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS] && query) {
      return { id, name: `${query}(${alias || id})` };
    }
    return { id, name: alias ? `${id}(${alias})` : id };
  };
  /**
   * 根据字段信息返回别名
   * @param fields  字段信息
   * @returns 返回别名
   */
  const getQueryAlias = (field: any) => {
    return store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
      ? field.query_alias || field.field_name
      : field.field_name;
  };

  const getFieldList = (withAliasFieldMap = false) => {
    if (withAliasFieldMap) {
      return [].concat(store.state.indexFieldInfo.fields, store.state.indexFieldInfo.alias_field_list);
    }
    return store.state.indexFieldInfo.fields;
  };

  /**
   * 根据别名返回字段名
   * @param name  别名query_alias
   * @returns 返回字段名，如果没有字段名则返回别名
   */
  const changeFieldName = (name: string, list?: FieldInfoItem[], withAliasFieldMap = false) => {
    const field = (list || getFieldList(withAliasFieldMap)).filter(item => item.query_alias === name);
    return field[0]?.field_name || name;
  };
  /**
   * 根据字段名返回拼接字段名
   * @param name  字段名field_name
   * @returns 返回拼接字段名
   */
  const getQualifiedFieldName = (field_name: string, list?: FieldInfoItem[], withAliasFieldMap = false) => {
    const field = (list || getFieldList(withAliasFieldMap)).filter(item => item.field_name === field_name);
    if (field[0].query_alias) {
      return `${field[0].query_alias}(${field_name})`;
    }
    return field_name;
  };

  /**
   * 根据字段名返回拼接字段名
   * @param field_name
   * @param list
   * @param withAliasFieldMap
   * @param attrs
   * @returns
   */
  const getQualifiedFieldAttrs = (
    field_name: string,
    list?: FieldInfoItem[],
    withAliasFieldMap = false,
    attrs: string[] = [],
  ) => {
    const field = (list || getFieldList(withAliasFieldMap)).find(item => item.field_name === field_name);
    const reduceFn = (acc, attr) => {
      if (attr !== 'field_name') {
        acc[attr] = field[attr];
      }
      return acc;
    };
    if (field?.query_alias) {
      return attrs.reduce(reduceFn, { field_name: `${field.query_alias}(${field_name})` });
    }
    return attrs.reduce(reduceFn, { field_name });
  };

  return {
    getFieldName,
    getFieldNames,
    getConcatenatedFieldName,
    getQueryAlias,
    changeFieldName,
    getFieldNameByField: mGetFieldNameByField,
    getQualifiedFieldName,
    getQualifiedFieldAttrs,
  };
};
