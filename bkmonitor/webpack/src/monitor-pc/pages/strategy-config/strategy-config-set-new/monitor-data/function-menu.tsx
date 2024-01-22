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

import debounceDecorator from '../../../../../monitor-common/utils/debounce-decorator';
import { deepClone } from '../../../../../monitor-common/utils/utils';

import './function-menu.scss';

export interface IFunctionParam {
  id?: string;
  name?: string;
  default: string | number;
  value?: string | number;
  edit?: boolean;
  shortlist: string[] | number[];
}

export interface IFunctionItem {
  id: string;
  name: string;
  children?: IFunctionItem[];
  params?: IFunctionParam[];
  description?: string;
  key?: string;
  support_expression?: boolean;
}

interface IFunctionMenuProps {
  list: IFunctionItem[];
  isExpSupport?: boolean;
}
interface IFunctionMenuEvent {
  onFuncSelect: IFunctionItem;
}
@Component
export default class FunctionMenu extends tsc<IFunctionMenuProps, IFunctionMenuEvent> {
  @Prop({ type: Array, default: () => [] }) list: IFunctionItem[];
  /** 只展示支持表达式的函数 */
  @Prop({ default: false, type: Boolean }) readonly isExpSupport: boolean;
  @Ref('menuPanel') menuPanelRef: HTMLDivElement;
  activeFuncType = '';
  activeFuncId = '';
  activeItem: IFunctionItem;
  keyword = '';
  popoverInstance: any = null;

  get filterList() {
    if (!this.keyword) return this.list;
    return this.list.filter(
      func => func?.children?.some(item => item.name.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()))
    );
  }
  get activeFuncList() {
    // eslint-disable-next-line max-len
    return (
      this.filterList
        .find(item => item.id === this.activeFuncType)
        ?.children?.filter(item => (this.isExpSupport ? item.support_expression : true)) || []
    );
  }
  get activeFunc() {
    return this.activeFuncList.find(item => item.id === this.activeFuncId);
  }
  get activeFuncTypeDesc() {
    return this.list.find(item => item.id === this.activeFuncType)?.description || '';
  }
  @Watch('list', { immediate: true })
  handleListChange() {
    if (!this.activeFuncId && !this.activeFuncType) {
      this.activeFuncType = this.list?.[0]?.id || '';
      this.activeFuncId = '';
      this.activeItem = this.list?.[0];
    }
  }
  beforeDestroy() {
    this.destroyPopoverInstance();
  }
  // hover函数类型时触发
  handleFuncTypeMouseenter(item: IFunctionItem) {
    this.activeFuncType = item?.id || '';
    this.activeFuncId = '';
    this.activeItem = item;
    // this.handleFuncMouseenter(item?.children?.[0])
  }
  // hover 函数名时触发
  handleFuncMouseenter(item: IFunctionItem) {
    this.activeFuncId = item?.id || '';
    this.activeItem = item;
  }
  // 搜索函数时触发
  @debounceDecorator(300)
  handleKeywordChange(v: string) {
    this.keyword = v;
    this.handleFuncTypeMouseenter(this.filterList[0]);
  }
  // 点击锚点时触发
  handleClickMenuAnchor(e: MouseEvent) {
    // if (!this.popoverInstance) {
    // }
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.menuPanelRef,
      trigger: 'click',
      theme: 'light common-monitor',
      arrow: false,
      maxWidth: 578,
      hideOnClick: true,
      interactive: true,
      boundary: 'window',
      offset: -1,
      distance: 12
    });
    this.popoverInstance?.show?.(100);
  }
  @Emit('funcSelect')
  handleSelectFunc(item: IFunctionItem) {
    this.destroyPopoverInstance();
    return deepClone(item);
  }
  // 清除popover实例
  destroyPopoverInstance() {
    this.popoverInstance?.hide(0);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }
  render() {
    return (
      <div class='function-menu'>
        <div
          class='function-menu-anchor'
          on-click={this.handleClickMenuAnchor}
        >
          {this.$slots.default || <span class='icon-monitor icon-mc-add menu-icon'></span>}
        </div>
        <div style='display: none;'>
          <div
            class='function-menu-panel'
            ref='menuPanel'
          >
            <bk-input
              class='panel-search'
              rightIcon='bk-icon icon-search'
              behavior='simplicity'
              placeholder={this.$t('搜索函数')}
              value={this.keyword}
              on-change={this.handleKeywordChange}
            ></bk-input>
            <div class='panel-list'>
              {this.filterList?.length > 0 && (
                <ul class='panel-item'>
                  {this.filterList.map((item: IFunctionItem) => (
                    <li
                      class={['list-item', { 'item-active': item.id === this.activeFuncType }]}
                      key={item.id}
                      on-mouseenter={() => this.handleFuncTypeMouseenter(item)}
                    >
                      {item.name}
                      <i class='icon-monitor icon-arrow-right arrow-icon'></i>
                    </li>
                  ))}
                </ul>
              )}
              {this.activeFuncList?.length > 0 && (
                <ul class='panel-item'>
                  {this.activeFuncList.map(
                    (item: IFunctionItem) =>
                      item.id.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) && (
                        <li
                          class={['list-item', { 'item-active': item.id === this.activeFuncId }]}
                          key={item.id}
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
        </div>
      </div>
    );
  }
}
