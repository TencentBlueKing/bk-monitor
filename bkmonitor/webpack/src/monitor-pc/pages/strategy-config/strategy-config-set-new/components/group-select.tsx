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

import './group-select.scss';

interface IGroupSelect {
  list?: IGroupItem[];
  value?: string | number;
  readonly?: boolean;
  placeholder?: string;
}

export interface IGroupItem {
  id: string;
  name: string;
  children?: IGroupItem[];
  fatherName?: string;
}
interface IGroupSelectEvent {
  onClear?: any;
  onChange?: string | number;
}
@Component({
  name: 'GroupSelect'
})
export default class GroupSelect extends tsc<IGroupSelect, IGroupSelectEvent> {
  @Prop({ type: Array, default: () => [] }) list: IGroupItem[];
  @Prop({ type: [String, Number], default: '' }) value: string | number;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ type: String, default: window.i18n.tc('选择') }) placeholder: string;
  @Ref('group-select-panel') selectPanelRef: HTMLDivElement;
  @Ref('select-wrap') selectWapRef: HTMLDivElement;

  keyword = '';
  popoverInstance = null;
  isShow = false;
  activeGroupId = '';
  activeGroup: IGroupItem;
  activeId = '';
  activeItem: IGroupItem = null;

  get filterList() {
    if (!this.keyword) return this.list;
    return this.list.filter(
      item => item?.children?.some(child => child.name.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()))
    );
  }
  get activeList() {
    return this.filterList.find(item => item.id === this.activeGroupId)?.children || [];
  }
  // 回显
  @Watch('value', { immediate: true })
  handleValue(v: string) {
    this.activeId = v;
  }
  @Watch('list', { immediate: true })
  handleList(v: IGroupItem[]) {
    if (v.length) {
      this.activeGroup = this.list.filter(item => item?.children?.some(child => child.id === this.activeId))[0];
      this.activeGroupId = this.activeGroup?.id;
      this.activeItem = this.activeGroup?.children.find(item => item.id === this.activeId);
      if (this.activeGroup?.name) {
        this.activeItem.fatherName = this.activeGroup.name;
      }
    }
  }

  handleWrapClick(e: any) {
    let target = null;
    if (e.target?.dataset?.set === 'select-wrap') {
      target = e.target;
    } else {
      target = e.target.parentNode;
    }
    if (this.readonly) return;
    const width = this.selectWapRef.clientWidth;
    if (this.isShow) {
      this.destroyPopoverInstance();
      return;
    }
    this.destroyPopoverInstance(true);
    this.popoverInstance = this.$bkPopover(target, {
      content: this.selectPanelRef,
      trigger: 'click',
      theme: 'light common-monitor',
      boundary: 'window',
      distance: 3,
      placement: 'bottom',
      width,
      arrow: false,
      hideOnClick: true,
      interactive: true,
      onHide: () => {
        this.isShow = false;
      }
    });
    this.popoverInstance?.show?.(100);
  }
  // 清除popover实例
  destroyPopoverInstance(isShow = false) {
    this.keyword = '';
    this.popoverInstance?.hide(0);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    this.isShow = isShow;
  }
  @debounceDecorator(300)
  handleKeywordChange(v: string) {
    this.keyword = v;
    this.handleGroupMouseenter(this.filterList[0]);
  }
  handleGroupMouseenter(item: IGroupItem) {
    this.activeGroupId = item?.id || '';
    this.activeGroup = item;
  }
  handleSelect(item: IGroupItem) {
    this.destroyPopoverInstance();
    if (this.activeId === item.id) return;
    this.activeId = item.id;
    this.activeItem = item;
    this.activeItem.fatherName = this.activeGroup.name;
    this.handleChange(item.id);
  }
  @Emit('clear')
  handleClear() {
    this.activeId = '';
    this.activeItem = null;
    this.activeGroupId = '';
    this.activeGroup = null;
    this.destroyPopoverInstance();
  }
  @Emit('change')
  handleChange(v: string) {
    return v;
  }
  render() {
    return (
      <div class={['group-select-component', { 'is-readonly': this.readonly }]}>
        <div
          class={['select-wrap', { 'is-focus': this.isShow }, { 'is-hover': !this.readonly }]}
          ref='select-wrap'
          data-set='select-wrap'
          onClick={this.handleWrapClick}
        >
          <div class='select-name'>
            {this.activeItem?.name ? (
              <span class='name'>
                {this.activeItem.name}
                <span class='father-name'>（{this.activeItem?.fatherName || ''}）</span>
              </span>
            ) : (
              <span class='placeholder'>{this.placeholder}</span>
            )}
          </div>
          {!this.readonly && (
            <span
              class='icon-monitor sel-icon icon-mc-close-fill'
              onClick={e => {
                e.stopPropagation();
                this.handleClear();
              }}
            ></span>
          )}
          <span
            class={['icon-monitor', 'sel-icon', 'icon-arrow-down']}
            onClick={e => e.stopPropagation()}
          ></span>
        </div>
        <div style='display: none;'>
          <div
            class='group-select-panel'
            ref='group-select-panel'
          >
            <bk-input
              class='panel-search'
              leftIcon='bk-icon icon-search'
              behavior='simplicity'
              placeholder={this.$t('输入关键字')}
              value={this.keyword}
              on-change={this.handleKeywordChange}
            ></bk-input>
            {this.filterList.length > 0 ? (
              <div class='panel-list'>
                {this.filterList.length > 0 && (
                  <ul class='panel-item'>
                    {this.filterList.map(item => (
                      <li
                        class={['list-item', { 'item-active': item.id === this.activeGroupId }]}
                        key={item.id}
                        onMouseenter={() => this.handleGroupMouseenter(item)}
                      >
                        {item.name}
                        <i class='icon-monitor icon-arrow-right arrow-icon'></i>
                      </li>
                    ))}
                  </ul>
                )}
                {this.activeList.length > 0 && (
                  <ul class='panel-item child-item'>
                    {this.activeList.map(
                      item =>
                        item.name.toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) && (
                          <li
                            class={['list-item', { 'item-active': item.id === this.activeId }]}
                            key={item.id}
                            onClick={() => this.handleSelect(item)}
                          >
                            {item.name.slice(
                              0,
                              item.name.toLocaleLowerCase().indexOf(this.keyword.toLocaleLowerCase())
                            )}
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
              </div>
            ) : (
              <div class='panel-list'>
                <div style='width: 100%;'>
                  <bk-exception
                    class='exception-wrap-item exception-part'
                    type='empty'
                    scene='part'
                  >
                    {' '}
                  </bk-exception>
                </div>
              </div>
            )}
            {this.$slots.extension && <div class='select-extension'>{this.$slots.extension}</div>}
          </div>
        </div>
      </div>
    );
  }
}
