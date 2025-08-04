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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { throttle } from 'throttle-debounce';

import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './status-tab.scss';

interface IProps {
  maxWidth?: number;
  statusList: ITableFilterItem[];
  value?: string;
  onChange?: (va: string) => void;
}

@Component
export default class StatusTab extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) statusList: ITableFilterItem[];
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Number, default: 60 }) maxWidth: number;
  // 当前选中选项
  localValue = '';
  // 平铺列表
  tabList = [];
  // 更多列表
  moreList = [];
  // 是否弹出更多列表
  moreShow = false;
  moreText = '';
  throttleSetList = () => {};

  created() {
    this.tabList = [...this.statusList];
    this.moreList = [];
    this.moreText = '';
    this.throttleSetList = throttle(400, this.setList, {
      debounceMode: false,
    });
  }

  @Watch('maxWidth', { immediate: true })
  handleWatchMaxWidth() {
    this.throttleSetList();
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.localValue !== this.value) {
      this.localValue = this.value;
    }
  }

  /** 点击选中 */
  handleClickItem(item: ITableFilterItem) {
    this.valueChange(item.id);
  }

  @Emit('change')
  valueChange(val: string) {
    this.localValue = val;
    this.moreText = this.moreList.find(item => this.localValue === item.id)?.name || '';
    return val;
  }

  setList() {
    try {
      const moreWidth = 56; // 更多按钮宽度
      if (!this.maxWidth) {
        this.tabList = [...this.statusList];
        return;
      }
      let totalWidth = 0;
      let index = 0;
      for (const item of this.statusList) {
        if (totalWidth > this.maxWidth - moreWidth) {
          break;
        }
        index += 1;
        const w = item.name.toString().length * 10;
        totalWidth += w;
      }

      this.tabList = this.statusList.slice(0, index);
      this.moreList = this.statusList.slice(index, this.statusList.length);
      this.moreText = this.moreList.find(item => this.localValue === item.id)?.name || '';
    } catch (err) {
      console.log(err);
    }
  }

  handleMoreHide() {
    this.moreShow = false;
  }
  handleMoreShow() {
    this.moreShow = true;
  }

  render() {
    return (
      <div class='more-status-tab-wrap'>
        {this.tabList.map(item => (
          <span
            key={item.id}
            class={['common-status-wrap status-tab-item', { active: this.localValue === item.id }]}
            v-bk-tooltips={{
              content: item.tips,
              placements: ['top'],
              boundary: 'window',
              disabled: !item.tips,
              delay: 200,
              allowHTML: false,
            }}
            onClick={() => this.handleClickItem(item)}
          >
            {<span class='status-name'>{item?.name || '--'}</span>}
          </span>
        ))}
        {this.moreList.length ? (
          <bk-dropdown-menu
            trigger='click'
            on-hide={this.handleMoreHide}
            on-show={this.handleMoreShow}
          >
            <div
              class={['status-more-trigger', { active: !!this.moreText }, { 'more-show': this.moreShow }]}
              slot='dropdown-trigger'
            >
              <span class='more-text'>{this.moreText || this.$t('更多')}</span>
              <span class='icon-monitor icon-arrow-down' />
            </div>
            <div
              class='status-dropdown-list'
              slot='dropdown-content'
            >
              {this.moreList.map(item => (
                <span
                  key={item.id}
                  class='down-status-name'
                  onClick={() => this.handleClickItem(item)}
                >
                  {item?.name || '--'}
                </span>
              ))}
            </div>
          </bk-dropdown-menu>
        ) : undefined}
        <div class='more-status-tab-wrap-visible'>
          {this.statusList.map(item => (
            <span
              key={item.id}
              class={'common-status-wrap status-tab-item'}
            >
              {<span class='status-name'>{item?.name || '--'}</span>}
            </span>
          ))}
        </div>
      </div>
    );
  }
}
