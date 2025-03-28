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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './setting-more-menu.scss';

interface SettingMoreMenuProps {
  settingMoreList?: MenuOption[];
}
interface SettingMoreMenuEvents {
  onMenuClick: (operation: MenuOptionsEnum) => void;
}

interface MenuOption {
  id: MenuOptionsEnum;
  name: string;
}

const FIELD_SETTING_MENU = [
  {
    id: 'edit',
    name: window.$t('重命名'),
  },
  {
    id: 'export',
    name: window.$t('导出'),
  },
  {
    id: 'delete',
    name: window.$t('删除'),
  },
];

enum MenuOptionsEnum {
  EDIT = 'edit',
  EXPORT = 'export',
  DELETE = 'delete',
}

@Component
export default class SettingMoreMenu extends tsc<SettingMoreMenuProps, SettingMoreMenuEvents> {
  /** 字段设置 more 下拉菜单 */
  @Prop({ default: () => FIELD_SETTING_MENU }) settingMoreList: MenuOption[];

  @Ref('menu')
  menuRef: any;

  popoverInstance = null;

  /** 菜单点击后回调 */
  @Emit('menuClick')
  handleMenuClick(operation: MenuOptionsEnum) {
    this.popoverInstance?.hide?.();
    return operation;
  }

  async handleMenuListShow(e: Event) {
    if (this.popoverInstance) {
      return;
    }
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.menuRef,
      trigger: 'click',
      placement: 'bottom-end',
      theme: 'light field-template-menu field-template-menu-expand',
      arrow: false,
      followCursor: false,
      boundary: 'viewport',
      distance: 4,
      offset: '8, 0',
      onHidden: () => {
        this.popoverInstance?.destroy?.();
        this.popoverInstance = null;
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div class='field-setting-more'>
        <div
          class={`popover-trigger ${this.popoverInstance ? 'is-active' : ''}`}
          onClick={e => this.handleMenuListShow(e)}
        >
          <i class='bklog-icon bklog-more' />
        </div>
        <div style='display: none'>
          <ul
            ref='menu'
            class='field-setting-list-menu bklog-v3-popover-tag'
          >
            {this.settingMoreList.map(item => (
              <li
                key={item.id}
                class='menu-item'
                onClick={() => this.handleMenuClick(item.id)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
