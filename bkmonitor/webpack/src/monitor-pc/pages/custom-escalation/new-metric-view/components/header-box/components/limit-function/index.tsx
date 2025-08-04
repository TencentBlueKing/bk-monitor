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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

interface IEmit {
  onChange: (value: IProps['value']) => void;
}

interface IProps {
  value: {
    function: string;
    limit: number;
  };
}

const functionList = ['top', 'bottom'];

const genDefaultValue = (payload: Partial<IProps['value']>) => ({
  function: payload.function || 'top',
  limit: payload.limit || 0,
});

const renderFunction = (str: string) =>
  String(str ?? '')
    .toLowerCase()
    .replace(/\b\w/g, char => char.toUpperCase());

@Component
export default class LimitFunction extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: genDefaultValue }) readonly value: IProps['value'];

  @Ref('popoverRef') popoverRef: any;

  localFunction = '';

  @Watch('value', { immediate: true })
  valueChange() {
    if (this.value.function) {
      this.localFunction = this.value.function;
    }
  }

  handleFunctionChange(value: string) {
    this.localFunction = value;
    this.$emit('change', {
      function: this.localFunction,
      limit: Number(this.value.limit),
    });
    this.popoverRef.hideHandler();
  }

  handleLimitChange(value: number) {
    this.$emit('change', {
      function: this.localFunction,
      limit: Number(value),
    });
  }

  render() {
    return (
      <div class='new-metric-view-limit-function'>
        <div
          class='label'
          data-role='param-label'
        >
          <div>{this.$t('限制')}</div>
        </div>
        <bk-popover
          ref='popoverRef'
          tippyOptions={{
            placement: 'bottom-start',
            arrow: false,
            distance: 8,
            theme: 'light new-metric-view-limit-function',
            trigger: 'click',
            hideOnClick: true,
          }}
        >
          <div class='value-handler'>
            {renderFunction(this.localFunction)}
            <i class='icon-monitor icon-mc-triangle-down' />
          </div>
          <div
            class='item-wrapper'
            slot='content'
          >
            {functionList.map(item => (
              <div
                key={item}
                class={{
                  item: true,
                  'is-active': this.localFunction === item,
                }}
                onClick={() => this.handleFunctionChange(item)}
              >
                {renderFunction(item)}
              </div>
            ))}
          </div>
        </bk-popover>
        <div class='line' />
        <bk-input
          class='limit-input'
          min={0}
          size='small'
          type='number'
          value={this.value.limit}
          onChange={this.handleLimitChange}
        />
      </div>
    );
  }
}
