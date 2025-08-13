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

import type { IAddItemData } from '../space-add-list/space-add-list';

import './space-add-item.scss';

interface IEvents {
  onChecked: boolean;
}
interface IProps {
  checked: boolean;
  data: IAddItemData;
  disabled?: boolean;
}
@Component
export default class SpaceAddItem extends tsc<IProps, IEvents> {
  /** 全部的数据 */
  @Prop({ type: Object }) data: IAddItemData;
  /** 选中状态 */
  @Prop({ default: false, type: Boolean }) checked: boolean;
  /** 是否禁止选择 */
  @Prop({ default: false, type: Boolean }) disabled: boolean;

  @Emit('checked')
  handleChecked() {
    return !this.checked;
  }

  render() {
    return (
      <div class={['space-add-item-wrap', { checked: this.checked, disabled: this.disabled }]}>
        <div
          class={['spance-add-header', { checked: this.checked, disabled: this.disabled }]}
          onClick={this.handleChecked}
        >
          <div class='title-wrap'>
            <i class={['title-icon', 'icon-monitor', this.data.icon]} />
            <div class='title-text'>{this.data.name}</div>
          </div>
          <div class='header-desc'>{this.data.desc}</div>
          <div class={['item-radio', { checked: this.checked }]}>
            {this.checked && <i class='icon-monitor icon-mc-check-fill' />}
          </div>
        </div>
        {this.checked && !this.disabled && (
          <div class={['spance-add-content', { checked: this.checked }]}>
            <div class='spance-add-content-mian'>{this.$slots.default}</div>
          </div>
        )}
      </div>
    );
  }
}
