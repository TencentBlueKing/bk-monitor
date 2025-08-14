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

import './select-menu.scss';

export interface IListItem {
  id: number | string;
  name: number | string;
}
interface ISelectMenuProps {
  content?: any;
  list?: IListItem[];
  minWidth?: number;
  needDelete?: boolean;
  show?: boolean;
  target?: any;
}
@Component
export default class SelectMenu extends tsc<ISelectMenuProps> {
  // 触发目标
  @Prop({ default: null, type: HTMLElement }) private readonly target: HTMLElement;
  // 选择列表
  @Prop({ default: null, type: Object }) private readonly content: HTMLElement;
  @Prop({ default: false, type: Boolean }) private readonly show: boolean;
  @Prop({ default: false, type: Boolean }) private readonly needDelete: boolean;
  @Prop({ default: 98, type: Number }) private readonly minWidth: number;

  // 默认列表数据
  @Prop({ default: () => [], type: Array }) private readonly list: IListItem[];

  @Ref('content') private readonly defaultContent: HTMLElement;

  private popoverInstance: any = null;

  @Watch('show', { immediate: true })
  showChange(v) {
    if (v) {
      this.$nextTick(() => {
        this.initPopover();
      });
    } else {
      this.hiddenPopover();
    }
  }

  @Emit('on-hidden')
  handleHidden() {
    this.hiddenPopover();
    return 'hidden';
  }

  initPopover() {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.target, {
        content: this.defaultContent,
        trigger: 'manual',
        theme: 'light cycle-list-wrapper',
        interactive: true,
        arrow: false,
        placement: 'bottom-start',
        boundary: 'window',
        maxWidth: 300,
        delay: 100,
        offset: -1,
        distance: 12,
        followCursor: false,
        flip: true,
        // duration: [275, 250],
        animation: 'slide-toggle',
        onHidden: () => {
          this.handleHidden();
          this.popoverInstance?.destroy();
          this.popoverInstance = null;
        },
      });
    }
    this.popoverInstance?.show();
  }

  hiddenPopover() {
    this.popoverInstance?.hide();
  }

  @Emit('on-select')
  handleSelect(v, i) {
    this.hiddenPopover();
    return { id: v, index: i };
  }

  @Emit('on-delete')
  handleDel() {
    this.hiddenPopover();
    return 'delete';
  }

  render() {
    return (
      <div
        style='display: none'
        class='select-menu-wrap'
      >
        <div
          ref='content'
          class='select-menu-content'
        >
          {this.list?.length ? (
            <ul
              style={{ minWidth: `${this.minWidth}px` }}
              class='default-content-list'
            >
              {this.list.map((item, index) => (
                <li
                  key={index}
                  class='list-item'
                  on-mousedown={() => this.handleSelect(item.id, index)}
                >
                  {item.name}
                </li>
              ))}
            </ul>
          ) : undefined}
          {!this.list.length && !this.needDelete ? <div class='no-list'>{this.$t('暂无可选项')}</div> : undefined}
          <div
            style={{ display: this.needDelete ? 'block' : 'none' }}
            class='del-btn'
            on-mousedown={this.handleDel}
          >
            {this.$t('删除')}
          </div>
        </div>
      </div>
    );
  }
}
