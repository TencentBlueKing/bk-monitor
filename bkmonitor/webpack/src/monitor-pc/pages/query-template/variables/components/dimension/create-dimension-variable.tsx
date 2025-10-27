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
import { Component, Mixins, Prop, Ref } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import VariableFormMixin from '../../mixins/VariableFormMixin';
import VariableCommonForm from '../common-form/variable-common-form';

import type { IVariableFormEvents } from '../../../typings';
import type { DimensionVariableModel } from '../../index';
interface DimensionVariableEvents extends IVariableFormEvents {
  onDefaultValueChange: (val: string[]) => void;
  onValueChange: (val: string[]) => void;
}
interface DimensionVariableProps {
  variable: DimensionVariableModel;
}

@Component
class CreateDimensionVariable extends Mixins(VariableFormMixin) {
  @Prop({ type: Object, required: true }) variable!: DimensionVariableModel;
  @Ref() variableCommonForm!: VariableCommonForm;

  /** 可选维度 */
  options: string[] = [];

  rules = {
    options: [
      {
        required: true,
        message: this.$t('可选维度值必选'),
        trigger: 'blur',
      },
    ],
  };

  handleOptionsSelect(options: string[]) {
    const hasAll = this.options.includes('all');
    if (hasAll) {
      this.options = options.filter(item => item !== 'all');
    } else if (options.includes('all')) {
      this.options = ['all'];
    } else {
      this.options = options;
    }
  }

  /** 弹窗关闭的时候才进行传值 */
  handleOptionsToggle(show: boolean) {
    if (show) {
      this.options = this.variable.options;
    } else {
      let defaultValue = this.variable.data.defaultValue || [];
      const isAll = this.options.includes('all');
      const selectList = isAll ? this.variable.dimensionList.map(item => item.id) : this.options;
      /**
       * 全部维度：使用默认值
       * 非全部维度：过滤掉不在维度列表中的默认值
       */
      if (!isAll) {
        defaultValue = defaultValue.filter(item => selectList.includes(item));
      }

      let value = this.variable.value || [];
      /** 如果没有编辑过值，直接使用默认值 */
      if (!this.variable.isValueEditable) {
        value = defaultValue;
      } else if (selectList.length) {
        /** 判断编辑值是否在维度列表中 */
        value = value.filter(item => selectList.includes(item));
      }

      this.handleOptionsChange(this.options);
      this.handleDefaultValueChange(defaultValue);
      this.handleValueChange(value);
    }
  }

  defaultValueChange(defaultValue: string[]) {
    let value = this.variable.value || [];
    if (!this.variable.isValueEditable) {
      value = defaultValue;
    }
    this.handleDefaultValueChange(defaultValue);
    this.handleValueChange(value);
  }

  validateForm() {
    return this.variableCommonForm.validateForm();
  }

  mounted() {
    this.options = this.variable.options;
  }

  render() {
    return (
      <div class='dimension-variable'>
        <VariableCommonForm
          ref='variableCommonForm'
          data={this.variable.data}
          rules={this.rules}
          onAliasChange={this.handleAliasChange}
          onDescChange={this.handleDescChange}
          onNameChange={this.handleNameChange}
        >
          <bk-form-item label={this.$t('关联指标')}>
            <bk-input
              value={this.variable.metric?.metric_id}
              readonly
            />
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            label={this.$t('可选维度')}
            property='options'
            required
          >
            <bk-select
              clearable={false}
              selected-style='checkbox'
              value={this.options}
              collapse-tag
              display-tag
              multiple
              searchable
              onSelected={this.handleOptionsSelect}
              onToggle={this.handleOptionsToggle}
            >
              <bk-option
                id='all'
                name='- ALL -'
              />
              {this.variable.dimensionList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={this.$t('默认值')}
            property='defaultValue'
          >
            <bk-select
              clearable={false}
              value={this.variable.defaultValue}
              collapse-tag
              display-tag
              multiple
              searchable
              onChange={this.defaultValueChange}
            >
              {this.variable.dimensionOptionsMap.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </bk-form-item>
        </VariableCommonForm>
      </div>
    );
  }
}

export default tsx.ofType<DimensionVariableProps, DimensionVariableEvents>().convert(CreateDimensionVariable);
