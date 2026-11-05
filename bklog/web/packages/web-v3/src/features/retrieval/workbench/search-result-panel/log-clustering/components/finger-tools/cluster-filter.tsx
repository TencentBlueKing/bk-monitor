
import { Button as TButton, Checkbox as TCheckbox, Input as TInput, Popup as TPopup } from 'tdesign-vue-next';
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

import { Component, Prop, Emit, Watch } from 'vue-property-decorator';
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

  // Public props/events already installed by the source decorators.
  "onSelected"?: (value: string, arg0: string) => void;
  "onSubmit"?: (value: string[]) => void;
}

interface ISelectOption {
  id: string;
  name: string;
}

@Component
export default class ClusterFilter extends tsc<IProps> {
  @Prop({ type: String, required: true }) title!: string;
  @Prop({ type: Boolean, default: true }) searchable!: boolean;
  @Prop({ type: Number, default: 200 }) popoverMinWidth!: number;
  @Prop({ type: Function, default: () => {} }) toggle!: (boolean) => void;
  @Prop({ type: Array, default: () => [] }) select!: string[];
  @Prop({ type: Array, default: () => [] }) selectList!: ISelectOption[];
  @Prop({ type: Boolean, default: false }) loading!: boolean;
  @Prop({ type: Boolean, default: false }) isActive!: boolean;

  /** 选中的值 */
  selectValue: string[] = [];
  /** 是否显示了下拉框 */
  isShowSelectOption = false;
  /** 下拉内搜索关键字 */
  keyword = '';

  @Watch('select', { immediate: true })
  watchSelectValue(val: string[]) {
    this.selectValue = val;
  }

  @Emit('selected')
  handleSelectedOption(ids: string[]) {
    return ids;
  }

  getGroupItemCheckedState(id: string) {
    return this.selectValue.includes(id);
  }

  handleOptionChange(id: string, checked: boolean) {
    const nextValue = this.selectValue.filter(item => item !== id);
    if (checked) {
      nextValue.push(id);
    }
    this.selectValue = nextValue;
    this.handleSelectedOption(nextValue);
  }

  @Emit('submit')
  submitFilter() {
    this.closePanel();
    return this.select;
  }

  cancelFilter() {
    this.selectValue = [...(this.select || [])];
    this.closePanel();
  }

  closePanel() {
    this.keyword = '';
    this.isShowSelectOption = false;
    this.toggle(false);
  }

  toggleSelect(val: boolean) {
    this.isShowSelectOption = val;
    if (!val) {
      this.keyword = '';
    }
    this.toggle(val);
  }

  getVisibleOptions() {
    const keyword = this.keyword.trim().toLowerCase();
    if (!keyword) {
      return this.selectList;
    }
    return this.selectList.filter(option => {
      return (
        String(option.name || '')
          .toLowerCase()
          .includes(keyword) || String(option.id).toLowerCase().includes(keyword)
      );
    });
  }

  render() {
    const triggerSlot = () => (
      <div
        class='filter-box'
        onClick={(event: MouseEvent) => {
          event.stopPropagation();
          this.toggleSelect(!this.isShowSelectOption);
        }}
      >
        <span>{this.title}</span>
        <i class={['bk-icon icon-funnel', { 'is-active': this.isShowSelectOption || this.isActive }]} />
      </div>
    );
    const options = this.getVisibleOptions();
    const selectGroupDom = () => {
      return (
        <div class='group-list'>
          {options.length ? (
            options.map(option => (
              <div
                key={option.id}
                class='group-item'
              >
                <TCheckbox
                  class='ext-box'
                  checked={this.getGroupItemCheckedState(option.id)}
                  onChange={(checked: boolean) => this.handleOptionChange(option.id, checked)}
                >
                  <span title={option.name}>{option.name}</span>
                </TCheckbox>
              </div>
            ))
          ) : (
            <span
              class='group-loading'
              v-loading={{ loading: this.loading, zIndex: 10 }}
            >
              {this.loading ? '' : this.$t('暂无数据')}
            </span>
          )}
        </div>
      );
    };
    return (
      <TPopup
        class='cluster-select-filter'
        visible={this.isShowSelectOption}
        trigger='focus'
        placement='bottom-left'
        attach='body'
        overlayInnerClassName='cluster-select-filter-popover'
        overlayInnerStyle={{ minWidth: `${this.popoverMinWidth}px`, padding: '8px 0 0' }}
        v-slots={{
          content: () => (
            <div
              class='cluster-filter-panel'
              onClick={(event: MouseEvent) => event.stopPropagation()}
            >
              {this.searchable && (
                <TInput
                  class='cluster-filter-search'
                  value={this.keyword}
                  placeholder={String(this.$t('请输入关键字'))}
                  clearable
                  onChange={(value: string) => {
                    this.keyword = value;
                  }}
                />
              )}
              {selectGroupDom()}
              <div class='extension-box'>
                <TButton
                  style='margin-right: 8px;'
                  size='small'
                  theme='primary'
                  onClick={this.submitFilter}
                >
                  {this.$t('确定')}
                </TButton>
                <TButton
                  size='small'
                  theme='default'
                  onClick={this.cancelFilter}
                >
                  {this.$t('取消')}
                </TButton>
              </div>
            </div>
          ),
        }}
      >
        {triggerSlot()}
      </TPopup>
    );
  }
}
