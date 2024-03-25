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

import './select-card-item.scss';

interface IProps {
  title: string;
  img: String;
  checked?: boolean;
  theme?: ThemeType;
  descData?: IDescData;
  mode?: 'normal' | 'small';
  multiple?: boolean;
}
export type ThemeType = 'system' | 'plugin' | 'lang' | 'intro';

export interface IDescData {
  name: string;
  isOfficial: boolean;
  heat: number;
}

interface IEvent {
  onClick: Event;
}

@Component
export default class SelectCardItem extends tsc<IProps, IEvent> {
  @Prop({ default: '', type: String }) title: string;
  @Prop({ default: '', type: String }) img: string;
  @Prop({ default: 'normal', type: String }) mode: IProps['mode'];
  @Prop({ default: false, type: Boolean }) checked: boolean;
  @Prop({ default: false, type: Boolean }) multiple: IProps['multiple'];
  @Prop({ default: 'system', type: String }) theme: ThemeType;
  @Prop({ default: () => ({ name: '', isOfficial: false, heat: 0 }) }) descData: IDescData;

  @Emit('click')
  handleClick(evt: Event) {
    return evt;
  }
  render() {
    return (
      <div
        class={[
          'select-card-item-wrap',
          `${this.theme}-theme`,
          `${this.mode}-mode`,
          {
            checked: this.checked,
            multiple: this.multiple
          }
        ]}
        onClick={this.handleClick}
      >
        {this.mode === 'normal' ? (
          <div class='select-card-item-main'>
            {this.multiple && this.checked && <span class='lang-checked-icon'></span>}
            <div class='img-contain'>
              <img
                src={this.img}
                alt='img'
              ></img>
            </div>
            <div class='item-title'>{this.title}</div>
            {this.theme === 'plugin' && (
              <div class='plugin-desc'>
                <span class='left-wrap'>
                  <span class='text'>{this.descData.name}</span>
                  {this.descData.isOfficial && <i class='icon-monitor icon-mc-official'></i>}
                </span>
                <span class='right-wrap'>
                  <span class='text'>{this.descData.heat}</span>
                  <i class='icon-monitor icon-mc-heat'></i>
                </span>
              </div>
            )}
          </div>
        ) : (
          <div class='select-card-item-main'>
            {this.multiple && this.checked && <span class='lang-checked-icon'></span>}
            <span class='img-contain'>
              <img
                src={this.img}
                alt='img'
              ></img>
            </span>
            <span class='item-text'>{this.title}</span>
          </div>
        )}
      </div>
    );
  }
}
