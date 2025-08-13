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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import KeySelect from './panel-key-select';
import ValueSelect from './panel-value-select';

import './index.scss';

export interface IMetrics {
  alias: string;
  metric_name: string;
  dimensions: {
    alias: string;
    name: string;
  }[];
}

export interface IValue {
  condition: string;
  key: string;
  method: string;
  value: string[];
}

export const methodMap = {
  eq: '=',
  gt: '>',
  gte: '>=',
  lt: '<',
  lte: '<=',
  neq: '!=',
  reg: 'regex',
  nreg: 'nregex',
};

interface IEmit {
  onChange: (value: IProps['value']) => void;
}

interface IProps {
  metricsList: IMetrics[];
  value?: IValue;
}

const genDefaultVallue = (payload: Partial<IProps['value']> = {}) => ({
  key: payload.key || '',
  method: payload.method || 'eq',
  value: [...(payload.value || [])],
  condition: payload.condition || 'and',
});

const isMacOs = /Mac OS X ([\d_]+)/.test(navigator.userAgent);

let triggerHandler: HTMLElement;
let instance: any;

@Component
export default class ValueEditPanel extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: genDefaultVallue }) readonly value: IProps['value'];
  @Prop({ type: Array, required: true }) readonly metricsList: IProps['metricsList'];

  @Ref('popoverRef') popoverRef: HTMLDivElement;

  currentKey = '';
  localValue: IProps['value'] = genDefaultVallue();
  isShown = false;

  get isSubmitDisabled() {
    return this.localValue.value.length < 1;
  }

  // 实例方法，外部通过实例调用
  show(handlerEl: HTMLElement) {
    if (instance) {
      if (triggerHandler === handlerEl) {
        return;
      }
      instance.hide();
      instance.destroy();
      instance = undefined;
    }

    triggerHandler = handlerEl;
    // 延迟创建实例，避免在前一个实例未销毁时重复创建实例导致冲突
    setTimeout(() => {
      instance = this.$bkPopover(handlerEl, {
        content: this.popoverRef,
        allowHTML: true,
        arrow: false,
        placement: 'bottom-start',
        theme: 'light filter-conditions-value-edit-panel',
        interactive: true,
        animation: 'slide-toggle',
        zIndex: 1000,
        distance: 16,
        trigger: 'manual',
        hideOnClick: true,
        onShow: () => {
          this.isShown = true;
        },
        onHidden: () => {
          if (instance) {
            instance.destroy();
            instance = undefined;
          }
          this.isShown = false;
        },
      });
      this.localValue = genDefaultVallue(this.value);
      instance.show();
    });
  }
  // 实例方法，外部通过实例调用
  update() {
    if (instance) {
      instance.popperInstance.update();
    }
  }
  hide() {
    if (instance) {
      instance.hide();
      instance.destroy();
      instance = undefined;
    }
  }

  handleKeyChange(key: string) {
    this.localValue = genDefaultVallue({
      key,
    });
  }

  handleMethodChange(value: string) {
    this.localValue.method = value;
  }
  handleValueChange(value: string[]) {
    this.localValue.value = value;
  }

  handleConfirm() {
    if (this.localValue.value.length > 0) {
      this.$emit('change', {
        ...this.localValue,
      });
    }

    instance.hide();
    instance.destroy();
  }

  handleCancel() {
    instance.hide();
    instance.destroy();
  }

  handleQuickOperation(event: KeyboardEvent) {
    if (!instance || this.isSubmitDisabled) {
      return;
    }
    if (event.code === 'Enter') {
      if ((isMacOs && event.metaKey) || (!isMacOs && event.ctrlKey)) {
        this.handleConfirm();
        return;
      }
    }

    if (event.code === 'Escape') {
      this.handleCancel();
    }
  }

  mounted() {
    document.body.addEventListener('keydown', this.handleQuickOperation);
    this.$once('hook:beforeDestroy', () => {
      document.body.removeEventListener('keydown', this.handleQuickOperation);
    });
  }

  beforeDestroy() {
    if (instance) {
      instance.hide();
      instance.destroy();
      instance = undefined;
    }
  }

  render() {
    return (
      <div style='display: none'>
        <div
          ref='popoverRef'
          class='filter-conditions-value-edit-panel'
        >
          {this.isShown && (
            <div class='layout-wrapper'>
              <div class='layout-left'>
                <KeySelect
                  metricsList={this.metricsList}
                  value={this.localValue.key}
                  onChange={this.handleKeyChange}
                />
              </div>
              <div
                key={this.localValue.key}
                class='layout-right'
              >
                <ValueSelect
                  keyName={this.localValue.key}
                  method={this.localValue.method}
                  value={this.localValue.value}
                  onMethondChange={this.handleMethodChange}
                  onValueChange={this.handleValueChange}
                />
              </div>
            </div>
          )}
          <div class='layout-footer'>
            <div class='desc-box'>
              <div class='desc-tag'>
                <i class='icon-monitor icon-mc-triangle-down' />
              </div>
              <div class='desc-tag'>
                <i class='icon-monitor icon-mc-triangle-down' />
              </div>
              {this.$t('移动光标')}
            </div>
            <div class='desc-box'>
              <div class='desc-tag'>Enter</div>
              {this.$t('选中')}
            </div>
            <div class='desc-box'>
              <div class='desc-tag'>Esc</div>
              {this.$t('收起查询')}
            </div>
            <div class='desc-box'>
              <div class='desc-tag'> {isMacOs ? 'Cmd + Enter' : 'Ctrl + Enter'}</div>
              {this.$t('提交查询')}
            </div>
            <bk-button
              style='margin-left: auto'
              disabled={this.isSubmitDisabled}
              theme='primary'
              onClick={this.handleConfirm}
            >
              {isMacOs ? this.$t('确定 Cmd + Enter') : this.$t('确定 Ctrl + Enter')}
            </bk-button>
            <bk-button
              style='margin-left: 8px'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );
  }
}
