/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import { Component, Prop, Emit, Ref, Watch } from 'vue-property-decorator';
import './cluster-filter.scss';

interface IProps {
  title: string;
  searchable: boolean;
  popoverMinWidth: number;
  toggle: Function;
  select: Array<string>;
  selectList: Array<ISelectOption>;
  loading: boolean;
  isActive: boolean;
}

interface ISelectOption {
  id: string;
  name: string;
}

@Component
export default class TimeFormatterSwitcher extends tsc<IProps> {
  @Prop({ type: String, required: true }) title: string;
  @Prop({ type: Boolean, default: true }) searchable: boolean;
  @Prop({ type: Number, default: 200 }) popoverMinWidth: number;
  @Prop({ type: Function, default: () => {} }) toggle: Function;
  @Prop({ type: Array, default: () => [] }) select: Array<string>;
  @Prop({ type: Array, default: () => [] }) selectList: Array<ISelectOption>;
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Boolean, default: false }) isActive: boolean;
  @Ref('clusterSelect') clusterSelectRef: any;

  /** 选中的值 */
  selectValue = [];
  /** 是否显示了下拉框 */
  isShowSelectOption = false;

  @Watch('select', { immediate: true })
  watchSelectValue(val: Array<string>) {
    this.selectValue = val;
  }

  @Emit('selected')
  handleSelectedOption(id: string) {
    return id;
  }

  getGroupItemCheckedState(id: string) {
    return this.selectValue.includes(id);
  }

  @Emit('submit')
  submitFilter() {
    this.cancelFilter();
    return this.select;
  }

  cancelFilter() {
    this.selectValue = [];
    this.clusterSelectRef.close();
  }

  toggleSelect(val: boolean) {
    this.isShowSelectOption = val;
    this.toggle(val);
  }

  render() {
    const triggerSlot = () => (
      <div class='filter-box'>
        <span>{this.title}</span>
        <i class={['bk-icon icon-funnel', { 'is-active': this.isShowSelectOption || this.isActive }]}></i>
      </div>
    );
    const selectGroupDom = () => {
      return (
        <div class='group-list'>
          {this.selectList.map(option => (
            <bk-option
              class='group-item'
              id={option.id}
              name={option.name}
            >
              <bk-checkbox
                ext-cls='ext-box'
                checked={this.getGroupItemCheckedState(option.id)}
              >
                <span title={option.name}>{option.name}</span>
              </bk-checkbox>
            </bk-option>
          ))}
        </div>
      );
    };
    const extensionSlot = () => (
      <div
        slot='extension'
        class='extension-box'
      >
        <bk-button
          style='margin-right: 8px;'
          theme='primary'
          size='small'
          onClick={this.submitFilter}
        >
          {this.$t('确定')}
        </bk-button>
        <bk-button
          theme='default'
          size='small'
          onClick={this.cancelFilter}
        >
          {this.$t('取消')}
        </bk-button>
      </div>
    );
    return (
      <bk-select
        multiple
        searchable={this.searchable}
        ext-popover-cls='cluster-select-filter-popover'
        class='cluster-select-filter'
        ref='clusterSelect'
        clearable={false}
        loading={this.loading}
        // show-empty={false}
        v-model={this.selectValue}
        popover-min-width={this.popoverMinWidth}
        popover-options={{ boundary: 'window' }}
        scroll-height={236}
        onSelected={this.handleSelectedOption}
        onToggle={this.toggleSelect}
        scopedSlots={{
          trigger: () => triggerSlot()
        }}
      >
        {selectGroupDom()}
        {extensionSlot()}
      </bk-select>
    );
  }
}
