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
import { Component, Emit, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './operate-options.scss';

interface IOption {
  id: string;
  name?: string;
  authority?: boolean;
  disable?: boolean;
  authorityDetail?: string;
  tip?: string;
}
interface IOptions {
  outside?: IOption[];
  popover?: IOption[];
}

interface IOperateOptionsProps {
  options?: IOptions;
}

interface IOperateOptionsEvents {
  onOptionClick?: string;
}

@Component({
  name: 'OperateOptions'
})
export default class OperateOptions extends tsc<IOperateOptionsProps, IOperateOptionsEvents> {
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Prop({ type: Object, default: () => ({}) }) options: IOptions;

  @Ref('moreItems') moreItemsRef: HTMLDivElement;

  popoverInstance = null;

  @Emit('optionClick')
  handleOptionClick(id: string) {
    return id;
  }

  handleShowPopover(e: Event) {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.moreItemsRef,
        arrow: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light common-monitor',
        maxWidth: 520,
        duration: [200, 0],
        zIndex: 1000,
        onHidden: () => {
          this.popoverInstance.destroy();
          this.popoverInstance = null;
        }
      });
    }
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div class='table-operate-options-component'>
        {this.options?.outside.map(item => (
          <span
            v-bk-tooltips={{
              content: item?.tip,
              placement: 'top',
              boundary: 'window',
              disabled: !Boolean(item?.tip),
              allowHTML: false
            }}
          >
            <bk-button
              text
              theme='primary'
              class='options-item'
              v-authority={{ active: !item.authority }}
              disabled={Boolean(item.disable)}
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
            class='option-more'
            onClick={this.handleShowPopover}
          >
            <span class='bk-icon icon-more'></span>
          </div>
        ) : undefined}
        <div style={{ display: 'none' }}>
          <div
            class='table-operate-options-component-more-items'
            ref='moreItems'
          >
            {this.options?.popover?.map(item => (
              <span
                class='more-item'
                v-authority={{ active: !item.authority }}
                onClick={() =>
                  item.authority
                    ? this.handleOptionClick(item.id)
                    : this.handleShowAuthorityDetail(item.authorityDetail)
                }
              >
                {item.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
