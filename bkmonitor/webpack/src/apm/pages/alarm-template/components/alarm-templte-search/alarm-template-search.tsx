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

import { SEARCH_SELECT_OPTIONS } from '../../constant';

import type { AlarmTemplateConditionParamItem, AlarmTemplateField, AlarmTemplateOptionsItem } from '../../typing';
import type { SearchSelectItem } from 'monitor-pc/pages/query-template/typings';

import '@blueking/search-select-v3/vue2/vue2.css';

interface AlarmTemplateSearchEmits {
  /** 搜索选择器值变化时触发 */
  onChange: (keyword: AlarmTemplateConditionParamItem[]) => void;
}
type AlarmTemplateSearchProps = {
  /** 搜索关键字 */
  searchKeyword: AlarmTemplateConditionParamItem[];
  /** 候选值映射表 */
  selectOptionMap: Record<AlarmTemplateField, AlarmTemplateOptionsItem[]>;
};

@Component
export default class AlarmTemplateSearch extends tsc<AlarmTemplateSearchProps, AlarmTemplateSearchEmits> {
  /** 搜索关键字 */
  @Prop({ type: Array, default: () => [] }) searchKeyword!: AlarmTemplateConditionParamItem[];
  /** 候选值映射表 */
  @Prop({ type: Object, default: () => {} }) selectOptionMap: Record<AlarmTemplateField, AlarmTemplateOptionsItem[]>;

  get searchSelectData() {
    return (
      SEARCH_SELECT_OPTIONS.map(e => {
        const obj = { ...e };
        const options = this.selectOptionMap?.[obj.id];
        if (options?.length) {
          obj.children = options;
        }
        return obj;
      }) || []
    );
  }

  /** 所有可搜索项信息映射表 */
  get allSearchSelectOptionMap() {
    return this.searchSelectData.reduce((acc, cur) => {
      acc[cur.id] = {
        ...cur,
        childrenMap: cur?.children?.reduce?.((prev, curr) => {
          prev[curr.id] = curr;
          return prev;
        }, {}),
      };
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
      values: e.value.map(v => ({ id: v, name: this.allSearchSelectOptionMap[e.key]?.childrenMap?.[v]?.name ?? v })),
    }));
  }

  /**
   * @description 搜索选择器值变化时触发(将搜索选择器值转换为外层接口所需结构)
   * @param {SearchSelectItem[]} list
   * @returns {AlarmTemplateConditionParamItem[]} keyword-外层请求接口时筛选值属性所需结构
   */
  @Emit('change')
  handleSearchChange(list: SearchSelectItem[]): AlarmTemplateConditionParamItem[] {
    if (!list?.length) {
      return [];
    }
    // 利用Map结构key重复值覆盖特性，进行去重并保证值为最新值
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

    // 开始转换为所需数据结构
    const keys = map.keys();
    const keyword = [];
    for (const key of keys) {
      const item = map.get(key);
      if (!item) {
        continue;
      }
      keyword.push({
        key: item.id,
        value: item.values.map(v => v.id),
      });
    }
    return keyword;
  }

  render() {
    return (
      <SearchSelect
        class='alarm-template-search'
        clearable={true}
        data={this.searchSelectData}
        modelValue={this.searchSelectValue}
        placeholder={this.$t('搜索 模板名称、模板类型、最近更新人、关联服务、告警组、启停')}
        uniqueSelect={true}
        onChange={this.handleSearchChange}
      />
    );
  }
}
