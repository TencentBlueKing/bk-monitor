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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';

import { SEARCH_SELECT_OPTIONS } from '../../constants';

import type { QueryListRequestParams, SearchSelectItem } from '../../typings';

import '@blueking/search-select-v3/vue2/vue2.css';

interface QueryTemplateSearchEmits {
  onChange: (list: QueryListRequestParams['conditions']) => void;
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
      acc[cur.id] = cur;
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
      id: e.key,
      values: e.value.map(v => ({ id: v, name: v })),
    }));
  }

  @Emit('change')
  handleSearchChange(list: SearchSelectItem[]) {
    if (!list?.length) {
      return [];
    }
    const map = new Map(
      list.map(item => {
        let key = item.id;
        let val = item;
        if (item?.type === 'text') {
          key = 'query';
          val = {
            id: 'query',
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
        key: item.id,
        value: item.values.map(v => v.id),
      });
    }
    return search;
  }

  render() {
    return (
      <SearchSelect
        class='query-template-search'
        clearable={true}
        data={SEARCH_SELECT_OPTIONS}
        modelValue={this.searchSelectValue}
        placeholder={this.$t('搜索 模板名称、模板别名、模板说明、创建人、更新人')}
        onChange={this.handleSearchChange}
      />
    );
  }
}
