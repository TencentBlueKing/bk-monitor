/* eslint-disable @typescript-eslint/naming-convention */
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

import type { ConsitionItem } from './store.type';

class ConditionOperator {
  item: ConsitionItem;
  relationList = [];
  containOperatorList = [];

  // 判定是否属于启用通配符的操作符列表
  wildcardList = [];
  textMappingKey = {};
  allContainsStrList = [];
  containsStrList = [];

  constructor(item: ConsitionItem) {
    this.item = item;
    this.relationList = ['AND', 'OR', 'and', 'or'];
    this.containOperatorList = ['contains match phrase', '=~', 'not contains match phrase', '!=~'];
    this.wildcardList = ['&!=~', '!=~', '&=~', '=~'];

    /** text类型字段类型给到检索参数时的映射 */
    this.textMappingKey = {
      is: 'contains match phrase',
      'is not': 'not contains match phrase',
      'and is': 'all contains match phrase',
      'and is not': 'all not contains match phrase',
      'is match': '=~',
      'is not match': '!=~',
      'and is match': '&=~',
      'and is not match': '&!=~',
    };

    /** 所有的包含,非包含情况下的类型操作符字符串 */
    this.allContainsStrList = Object.values(this.textMappingKey);

    /**
     * 包含情况下的text类型操作符
     * operator: contains
     */
    this.containsStrList = ['contains match phrase', '=~', 'all contains match phrase', '&=~'];
  }

  /** 当前text字段类型操作符对应且/或的值 */
  get operatorRelationVlaue() {
    if (this.relationList.includes(this.item.relation)) {
      return this.item.relation;
    }

    return this.containOperatorList.includes(this.item.operator) ? 'OR' : 'AND';
  }

  /**
   * 是否启用通配符
   */
  get isWildcardMatch() {
    if (typeof this.item.isInclude === 'boolean') {
      return this.item.isInclude;
    }

    return this.wildcardList.includes(this.item.operator);
  }

  /**
   * 是否为全文检索
   */
  get isFulltextField() {
    return this.item.field === '*';
  }

  /** 获取text类型操作符所需的值 */
  FormatOpetatorFrontToApi() {
    // 如果是全文检索这里不做任何处理
    if (this.isFulltextField) {
      return this.item.operator;
    }

    // 在前端的逻辑中，只有Text String类型的字段才支持配置是否启用通配符
    if (
      this.containOperatorList.includes(this.item.operator) &&
      (['text', 'string'].includes(this.item.field_type) || /^and$/i.test(this.operatorRelationVlaue))
    ) {
      let value = '';
      // 首先判断是且还是或 如果是且则先加一个and
      value = this.operatorRelationVlaue === 'AND' ? 'and ' : '';

      // 然后判断是包含还是不包含操作符
      value += this.item.operator === 'contains match phrase' ? 'is ' : 'is not ';

      // 最后判断是否有开打开通配符
      value += this.isWildcardMatch ? 'match' : '';

      return this.textMappingKey[value.trim()];
    }

    return this.item.operator;
  }

  /** 前端展示转换 */
  getShowCondition() {
    // allContainsStrList 列表中包含的操作关系说明是 string | text 字段类型
    // 这些类型需要反向解析 FormatOpetatorFrontToApi 方法生成的语法
    if (!this.isFulltextField && this.allContainsStrList.includes(this.item.operator)) {
      const value = this.allContainsStrList.find(valueItem => valueItem === this.item.operator);
      // this.containOperatorList 列表中所包含的操作关系说明是 OR 操作
      // OR 操作才支持这些查询,已有组间关系则不通过操作符判断
      const relation = ['AND', 'OR'].includes(this.item.relation?.toLocaleUpperCase())
        ? this.item.relation
        : this.containOperatorList.includes(value)
          ? 'OR'
          : 'AND';

      // 包含和不包含操作符只有这两种，其他逻辑不走这个分支
      const operator = this.containsStrList.includes(value) ? 'contains match phrase' : 'not contains match phrase';

      return {
        operator,
        relation,
        field: this.item.field,
        isInclude: this.isWildcardMatch,
        value: Array.isArray(this.item.value) ? this.item.value : [this.item.value],
        hidden_values: this.item.hidden_values ?? [],
        disabled: this.item.disabled ?? false,
      };
    }
  }

  /**
   * 格式化接口拿到的查询关系解析成组件可以适配的数据结构
   * @param isInitializing 是否为初始化,初始化不改变operator
   * @returns
   */
  formatApiOperatorToFront(isInitializing = false) {
    // allContainsStrList 列表中包含的操作关系说明是 string | text 字段类型
    // 这些类型需要反向解析 FormatOpetatorFrontToApi 方法生成的语法
    if (!this.isFulltextField && this.allContainsStrList.includes(this.item.operator)) {
      const newValue = this.allContainsStrList.find(valueItem => valueItem === this.item.operator);

      // this.containOperatorList 列表中所包含的操作关系说明是 OR 操作
      // OR 操作才支持这些查询
      const newRelation = ['AND', 'OR'].includes(this.item.relation?.toLocaleUpperCase())
        ? this.item.relation
        : this.containOperatorList.includes(newValue)
          ? 'OR'
          : 'AND';

      // 如果是通配符这里不做转换
      if (this.wildcardList.includes(newValue) || isInitializing) {
        return {
          operator: newValue,
          relation: newRelation,
          field: this.item.field,
          isInclude: this.isWildcardMatch,
          value: Array.isArray(this.item.value) ? this.item.value : [this.item.value],
          hidden_values: this.item.hidden_values ?? [],
          disabled: this.item.disabled ?? false,
        };
      }

      // 包含和不包含操作符只有这两种，其他逻辑不走这个分支
      const newOperator = this.containsStrList.includes(newValue)
        ? 'contains match phrase'
        : 'not contains match phrase';

      return {
        operator: newOperator,
        relation: newRelation,
        field: this.item.field,
        isInclude: this.isWildcardMatch,
        value: Array.isArray(this.item.value) ? this.item.value : [this.item.value],
        hidden_values: this.item.hidden_values ?? [],
        disabled: this.item.disabled ?? false,
      };
    }

    const {
      operator,
      field,
      value,
      isInclude = null,
      relation = 'OR',
      hidden_values = [],
      disabled = false,
    } = this.item;
    return {
      relation,
      operator,
      field,
      value: Array.isArray(value) ? value : [value],
      isInclude,
      hidden_values,
      disabled,
    };
  }

  /**
   * 获取API请求所需要的的参数
   */
  getRequestParam() {
    return {
      field: this.item.field,
      operator: this.FormatOpetatorFrontToApi(),
      value: Array.isArray(this.item.value) ? this.item.value : [this.item.value],
      hidden_values: this.item.hidden_values ?? [],
      disabled: this.item.disabled ?? false,
    };
  }
}

export { ConditionOperator };
