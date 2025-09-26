/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Emit, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { TranslateResult } from 'vue-i18n';

import './operate-options.scss';

export interface IOperateOption {
  authority?: boolean;
  authorityDetail?: string;
  disable?: boolean;
  id: string;
  name?: string | TranslateResult;
  tip?: string;
  iconClassName?: string;
  isDanger?: boolean;
}
interface IOperateOptionsEvents {
  onOptionClick?: string;
}

interface IOperateOptionsProps {
  isClickShow?: boolean;
  isMouseOverShow?: boolean;
  options?: IOptions;
}

interface IOptions {
  outside?: IOperateOption[];
  popover?: IOperateOption[];
}

@Component({
  name: 'OperateOptions',
})
export default class OperateOptions extends tsc<IOperateOptionsProps, IOperateOptionsEvents> {
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Prop({ type: Object, default: () => ({}) }) options: IOptions;
  @Prop({ type: Boolean, default: false }) isMouseOverShow: boolean;
  @Prop({ type: Boolean, default: true }) isClickShow: boolean;
  // 文字左边展示icon
  @Prop({ type: Boolean, default: false }) isIconShow: boolean;

  @Ref('moreItems') moreItemsRef: HTMLDivElement;

  popoverInstance = null;

  @Emit('optionClick')
  handleOptionClick(id: string) {
    this.isMouseOverShow && this.handleHidden();
    return id;
  }

  handleShowPopover(e: Event) {
    e.stopPropagation();
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.moreItemsRef,
        arrow: false,
        trigger: this.isMouseOverShow ? 'mouseenter' : 'click',
        interactive: this.isMouseOverShow,
        placement: 'bottom',
        theme: 'light common-monitor',
        maxWidth: 520,
        duration: [200, 0],
        onHidden: () => {
          this.handleHidden();
        },
      });
    }
    this.popoverInstance?.show(100);
  }

  handleHidden() {
    document.querySelector('#directive-ele')?.remove();
    this.popoverInstance.destroy();
    this.popoverInstance = null;
  }

  render() {
    return (
      <div class='table-operate-options-component'>
        {this.options?.outside.map(item => (
          <span
            key={item.id}
            v-bk-tooltips={{
              content: item?.tip,
              placement: 'top',
              boundary: 'window',
              disabled: !item?.tip,
              allowHTML: false,
            }}
          >
            <bk-button
              class='options-item'
              v-authority={{ active: !item.authority }}
              disabled={Boolean(item.disable)}
              theme='primary'
              text
              on-click={() =>
                item.authority ? this.handleOptionClick(item.id) : this.handleShowAuthorityDetail(item.authorityDetail)
              }
            >
              {item.name}
            </bk-button>
          </span>
        ))}
        {this.options?.popover?.length ? (
          <div
            onClick={e => {
              if (!this.isClickShow) return;
              this.handleShowPopover(e);
            }}
            onMouseenter={e => {
              if (!this.isMouseOverShow) return;
              this.handleShowPopover(e);
            }}
          >
            {this.$slots?.trigger || (
              <div class='option-more'>
                <span class='bk-icon icon-more' />
              </div>
            )}
          </div>
        ) : undefined}
        <div style={{ display: 'none' }}>
          <div
            ref='moreItems'
            class='table-operate-options-component-more-items'
          >
            {this.options?.popover?.map(item => (
              <span
                key={item.id}
                class={['more-item', { authority: !item.authority }, { 'is-danger': item.isDanger}]}
                v-authority={{ active: !item.authority }}
                onClick={() =>
                  item.authority
                    ? this.handleOptionClick(item.id)
                    : this.handleShowAuthorityDetail(item.authorityDetail)
                }
              >
                {item.iconClassName && <i class={['icon-monitor', item.iconClassName]} />}
                {item.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
