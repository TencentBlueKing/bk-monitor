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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type SelectTypeEnum, SelectType } from './typing';

import './across-page-selection.scss';

interface IProps {
  value?: SelectTypeEnum;
  onChange?: (v: SelectTypeEnum) => void;
}

@Component
export default class AcrossPageSelection extends tsc<IProps> {
  @Prop({ default: SelectType.UN_SELECTED, type: Number }) value: SelectTypeEnum;

  @Ref('popover') readonly popover;

  selectList = [
    {
      id: SelectType.SELECTED,
      name: window.i18n.t('本页全选'),
    },
    {
      id: SelectType.ALL_SELECTED,
      name: window.i18n.t('跨页全选'),
    },
  ];

  show = false;

  handleSelect(id: SelectTypeEnum) {
    this.popover.instance.hide();
    this.$emit('change', id);
  }

  handleChangeValue(val: boolean) {
    if (val) {
      this.$emit('change', SelectType.SELECTED);
    } else {
      this.$emit('change', SelectType.UN_SELECTED);
    }
  }

  render() {
    return (
      <div class='across-page-selection-component'>
        <bk-checkbox
          class={{
            'all-checked': this.value === SelectType.ALL_SELECTED,
          }}
          indeterminate={this.value === SelectType.HALF_SELECTED}
          value={[SelectType.ALL_SELECTED, SelectType.SELECTED].includes(this.value as any)}
          onChange={this.handleChangeValue}
        />
        <bk-popover
          ref='popover'
          arrow={false}
          distance={0}
          offset={'-10, 0'}
          placement={'bottom-start'}
          theme={'across-page-selection-component'}
          trigger={'click'}
          on-hide={() => {
            this.show = false;
          }}
          on-show={() => {
            this.show = true;
          }}
        >
          <i class={['icon-monitor', this.show ? 'icon-arrow-up' : 'icon-arrow-down']} />
          <ul
            class='dropdown-list'
            slot='content'
          >
            {this.selectList.map(item => {
              return (
                <li
                  key={`${item.id}`}
                  class={['list-item', { 'list-item-active': this.value === item.id }]}
                  onClick={() => {
                    this.handleSelect(item.id);
                  }}
                >
                  {item.name}
                </li>
              );
            })}
          </ul>
        </bk-popover>
      </div>
    );
  }
}
