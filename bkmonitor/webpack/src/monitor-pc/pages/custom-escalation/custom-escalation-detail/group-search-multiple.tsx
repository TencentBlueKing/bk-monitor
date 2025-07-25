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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils';

import { matchRuleFn } from '../group-manage-dialog';

import './group-search-multiple.scss';

interface IListItem {
  disable?: boolean;
  id: string;
  name: string;
}
interface IProps {
  groupsMap?: Map<string, any>;
  list?: IListItem[];
  metricName?: string;
  onChange?: any;
  onToggle?: any;
  value?: string[];
}

@Component
export default class GroupSearchMultiple extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  @Prop({ default: () => [], type: Array }) value: string[];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: Map<string, any>;
  @Prop({ default: '', type: String }) metricName: string;
  @Ref('selectDropdown') selectDropdownRef: any;

  isDropdownOpen = false;
  localValue = [];
  localList = [];
  searchKeyword = ''; // 搜索关键词
  disabled: boolean;

  // 新增计算属性：过滤后的列表
  get filteredList() {
    if (!this.searchKeyword) return this.localList;
    const keyword = this.searchKeyword.toLowerCase();
    return this.localList.filter(item => item.name.toLowerCase().includes(keyword));
  }

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    this.localValue = v;
  }

  @Watch('list', { immediate: true, deep: true })
  handleListChange(list) {
    this.localList = list;
  }

  // 搜索输入处理
  handleSearchInput(v: string) {
    this.searchKeyword = v;
  }

  @Emit('change')
  emitValueChange() {
    return this.localValue;
  }

  @Emit('listChange')
  emitListChange() {
    return deepClone(this.localList);
  }

  handleClick() {
    if (this.disabled) return;
    this.selectDropdownRef?.show();
  }

  handleSelectChange() {
    this.emitValueChange();
  }

  getIsDisabel(key) {
    if (!this.metricName) return false;
    return this.groupsMap.get(key)?.matchRulesOfMetrics?.includes?.(this.metricName) || false;
  }

  getDisableTip(groupName) {
    const targetGroup = this.groupsMap.get(groupName);
    let targetRule = '';
    targetGroup?.matchRules?.forEach(rule => {
      if (!targetRule && matchRuleFn(this.metricName, rule)) {
        targetRule = rule;
      }
    });
    return targetRule;
  }

  @Emit('toggle')
  handleToggle(v: boolean) {
    this.isDropdownOpen = v;
    // this.$emit('', v, deepClone(this.localList));
    return v;
  }

  render() {
    return (
      <span
        class='group-search-multiple-component'
        onClick={this.handleClick}
      >
        <span class={['btn-content', this.isDropdownOpen ? 'active' : '']}>{this.$slots?.default}</span>
        <bk-select
          ref='selectDropdown'
          class='select-dropdown'
          v-model={this.localValue}
          ext-popover-cls={'group-search-multiple-component-dropdown-content'}
          popover-min-width={162}
          multiple
          searchable
          onSearchChange={this.handleSearchInput} // 搜索事件
          onSelected={this.handleSelectChange}
          onToggle={this.handleToggle}
        >
          {/* 搜索框 */}
          <div
            class='custom-search-header'
            slot='header'
          >
            <bk-input
              placeholder='搜索...'
              value={this.searchKeyword}
              clearable
              onInput={this.handleSearchInput}
            />
          </div>

          {this.filteredList.map(
            (
              item,
              index // 改为使用过滤后的列表
            ) => (
              <bk-option
                id={item.id}
                key={index}
                v-bk-tooltips={
                  !this.getIsDisabel(item.id)
                    ? { disabled: true }
                    : {
                        content: this.$t('由匹配规则{0}生成', [this.getDisableTip(item.id)]),
                        placements: ['right'],
                        boundary: 'window',
                        allowHTML: false,
                      }
                }
                disabled={this.getIsDisabel(item.id)}
                name={item.name}
              />
            )
          )}
          <div
            style='cursor: pointer'
            slot='extension'
          >
            {this.$slots?.extension}
          </div>
        </bk-select>
      </span>
    );
  }
}
