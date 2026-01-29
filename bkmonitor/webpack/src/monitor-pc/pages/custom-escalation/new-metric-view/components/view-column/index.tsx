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
import { Component, Model, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

interface IEmit {
  onChange: (value: number) => void;
}

@Component
export default class ViewColumn extends tsc<object, IEmit> {
  @Model('change', { type: Number, default: 1 }) readonly value: number;

  @Ref('popoverRef') readonly popoverRef: any;

  localValue = 1;

  columnList = [
    {
      id: 1,
      name: this.$t('1 列'),
    },
    {
      id: 2,
      name: this.$t('2 列'),
    },
    {
      id: 3,
      name: this.$t('3 列'),
    },
  ];

  get renderText() {
    return this.columnList.find(item => item.id === this.value).name || '--';
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = this.value;
  }

  handleChange(value: number) {
    this.$emit('change', value);
    this.popoverRef.hideHandler();
  }

  render() {
    return (
      <bk-popover
        ref='popoverRef'
        tippyOptions={{
          placement: 'bottom-end',
          arrow: false,
          distance: 8,
          theme: 'light new-metric-view-view-column common-monitor',
          trigger: 'click',
        }}
      >
        <div class='new-metric-view-view-column-btn'>
          <i
            style='margin-right: 4px;'
            class='icon-monitor icon-card'
          />
          {this.renderText}
        </div>
        <div
          class='wrapper'
          slot='content'
        >
          {this.columnList.map(item => (
            <div
              key={item.id}
              class={{
                item: true,
                'is-active': item.id === this.localValue,
              }}
              onClick={() => this.handleChange(item.id)}
            >
              {item.name}
            </div>
          ))}
        </div>
      </bk-popover>
    );
  }
}
