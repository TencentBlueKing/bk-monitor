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
import { Component, Emit, InjectReactive, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { IOption } from '../../pages/monitor-k8s/typings';
import { getPopoverWidth } from '../../utils';

import './custom-select.scss';

export interface ICustomSelectProps {
  value?: string[] | string;
  multiple?: boolean;
  options?: IOption[];
  searchable?: boolean;
}
export interface ICustomSelectEvents {
  onSelected: ICustomSelectProps['value'];
}
/**
 * 自定义触发目标的下拉选择器功能跟bk-select一致
 */
@Component
export default class CustomSelect extends tsc<ICustomSelectProps, ICustomSelectEvents> {
  @Model('emitValue') value: string | string[];
  @Prop({ default: () => [], type: Array }) options: IOption[];
  @Ref() bkSelectRef: any;
  // 是否只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  isShow = false;

  @Emit('change')
  emitValue(val) {
    return val;
  }

  @Emit('showChange')
  handleShowChange(val: boolean) {
    return val;
  }

  /** bk-select属性 */
  get props() {
    return Object.assign(
      {
        value: this.value,
        'popover-min-width': 240,
        'popover-width': getPopoverWidth(this.options) || void 0,
        'popover-options': {
          boundary: 'window',
          onHide: () => {
            this.isShow = false;
            this.handleShowChange(false);
            return true;
          }
        },
        searchable: true
      },
      this.$attrs
    );
  }

  /**
   * @description: 展示下拉弹层
   */
  handleShowDropDown() {
    this.bkSelectRef.show();
    this.isShow = true;
    this.handleShowChange(true);
  }

  render() {
    return (
      <div class={['custom-select-wrap', this.theme]}>
        <span
          class={['custom-select-target', { active: this.isShow }]}
          onClick={this.handleShowDropDown}
        >
          {this.$slots.target ??
            (!this.readonly && (
              <span class='custom-select-add'>
                <i class='icon-monitor icon-mc-add'></i>
              </span>
            ))}
        </span>
        <bk-select
          ref='bkSelectRef'
          {...{
            props: this.props,
            on: {
              ...this.$listeners
            }
          }}
          class='bk-select-wrap'
        >
          {this.$slots.default}
        </bk-select>
      </div>
    );
  }
}
