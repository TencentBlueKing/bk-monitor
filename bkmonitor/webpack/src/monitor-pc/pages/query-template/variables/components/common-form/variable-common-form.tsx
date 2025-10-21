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
import { Component, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type VariableModelType, variableNameReg } from '../../index';

import type { IVariableData } from '../../../typings/variables';

import './variable-common-form.scss';
interface VariableCommonFormEvents {
  onAliasChange: (alias: string) => void;
  onDescChange: (desc: string) => void;
  onNameChange: (name: string) => void;
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

  /** 本地数据，因为变量名不规范的情况不把值传递给上层 */
  localName = '';

  get formData() {
    return {
      ...this.data,
      localName: this.localName,
    };
  }

  get formRules() {
    return {
      localName: [
        {
          validator: () => {
            return !!this.localName;
          },
          message: this.$t('变量名必填'),
          trigger: 'blur',
        },
        { validator: this.handleCheckName, message: this.$t('变量名不能重复'), trigger: 'blur' },
        {
          validator: () => {
            return variableNameReg.test(this.localName);
          },
          message: this.$t('1～50 字符，仅支持 大小写字母、数字、下划线、点'),
          trigger: 'blur',
        },
      ],
      ...this.rules,
    };
  }

  mounted() {
    this.localName = this.data.variableName;
  }

  handleCheckName() {
    const valid = this.variableList.find(item => item.variableName === this.localName && item.id !== this.data.id);
    return !valid;
  }

  handleNameChange(value: string) {
    this.localName = value;
  }

  emitNameChange(value: string) {
    if (!variableNameReg.test(value)) return;
    this.$emit('nameChange', value ? `\${${value}}` : '');
  }

  handleAliasChange(value: string) {
    this.$emit('aliasChange', value);
  }

  handleDescChange(value: string) {
    this.$emit('descChange', value);
  }

  validateForm() {
    return this.formRef.validate();
  }

  render() {
    return (
      <bk-form
        ref='form'
        class='variable-common-form'
        {...{ props: { model: this.formData, rules: this.formRules } }}
        label-width={76}
      >
        <bk-form-item
          class='variable-name-form-item'
          error-display-type='normal'
          label={this.$t('变量名')}
          property='localName'
          required
        >
          <bk-input
            class='variable-name-input'
            placeholder={this.$t('1～50 字符，仅支持 大小写字母、数字、下划线、点')}
            value={this.localName}
            onBlur={this.emitNameChange}
            onChange={this.handleNameChange}
            onEnter={this.emitNameChange}
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
          error-display-type='normal'
          label={this.$t('变量别名')}
          property='alias'
        >
          <bk-input
            value={this.formData.alias}
            onBlur={this.handleAliasChange}
            onEnter={this.handleAliasChange}
          />
        </bk-form-item>
        <bk-form-item
          desc={{
            content: this.$t('消费场景，hover 变量名 / 别名的 label，可以显示“变量描述”'),
            width: 200,
          }}
          label={this.$t('变量描述')}
          property='description'
        >
          <bk-input
            maxlength={100}
            type='textarea'
            value={this.formData.description}
            onBlur={this.handleDescChange}
            onEnter={this.handleDescChange}
          />
        </bk-form-item>
        {this.$slots.default}
      </bk-form>
    );
  }
}
