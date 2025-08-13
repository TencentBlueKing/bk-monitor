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

import type { CommonItem } from './tcp-target';

import './common-collapse.scss';

const MenuList: CommonItem[] = [
  {
    id: 'clear-all',
    name: window.i18n.tc('清除所有'),
  },
  {
    id: 'copy-all',
    name: window.i18n.tc('复制所有'),
  },
];
interface ICommonCollapseEvents {
  onMenuSelect: string;
}
interface ICommonCollapseProps {
  menuList?: CommonItem[];
}
@Component
export default class CommonCollapse extends tsc<ICommonCollapseProps, ICommonCollapseEvents> {
  @Prop({
    default() {
      return MenuList;
    },
  })
  menuList: CommonItem[];
  actived: string[] = ['common-collapse'];
  handleMenuItemSelect(id: string) {
    this.$emit('menuSelect', id);
    (this.$refs.menuPopover as any)?.hideHandler?.();
  }
  render() {
    return (
      <bk-collapse
        class='common-collapse'
        vModel={this.actived}
      >
        <bk-collapse-item
          name='common-collapse'
          hide-arrow
        >
          <div class='collapse-header'>
            <div class='header-left'>
              <i class={`bk-icon icon-down-shape collapse-icon ${this.actived.length ? 'is-actived' : ''}`} />
              <div class='header-left-wrap'>{this.$slots.headerLeft}</div>
            </div>
            <div
              class='header-right'
              onClick={e => e.stopPropagation()}
            >
              {this.$slots.headerRight}
              <bk-popover
                ref='menuPopover'
                ext-cls='domain-select-tips common-collapse-tips'
                tippy-options={{
                  arrow: false,
                  trigger: 'click',
                }}
                always={false}
                transfer
              >
                <span class='rigth-tools'>
                  <i class='bk-icon icon-more' />
                </span>
                <ul
                  class='domain-select-list'
                  slot='content'
                >
                  {this.menuList.map(item => (
                    <li
                      key={item.id}
                      class='domain-select-list-item'
                      onClick={() => this.handleMenuItemSelect(item.id)}
                    >
                      {item.name}
                    </li>
                  ))}
                </ul>
              </bk-popover>
            </div>
          </div>
          <div
            class='collapse-content'
            slot='content'
          >
            {this.$slots.content}
          </div>
        </bk-collapse-item>
      </bk-collapse>
    );
  }
}
