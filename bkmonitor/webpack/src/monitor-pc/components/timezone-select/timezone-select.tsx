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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import timezoneList from './timezone';

import './timezone-select.scss';

interface IProps {
  value: string;
  onChange?: (v: string) => void;
}

@Component
export default class TimezoneSelect extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;

  localValue = '';

  curInfo = {
    name: '',
    z: '',
    Z: ''
  };

  toggle = false;

  @Watch('value', { immediate: true })
  handleWatchValue(v: string) {
    if (v !== this.localValue) {
      this.localValue = v;
      this.curInfo = timezoneList.find(item => item.name === v);
    }
  }

  handleSelected(v: string) {
    this.curInfo = timezoneList.find(item => item.name === v);
    this.$emit('change', v);
  }

  handleToggle(v: boolean) {
    this.toggle = v;
  }

  render() {
    return (
      <bk-select
        v-model={this.localValue}
        ext-popover-cls={'timezone-select-component-pop'}
        class='time-select-component'
        searchable
        onSelected={this.handleSelected}
        onToggle={this.handleToggle}
      >
        <div
          slot='trigger'
          class='input-wrap'
        >
          <div class='left'>
            {!!this.curInfo.name ? (
              <span>{`${this.curInfo.name}, ${this.curInfo.z}`}</span>
            ) : (
              <span class='placeholder'>{this.$t('请选择时区')}</span>
            )}
          </div>
          <div class='right'>
            {!!this.curInfo.name && <bk-tag>{`UTC${this.curInfo.Z}`}</bk-tag>}
            <div class='icon-wrap'>
              <span class={['icon-monitor icon-arrow-down', { active: this.toggle }]}></span>
            </div>
          </div>
        </div>
        {timezoneList.map(item => (
          <bk-option
            key={item.name}
            id={item.name}
            name={item.name}
          >
            <span class='timezone-option'>
              <span>{`${item.name}, ${item.z}`}</span>
              <bk-tag>{`UTC${item.Z}`}</bk-tag>
            </span>
          </bk-option>
        ))}
      </bk-select>
    );
  }
}
