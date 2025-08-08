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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SelectWrap from '../utils/select-wrap';

import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './function-creator.scss';

interface IProps {
  showLabel?: boolean;
}

@Component
export default class FunctionCreator extends tsc<IProps> {
  /* 是否展示左侧标签 */
  @Prop({ default: true }) showLabel: boolean;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  /* 可选项列表 */
  @Prop({ default: () => [] }) options: IFunctionOptionsItem[];
  /* 是否展示变量 */
  @Prop({ default: false }) showVariables: boolean;

  showSelect = false;
  popClickHide = true;

  keyword = '';
  activeFuncType = '';
  activeFuncId = '';
  activeItem = null;

  get filterList() {
    return [];
  }
  get activeFuncList() {
    return [];
  }

  handleOpenChange(v) {
    this.showSelect = v;
  }
  handleFuncTypeMouseenter(item) {
    this.activeFuncType = item?.id || '';
    this.activeFuncId = '';
    this.activeItem = item;
  }

  handleSelectFunc(item) {
    console.log(item);
  }

  handleKeywordChange(v: string) {
    this.keyword = v;
  }
  handleFuncMouseenter(item) {
    this.activeFuncId = item?.id || '';
    this.activeItem = item;
  }

  render() {
    return (
      <div class='template-function-creator-component'>
        {this.showLabel && <div class='function-label'>{this.$slots?.label || this.$t('函数')}</div>}
        <SelectWrap
          expanded={this.showSelect}
          minWidth={357}
          needPop={true}
          popClickHide={this.popClickHide}
          onOpenChange={this.handleOpenChange}
        >
          <div class='tags-wrap' />
          <div
            ref='menuPanel'
            class='template-function-creator-component-popover'
            slot='popover'
          >
            <bk-input
              class='panel-search'
              behavior='simplicity'
              placeholder={this.$t('搜索函数')}
              rightIcon='bk-icon icon-search'
              value={this.keyword}
              on-change={this.handleKeywordChange}
            />
            <div class='panel-list'>
              {this.filterList?.length > 0 && (
                <ul class='panel-item'>
                  {this.filterList.map(item => (
                    <li
                      key={item.id}
                      class={['list-item', { 'item-active': item.id === this.activeFuncType }]}
                      on-mouseenter={() => this.handleFuncTypeMouseenter(item)}
                    >
                      {item.name}
                      <i class='icon-monitor icon-arrow-right arrow-icon' />
                    </li>
                  ))}
                </ul>
              )}
              {this.activeFuncList?.length > 0 && (
                <ul class='panel-item'>
                  {this.activeFuncList.map(
                    item =>
                      item.id.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) && (
                        <li
                          key={item.id}
                          class={['list-item', { 'item-active': item.id === this.activeFuncId }]}
                          on-click={() => this.handleSelectFunc(item)}
                          on-mouseenter={() => this.handleFuncMouseenter(item)}
                        >
                          {item.name.slice(0, item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()))}
                          <span style='color: #FF9C00'>
                            {item.name.slice(
                              item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()),
                              item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) +
                                this.keyword.length
                            )}
                          </span>
                          {item.name.slice(
                            item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase()) +
                              this.keyword.length,
                            item.name.length
                          )}
                        </li>
                      )
                  )}
                </ul>
              )}
              {(this.activeFuncId || this.activeFuncType) && (
                <div class='panel-desc'>
                  <div class='desc-title'>{this.activeItem.name}</div>
                  <div class='desc-content'>{this.activeItem.description}</div>
                </div>
              )}
              {(!this.filterList?.length || !this.activeFuncList?.length) && (
                <div class='panel-desc'>{this.$t('查无数据')}</div>
              )}
            </div>
          </div>
        </SelectWrap>
      </div>
    );
  }
}
