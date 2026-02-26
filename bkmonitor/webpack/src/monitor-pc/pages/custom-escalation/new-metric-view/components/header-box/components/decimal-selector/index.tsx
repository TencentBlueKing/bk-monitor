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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

interface IEmit {
  onChange: (value: number) => void;
}

interface IProps {
  value: number;
}

@Component
export default class DecimalSelector extends tsc<IProps, IEmit> {
  @Prop({ type: Number, default: 0 }) readonly value: IProps['value'];

  @Ref('popoverRef') popoverRef: any;

  localValue = 0;

  get currentDecimalName() {
    return this.$t('{0} 位', [this.localValue]);
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = this.value;
  }

  triggerChange() {
    if (this.value !== this.localValue) {
      this.$emit('change', this.localValue);
    }
  }

  handleDecimalChange(value: number) {
    this.localValue = value;
    this.triggerChange();
    this.popoverRef.hideHandler();
  }

  render() {
    return (
      <div class='new-metric-view-decimal-selector'>
        <div class='label'>
          <div>{this.$t('数据后保留小数位')}</div>
        </div>
        <bk-popover
          ref='popoverRef'
          tippy-options={{
            placement: 'bottom',
            arrow: false,
            distance: 8,
            hideOnClick: true,
          }}
          theme='light new-metric-view-decimal-selector'
          trigger='click'
        >
          <div style='display: flex; align-items: center; height: 34px; padding: 0 6px; cursor: pointer'>
            {this.currentDecimalName}
            <i class='icon-monitor icon-mc-triangle-down' />
          </div>
          <div
            class='wrapper'
            slot='content'
          >
            {new Array(5).fill(0).map((_, index) => (
              <div
                key={index}
                class={{
                  'decimal-item': true,
                  'is-active': index === this.localValue,
                }}
                onClick={() => this.handleDecimalChange(index)}
              >
                {this.$t('{0} 位', [index])}
              </div>
            ))}
          </div>
        </bk-popover>
      </div>
    );
  }
}
