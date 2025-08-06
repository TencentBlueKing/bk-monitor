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

import type { BasicInfoData, BasicInfoProps } from './typing';

import './basic-info.scss';

interface BasicInfoCreateEvents {
  onChange(data: BasicInfoData): void;
}

@Component
export default class BasicInfoCreate extends tsc<BasicInfoProps, BasicInfoCreateEvents> {
  @Prop() readonly formData: BasicInfoData;

  @Ref('form') formRef!: any;

  rules = {
    name: [
      {
        required: true,
        message: window.i18n.t('模版名称必填'),
        trigger: 'blur',
      },
    ],
    effect: [
      {
        required: true,
        message: window.i18n.t('生效范围必填'),
        trigger: 'blur',
      },
    ],
  };

  handleNameChange(value: string) {
    this.$emit('onChange', {
      ...this.formData,
      name: value,
    });
  }

  handleEffectChange(value: string) {
    this.$emit('onChange', {
      ...this.formData,
      effect: value,
    });
  }

  handleDescChange(value: string) {
    this.$emit('onChange', {
      ...this.formData,
      desc: value,
    });
  }

  validate() {
    return this.formRef.validate();
  }

  render() {
    return (
      <div class='basic-info create'>
        <div class='title'>{this.$t('基本信息')}</div>

        <bk-form
          ref='form'
          class='basic-info-form'
          {...{
            props: {
              model: this.formData,
              rules: this.rules,
            },
          }}
          form-type='vertical'
        >
          <bk-form-item
            class='w50'
            error-display-type='normal'
            label={this.$t('模版名称')}
            property='name'
            required
          >
            <bk-input
              value={this.formData.name}
              onChange={this.handleNameChange}
            />
          </bk-form-item>
          <bk-form-item
            class='w50'
            error-display-type='normal'
            label={this.$t('生效范围')}
            property='effect'
            required
          >
            <bk-select />
          </bk-form-item>
          <bk-form-item
            class='w100'
            error-display-type='normal'
            label={this.$t('模板说明')}
            property='desc'
          >
            <bk-input
              type='textarea'
              value={this.formData.desc}
              onChange={this.handleEffectChange}
            />
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
