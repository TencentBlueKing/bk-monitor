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

import './chart-more-tool.scss';

export interface IProps {
  toolChecked: string[];
  moreChecked: string[];
}
export interface IEvents {
  onSelect: string;
}
@Component
export default class ChartToolsMenu extends tsc<IProps, IEvents> {
  /** 工具栏 */
  @Prop({ default: () => [], type: Array }) toolChecked: string[];
  /** 收藏在更多的工具菜单 */
  @Prop({ default: () => [], type: Array }) moreChecked: string[];
  @Ref() moreRef: Element;
  @Ref() menuRef: Element;
  // 菜单的可选列表
  menuList = [];

  /** 展示出来的工具栏 */
  get toolCheckedList() {
    return this.menuList.filter(item => this.toolChecked.includes(item.id));
  }
  /** 更多菜单展示列表 */
  get moreMenuList() {
    return this.menuList.filter(item => this.moreChecked.includes(item.id));
  }

  popoverInstance = null;

  created() {
    this.menuList = [
      {
        name: this.$t('保存到仪表盘'),
        checked: false,
        id: 'save',
        icon: 'mc-mark',
      },
      {
        name: this.$t('截图到本地'),
        checked: false,
        id: 'screenshot',
        icon: 'mc-camera',
      },
      {
        name: this.$t('查看大图'),
        checked: false,
        id: 'fullscreen',
        icon: 'fullscreen',
      },
      {
        name: this.$t('检索'),
        checked: false,
        id: 'explore',
        icon: 'mc-retrieval',
        hasLink: true,
      },
      {
        name: this.$t('添加策略'),
        checked: false,
        id: 'strategy',
        icon: 'menu-strategy',
        hasLink: true,
      },
      {
        name: this.$t('Y轴固定最小值为0'),
        checked: false,
        id: 'set',
        nextName: this.$t('Y轴自适应'),
        icon: 'mc-yaxis',
        nextIcon: 'mc-yaxis-scale',
      },
      {
        name: this.$t('面积图'),
        checked: false,
        id: 'area',
        nextName: this.$t('线性图'),
        icon: 'mc-area',
        nextIcon: 'mc-line',
      },
    ];
  }

  beforeDestroy() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  @Emit('select')
  handleSelect(type: string) {
    this.popoverInstance?.hide?.();
    return type;
  }

  handleShowMenu() {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.moreRef, {
        content: this.menuRef,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light common-monitor',
        arrow: false,
        // hideOnClick: false,
        interactive: true,
        boundary: 'window',
        distance: 20,
        zIndex: 1000,
        animation: 'slide-toggle',
        followCursor: false,
      });
      this.popoverInstance.show();
    }
  }
  render() {
    return (
      <span class='chart-tools-menu'>
        {this.toolCheckedList.map(item => (
          <i
            class={['icon-monitor', `icon-${item.icon}`]}
            v-bk-tooltips={{ content: item.name, allowHTML: false }}
            onClick={() => this.handleSelect(item.id)}
          />
        ))}
        {this.moreChecked.length ? (
          <i
            ref='moreRef'
            class='icon-monitor icon-mc-more'
            onClick={this.handleShowMenu}
          />
        ) : undefined}
        <div style='display: none;'>
          <ul
            ref='menuRef'
            class='chart-tools-menu-list'
          >
            {this.moreMenuList.map(item => (
              <li
                class='chart-tools-menu-item'
                onClick={() => this.handleSelect(item.id)}
              >
                <i class={['icon-monitor', `icon-${item.icon}`, 'item-icon']} />
                <span>{item.name}</span>
                {item.hasLink ? <i class='icon-monitor icon-mc-link link-icon' /> : undefined}
              </li>
            ))}
          </ul>
        </div>
      </span>
    );
  }
}
