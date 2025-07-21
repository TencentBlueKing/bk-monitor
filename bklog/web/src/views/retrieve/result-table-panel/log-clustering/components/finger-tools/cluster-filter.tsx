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
export default class ClusterFilter extends tsc<IProps> {
  @Prop({ required: true, type: String }) title: string;
  @Prop({ default: true, type: Boolean }) searchable: boolean;
  @Prop({ default: 200, type: Number }) popoverMinWidth: number;
  @Prop({ default: () => {}, type: Function }) toggle: (boolean) => void;
  @Prop({ default: () => [], type: Array }) select: Array<string>;
  @Prop({ default: () => [], type: Array }) selectList: Array<ISelectOption>;
  @Prop({ default: false, type: Boolean }) loading: boolean;
  @Prop({ default: false, type: Boolean }) isActive: boolean;
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
      <div class="filter-box">
        <span>{this.title}</span>
        <i
          class={[
            'bk-icon icon-funnel',
            { 'is-active': this.isShowSelectOption || this.isActive },
          ]}
        ></i>
      </div>
    );
    const selectGroupDom = () => {
      return (
        <div class="group-list">
          {!!this.selectList.length ? (
            this.selectList.map((option) => (
              <bk-option class="group-item" id={option.id} name={option.name}>
                <bk-checkbox
                  checked={this.getGroupItemCheckedState(option.id)}
                  ext-cls="ext-box"
                >
                  <span title={option.name}>{option.name}</span>
                </bk-checkbox>
              </bk-option>
            ))
          ) : (
            <span
              class="group-loading"
              v-bkloading={{ isLoading: this.loading, zIndex: 10 }}
            >
              {this.loading ? '' : this.$t('暂无数据')}
            </span>
          )}
        </div>
      );
    };
    const extensionSlot = () => (
      <div class="extension-box" slot="extension">
        <bk-button
          onClick={this.submitFilter}
          size="small"
          style="margin-right: 8px;"
          theme="primary"
        >
          {this.$t('确定')}
        </bk-button>
        <bk-button onClick={this.cancelFilter} size="small" theme="default">
          {this.$t('取消')}
        </bk-button>
      </div>
    );
    return (
      <bk-select
        class="cluster-select-filter"
        clearable={false}
        ext-popover-cls="cluster-select-filter-popover"
        multiple
        onSelected={this.handleSelectedOption}
        onToggle={this.toggleSelect}
        popover-min-width={this.popoverMinWidth}
        popover-options={{ boundary: 'window' }}
        ref="clusterSelect"
        scopedSlots={{
          trigger: () => triggerSlot(),
        }}
        scroll-height={236}
        searchable={this.searchable}
        show-empty={false}
        v-model={this.selectValue}
      >
        {selectGroupDom()}
        {extensionSlot()}
      </bk-select>
    );
  }
}
