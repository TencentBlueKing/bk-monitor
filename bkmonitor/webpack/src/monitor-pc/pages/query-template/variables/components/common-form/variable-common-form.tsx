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
import { Component, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { IVariableData, IVariableModel } from '../../../typings/variables';
import type { VariableModelType } from '../../index';

import './variable-common-form.scss';
interface VariableCommonFormEvents {
  onDataChange: (data: IVariableModel) => void;
}

interface VariableCommonFormProps {
  data: IVariableData;
  rules?: Record<string, Record<string, any>[]>;
}

@Component
export default class VariableCommonForm extends tsc<VariableCommonFormProps, VariableCommonFormEvents> {
  @Prop({ type: Object, required: true }) data!: IVariableData;
  @Prop({ type: Object, default: () => ({}) }) rules: VariableCommonFormProps['rules'];
  @Ref('form') formRef: any;

  @InjectReactive({
    from: 'variableList',
    default: () => [],
  })
  variableList: VariableModelType[];

  get formRules() {
    return {
      name: [
        { required: true, message: this.$t('变量名必填'), trigger: 'blur' },
        { validator: this.handleCheckName, message: this.$t('变量名不能重复'), trigger: 'blur' },
      ],
      ...this.rules,
    };
  }

  handleCheckName(val: string) {
    const valid = this.variableList.find(item => item.name === val && item.id !== this.data.id);
    console.log(valid, val);
    return !valid;
  }

  handleNameChange(value: string) {
    this.handleDataChange({ ...this.data, name: value ? `\${${value}}` : '' });
  }

  handleAliasChange(value: string) {
    this.handleDataChange({ ...this.data, alias: value });
  }

  handleDescChange(value: string) {
    this.handleDataChange({ ...this.data, desc: value });
  }

  handleDataChange(value: IVariableData) {
    delete value.variableName;
    this.$emit('dataChange', value);
  }

  validateForm() {
    return this.formRef.validate();
  }

  render() {
    return (
      <bk-form
        ref='form'
        class='variable-common-form'
        {...{ props: { model: this.data, rules: this.formRules } }}
        label-width={76}
      >
        <bk-form-item
          class='variable-name-form-item'
          error-display-type='normal'
          label={this.$t('变量名')}
          property='name'
          required
        >
          <bk-input
            class='variable-name-input'
            value={this.data.variableName}
            onChange={this.handleNameChange}
          >
            <template slot='prepend'>
              <div class='group-text'>{'${'}</div>
            </template>
            <template slot='append'>
              <div class='group-text'>{'}'}</div>
            </template>
          </bk-input>
        </bk-form-item>
        <bk-form-item
          desc={{
            content: `${this.$t('消费场景优先显示“变量别名”')}<br />${this.$t('变量别名留空，则显示“变量名”')}`,
            width: 200,
            allowHTML: true,
          }}
          label={this.$t('变量别名')}
          property='alias'
        >
          <bk-input
            value={this.data.alias}
            onChange={this.handleAliasChange}
          />
        </bk-form-item>
        <bk-form-item
          desc={{
            content: this.$t('消费场景，hover 变量名 / 别名的 label，可以显示“变量描述”'),
            width: 200,
          }}
          label={this.$t('变量描述')}
          property='desc'
        >
          <bk-input
            maxlength={100}
            type='textarea'
            value={this.data.desc}
            onChange={this.handleDescChange}
          />
        </bk-form-item>
        {this.$slots.default}
      </bk-form>
    );
  }
}
