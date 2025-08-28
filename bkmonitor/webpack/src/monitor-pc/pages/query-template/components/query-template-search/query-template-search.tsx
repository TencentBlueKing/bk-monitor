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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { SEARCH_SELECT_OPTIONS } from '../../constants';

import type { QueryListRequestParams, SearchSelectItem } from '../../typings';

interface QueryTemplateSearchEmits {
  onChange: (list: QueryListRequestParams['conditions']) => void;
  onSearch: () => void;
}
type QueryTemplateSearchProps = {
  searchKeyword: QueryListRequestParams['conditions'];
};

@Component
export default class QueryTemplateSearch extends tsc<QueryTemplateSearchProps, QueryTemplateSearchEmits> {
  @Prop({ type: Array, default: () => [] }) searchKeyword!: QueryListRequestParams['conditions'];

  /** 所有可搜索项信息映射表 */
  get allSearchSelectOptionMap() {
    return SEARCH_SELECT_OPTIONS.reduce((acc, cur) => {
      acc[cur.key] = cur;
      return acc;
    }, {});
  }

  /** 将传入的接口所需结构转换为搜索选择器所需结构数据 */
  get searchSelectValue() {
    if (!this.searchKeyword?.length) {
      return [];
    }
    return this.searchKeyword?.map(e => ({
      name: this.allSearchSelectOptionMap[e.key]?.name,
      key: e.key,
      values: e.value.map(v => ({ key: v, name: v })),
    }));
  }

  @Emit('search')
  handleRefresh() {
    return;
  }

  @Emit('change')
  handleSearchChange(list: SearchSelectItem[]) {
    if (!list?.length) {
      return [];
    }
    const map = new Map(
      list.map(item => {
        let key = item.key;
        let val = item;
        if (!Object.hasOwn(item, 'values')) {
          key = 'query';
          val = {
            key: 'query',
            name: this.$i18n.t('全文检索') as unknown as string,
            values: [item],
          };
        }
        return [key, val];
      })
    );
    const keys = map.keys();
    const search = [];
    for (const key of keys) {
      const item = map.get(key);
      if (!item) {
        continue;
      }
      search.push({
        key: item.key,
        value: item.values.map(v => v.key),
      });
    }
    return search;
  }

  render() {
    return (
      <bk-search-select
        class='query-template-search'
        clearable={true}
        data={SEARCH_SELECT_OPTIONS}
        placeholder={this.$t('搜索 模板名称、模板别名、模板说明、创建人、更新人')}
        primary-key='key'
        show-condition={false}
        values={this.searchSelectValue}
        onChange={this.handleSearchChange}
        onClear={() => this.handleSearchChange([])}
        onSearch={this.handleRefresh}
      />
    );
  }
}
