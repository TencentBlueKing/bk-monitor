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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IMenuItem, COMMON_SETTINGS_LIST } from '../typings';

import './list-menu.scss';

interface IListMenuEvent {
  onHidden: void;
  onMenuSelect: IMenuItem;
  onShow: void;
}
interface IListMenuProps {
  keyword?: string;
  list?: IMenuItem[];
}
@Component
export default class ListMenu extends tsc<IListMenuProps, IListMenuEvent> {
  @Prop({ default: () => COMMON_SETTINGS_LIST }) list: IMenuItem[];
  // 过滤字符
  @Prop({ default: '' }) keyword: string;

  poppoverInstance: any = null;
  // 过滤列表
  get filterList() {
    if (!this.keyword?.trim?.().length) return this.list;
    const keyword = this.keyword.toLowerCase();
    return this.list.filter(
      item => item.id.toString().toLowerCase().includes(keyword) || item.name.toLowerCase().includes(keyword)
    );
  }
  beforeDestroy() {
    if (this.poppoverInstance) {
      this.poppoverInstance.hide(0);
      this.poppoverInstance.destroy();
      this.poppoverInstance = null;
    }
  }

  @Emit('menuSelect')
  handleMenuClick(item: IMenuItem) {
    this.poppoverInstance?.hide(0);
    return item;
  }
  handleClick(e?: MouseEvent) {
    e?.stopPropagation?.();
    !!e && (e.cancelBubble = true);
    e?.preventDefault?.();
    this.poppoverInstance = this.$bkPopover(this.$el, {
      content: this.$refs.menu,
      trigger: 'click',
      arrow: false,
      placement: 'bottom-start',
      theme: 'light common-monitor',
      distance: 5,
      duration: [275, 0],
      followCursor: false,
      flip: true,
      flipBehavior: ['bottom', 'top'],
      flipOnUpdate: true,
      onHidden: () => {
        this.$emit('hidden');
      },
      onShow: () => {
        this.$emit('show');
        return true;
      },
    });
    this.poppoverInstance?.show(100);
  }
  render() {
    return (
      <span onClick={this.handleClick}>
        {this.$slots.default}
        <div style='display: none'>
          <ul
            ref='menu'
            class='list-menu'
          >
            {this.filterList?.length ? (
              this.filterList.map(item => (
                <li
                  key={item.id}
                  class='list-menu-item'
                  onMousedown={() => this.handleMenuClick(item)}
                >
                  {item.name}
                </li>
              ))
            ) : (
              <div class='global-part-empty'>
                <bk-exception
                  scene='part'
                  type='empty'
                >
                  {this.$t('查无数据')}
                </bk-exception>
              </div>
            )}
          </ul>
        </div>
      </span>
    );
  }
}
