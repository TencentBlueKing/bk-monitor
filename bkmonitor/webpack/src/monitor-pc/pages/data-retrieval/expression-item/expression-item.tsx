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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import FunctionSelect from '../../strategy-config/strategy-config-set-new/monitor-data/function-select';

import type { IDataRetrieval } from '../typings';

import './expression-item.scss';

interface IEvents {
  onChange: IDataRetrieval.IExpressionItem;
}
interface IProps {
  value: IDataRetrieval.IExpressionItem;
}
@Component
export default class ExpressionItem extends tsc<IProps, IEvents> {
  @Prop({ required: true, type: Object }) value: IDataRetrieval.IExpressionItem;

  localValue: IDataRetrieval.IExpressionItem = null;

  /** 缓存表达式 */
  expCache = '';

  @Watch('value', { immediate: true })
  valueChange(val: IDataRetrieval.IExpressionItem) {
    this.localValue = deepClone(val);
  }

  /**
   * @description: 表达式输入聚焦
   */
  handleExpFocus() {
    this.expCache = this.localValue.value;
  }
  /**
   * @description: 表达式失焦查询
   */
  handleExpressionBlur() {
    const isDiff = this.localValue.value !== this.expCache;
    if (isDiff) this.handleChange();
  }

  /**
   * 选择函数
   */
  handleFunctionsChange() {
    if (this.localValue.value.trim()) this.handleChange();
  }

  @Emit('change')
  handleChange() {
    return deepClone(this.localValue);
  }

  render() {
    return (
      <div class='expression-item-wrap'>
        <div class='expr-item'>
          <div class='expr-label'>{this.$t('表达式')}</div>
          <bk-input
            vModel={this.localValue.value}
            placeholder={this.$t('支持四则运算 + - * / % ^ ( ) ,如(A+B)/100')}
            onBlur={this.handleExpressionBlur}
            onFocus={this.handleExpFocus}
          />
        </div>
        <div class='expr-item'>
          <div class='expr-label'>{this.$t('函数')}</div>
          <FunctionSelect
            class='query-func-selector'
            v-model={this.localValue.functions}
            isExpSupport
            onValueChange={() => this.handleFunctionsChange()}
          />
        </div>
      </div>
    );
  }
}
