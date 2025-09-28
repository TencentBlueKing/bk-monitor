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

import { Component, Prop, Emit, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './cluster-filter.scss';

interface IProps {
  title: string;
  searchable: boolean;
  popoverMinWidth: number;
  toggle: (boolean) => void;
  select: string[];
  selectList: ISelectOption[];
  loading: boolean;
  isActive: boolean;
}

interface ISelectOption {
  id: string;
  name: string;
}

@Component
export default class ClusterFilter extends tsc<IProps> {
  @Prop({ type: String, required: true }) title: string;
  @Prop({ type: Boolean, default: true }) searchable: boolean;
  @Prop({ type: Number, default: 200 }) popoverMinWidth: number;
  @Prop({ type: Function, default: () => {} }) toggle: (boolean) => void;
  @Prop({ type: Array, default: () => [] }) select: string[];
  @Prop({ type: Array, default: () => [] }) selectList: ISelectOption[];
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Boolean, default: false }) isActive: boolean;
  @Ref('clusterSelect') clusterSelectRef: any;

  /** 选中的值 */
  selectValue = [];
  /** 是否显示了下拉框 */
  isShowSelectOption = false;

  @Watch('select', { immediate: true })
  watchSelectValue(val: string[]) {
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
        <i class={['bk-icon icon-funnel', { 'is-active': this.isShowSelectOption || this.isActive }]} />
      </div>
    );
    const selectGroupDom = () => {
      return (
        <div class='group-list'>
          {this.selectList.length ? (
            this.selectList.map(option => (
              <bk-option
                id={option.id}
                key={option.id}
                class='group-item'
                name={option.name}
              >
                <bk-checkbox
                  ext-cls='ext-box'
                  checked={this.getGroupItemCheckedState(option.id)}
                >
                  <span title={option.name}>{option.name}</span>
                </bk-checkbox>
              </bk-option>
            ))
          ) : (
            <span
              class='group-loading'
              v-bkloading={{ isLoading: this.loading, zIndex: 10 }}
            >
              {this.loading ? '' : this.$t('暂无数据')}
            </span>
          )}
        </div>
      );
    };
    const extensionSlot = () => (
      <div
        class='extension-box'
        slot='extension'
      >
        <bk-button
          style='margin-right: 8px;'
          size='small'
          theme='primary'
          onClick={this.submitFilter}
        >
          {this.$t('确定')}
        </bk-button>
        <bk-button
          size='small'
          theme='default'
          onClick={this.cancelFilter}
        >
          {this.$t('取消')}
        </bk-button>
      </div>
    );
    return (
      <bk-select
        ref='clusterSelect'
        class='cluster-select-filter'
        v-model={this.selectValue}
        scopedSlots={{
          trigger: () => triggerSlot(),
        }}
        clearable={false}
        ext-popover-cls='cluster-select-filter-popover'
        popover-min-width={this.popoverMinWidth}
        popover-options={{ boundary: 'window' }}
        scroll-height={236}
        searchable={this.searchable}
        show-empty={false}
        multiple
        onSelected={this.handleSelectedOption}
        onToggle={this.toggleSelect}
      >
        {selectGroupDom()}
        {extensionSlot()}
      </bk-select>
    );
  }
}
