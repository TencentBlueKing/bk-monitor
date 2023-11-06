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
import { Component as tsc, modifiers } from 'vue-tsx-support';

import './icon-btn.scss';

interface IProps {
  icon?: string;
  title?: string;
  theme?: 'dark' | 'light';
  iconOnly?: boolean;
  options?: IIconBtnOptions[];
  checked?: boolean;
}
interface IEvents {
  onClick: Event;
  onShowChange: boolean;
  onSelected: IIconBtnOptions;
}
export interface IIconBtnOptions {
  id: unknown;
  name: string;
  icon?: string;
  style?: Record<string, string>;
  hasAuth?: boolean;
  action_id?: string;
}
@Component
export default class IconBtn extends tsc<IProps, IEvents> {
  /** icon */
  @Prop({ type: String, default: 'icon-jia' }) icon: string;
  /** 按钮文字 */
  @Prop({ type: String, default: '' }) title: string;
  /** 主题 */
  @Prop({ type: String, default: 'dark' }) theme: 'dark' | 'light';
  /** 纯icon */
  @Prop({ type: Boolean, default: false }) iconOnly: boolean;
  /** 列表数据 */
  @Prop({ type: Array, default: () => [] }) options: IIconBtnOptions[];
  /** 是否选中 */
  @Prop({ type: Boolean, default: false }) checked: boolean;
  @Ref() optionsPopoverRef: any;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  localValue = null;

  optionsActive = false;

  get isChecked() {
    return this.checked || this.optionsActive;
  }
  get hasOptions() {
    return !!this.options.length;
  }

  @Emit('click')
  handleClick(evt: Event) {
    return evt;
  }

  @Emit('showChange')
  handleOptionsShow(show: boolean): boolean {
    this.optionsActive = show;
    return show;
  }

  @Emit('selected')
  handleSelected(item: IIconBtnOptions) {
    this.handleHide();
    return item;
  }

  handleHide() {
    this.optionsPopoverRef.instance.hide();
  }
  render() {
    const btnTpl = (
      <span
        class={[
          'icon-btn',
          this.theme,
          { 'only-icon': this.iconOnly, checked: this.isChecked, 'has-title': !!this.title }
        ]}
        onClick={this.handleClick}
      >
        {this.$slots.icon || (this.icon && <i class={['icon-monitor', this.icon]}></i>)}
        {this.title && <span>{this.title}</span>}
      </span>
    );
    return (
      <span onClick={modifiers.stop(() => {})}>
        {this.hasOptions ? (
          <bk-popover
            ref='optionsPopoverRef'
            trigger='click'
            placement='bottom-start'
            theme='dark icon-btn'
            animation='slide-toggle'
            // width={74}
            arrow={false}
            offset={-1}
            distance={12}
            onShow={() => this.handleOptionsShow(true)}
            onHide={() => this.handleOptionsShow(false)}
          >
            {btnTpl}
            <div
              slot='content'
              class='icon-options-list'
            >
              {this.options.map(opt => (
                <div
                  class='icon-option'
                  v-authority={{ active: !opt.hasAuth }}
                  onClick={() =>
                    opt.hasAuth ? this.handleSelected(opt) : this.handleShowAuthorityDetail(opt.action_id)
                  }
                >
                  {!!opt.icon && (
                    <i
                      class={['icon-monitor', 'option-icon', opt.icon]}
                      style={{ ...opt.style }}
                    ></i>
                  )}
                  <span>{opt.name}</span>
                </div>
              ))}
            </div>
          </bk-popover>
        ) : (
          btnTpl
        )}
      </span>
    );
  }
}
