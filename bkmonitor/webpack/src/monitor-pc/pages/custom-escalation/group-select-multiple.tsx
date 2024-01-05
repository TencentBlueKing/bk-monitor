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

import { matchRuleFn } from './group-manage-dialog';

import './group-select-multiple.scss';

interface IListItem {
  id: string;
  name: string;
  disable?: boolean;
}
interface IProps {
  list?: IListItem[];
  value?: string[];
  groupsMap?: Map<string, any>;
  metricName?: string;
  onChange?: any;
  onToggle?: any;
}

@Component
export default class GroupSelectMultiple extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  @Prop({ default: () => [], type: Array }) value: string[];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: Map<string, any>;
  @Prop({ default: '', type: String }) metricName: string;
  @Ref('selectDropdown') selectDropdownRef: any;

  localValue = [];
  localList = [];

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    this.localValue = v;
  }

  @Watch('list', { immediate: true, deep: true })
  handleListChange(list) {
    this.localList = list;
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

  /* 是否为匹配规则匹配的选项 */
  getIsDisabel(key) {
    if (!this.metricName) {
      return false;
    }
    return this.groupsMap.get(key)?.matchRulesOfMetrics?.includes?.(this.metricName) || false;
  }
  /* 由匹配规则生成的tip */
  getDisableTip(groupName) {
    const targetGroup = this.groupsMap.get(groupName);
    let targetRule = '';
    targetGroup?.matchRules?.forEach(rule => {
      if (!targetRule) {
        if (matchRuleFn(this.metricName, rule)) {
          targetRule = rule;
        }
      }
    });
    return targetRule;
  }

  @Emit('toggle')
  handleToggle(v: Boolean) {
    return v;
  }

  render() {
    return (
      <span
        class='group-select-multiple-component'
        onClick={this.handleClick}
      >
        <span class='btn-content'>{this.$slots?.default}</span>
        <bk-select
          ext-popover-cls={'group-select-multiple-component-dropdown-content'}
          class='select-dropdown'
          ref='selectDropdown'
          v-model={this.localValue}
          popover-min-width={162}
          multiple
          onSelected={this.handleSelectChange}
          onToggle={this.handleToggle}
        >
          {this.list.map((item, index) => (
            <bk-option
              key={index}
              id={item.id}
              name={item.name}
              disabled={this.getIsDisabel(item.id)}
              v-bk-tooltips={
                !this.getIsDisabel(item.id)
                  ? { disabled: true }
                  : {
                      content: this.$t('由匹配规则{0}生成', [this.getDisableTip(item.id)]),
                      placements: ['right'],
                      boundary: 'window',
                      allowHTML: false
                    }
              }
            ></bk-option>
          ))}
          <div
            slot='extension'
            style='cursor: pointer'
          >
            {this.$slots?.extension}
          </div>
        </bk-select>
      </span>
    );
  }
}
