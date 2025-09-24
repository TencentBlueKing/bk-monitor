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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { xssFilter } from 'monitor-common/utils';

import { isVariableName } from '../../variables/template/utils';
import { replaceContent } from '@/components/retrieval-filter/query-string-utils';

import type { IVariablesItem } from '../type/query-config';

import './expression-creator.scss';

interface IProps {
  value?: string;
  variables?: IVariablesItem[];
  onChange?: (val: string) => void;
  onCreateVariable?: (val: string[]) => void;
}

@Component
export default class ExpressionCreator extends tsc<IProps> {
  @Prop({ default: () => [] }) variables: IVariablesItem[];

  @Prop({ default: '' }) value: string;

  elEdit: HTMLInputElement = null;
  inputValue = '';
  active = false;

  vars = [];

  @Watch('value', { immediate: true })
  handleWatchValue(val: string) {
    if (this.inputValue !== val) {
      this.inputValue = val;
      this.$nextTick(() => {
        this.handleSetInputParse(val, false);
      });

      this.active = false;
    }
  }

  mounted() {
    this.elEdit = this.$el.querySelector('.expression-input');
    this.handleSetInputParse(this.value, false);
    this.active = false;
  }

  handleInput(e: InputEvent) {
    const target = e.target as HTMLElement;
    this.inputValue = target.textContent;
  }

  handleSetInputParse(val: string, isFocus = true, getVariables?: (val: string[]) => void) {
    const matches = val.match(/(\$\{[^}]+\})|(\$|[^$]+)/g)?.filter(item => item) || [];
    const variables = [];
    const str = matches
      .map(item => {
        if (isVariableName(item)) {
          variables.push(item);
          return `<span style="color: #E54488;">${xssFilter(item)}</span>`;
        }
        return xssFilter(item);
      })
      .join('');
    getVariables?.(variables);
    if (isFocus) {
      replaceContent(this.elEdit, str);
    } else {
      this.elEdit.innerHTML = str;
    }
  }

  handleFocus() {
    this.active = true;
  }
  handleBlur() {
    this.active = false;
    this.handleSetInputParse(this.inputValue, false, vars => {
      this.vars = vars;
      for (const v of this.vars) {
        this.$emit('createVariable', v);
      }
    });
    this.$emit('change', this.inputValue);
  }

  handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault(); // 阻止默认的换行行为
      // 如果需要执行其他操作（如提交），可以在这里添加
      this.handleSetInputParse(this.inputValue, true, vars => {
        this.vars = vars;
        for (const v of this.vars) {
          this.$emit('createVariable', v);
        }
      });
      this.$emit('change', this.inputValue);
      return false;
    }
  }

  render() {
    return (
      <div class='template-expression-creator-component'>
        <div class='expression-label'>{this.$t('表达式')}</div>
        <div class={['expression-input-wrap', { focus: this.active }]}>
          <div
            class='expression-input'
            contenteditable={true}
            data-placeholder={this.inputValue ? '' : this.$t('支持四则运算 + - * / % ^ ( ) ,如(A+B)/100')}
            spellcheck={false}
            onBlur={this.handleBlur}
            // onCompositionend={() => {
            //   this.isComposing = false;
            // }}
            // onCompositionstart={() => {
            //   this.isComposing = true;
            // }}
            onFocus={this.handleFocus}
            onInput={this.handleInput}
            onKeydown={this.handleKeydown}
          />
        </div>
      </div>
    );
  }
}
