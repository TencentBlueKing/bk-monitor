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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { BasicInfoData } from '../../typings';

import './basic-info.scss';

interface BasicInfoEvents {
  onChange(data: BasicInfoData): void;
}

interface BasicInfoProps {
  formData: BasicInfoData;
  scene?: 'create' | 'edit';
}

@Component
export default class BasicInfo extends tsc<BasicInfoProps, BasicInfoEvents> {
  @Prop() readonly formData: BasicInfoData;
  @Prop({ type: String, default: 'create' }) readonly scene: 'create' | 'edit';

  @Ref('form') formRef!: any;

  get bizId() {
    return this.$store.getters.bizId;
  }

  /** 是否是全局模板 */
  get isGlobalTemplate() {
    return this.formData.space_scope.includes('all');
  }

  get bizList() {
    if (this.scene === 'create' || !this.isGlobalTemplate) return [...this.$store.getters.bizList];
    // 全局模板是全业务可见，目前全局模板只有编辑功能
    return [{ bk_biz_id: 'all', name: this.$t('全业务可见') }, ...this.$store.getters.bizList];
  }

  rules = {
    name: [
      {
        required: true,
        message: window.i18n.t('模板名称必填'),
        trigger: 'blur',
      },
      {
        validator: val => /^[a-z0-9_]{1,50}$/.test(val),
        message: window.i18n.t('1～50 字符，仅支持 英文小写、数字、下划线'),
        trigger: 'blur',
      },
    ],
    space_scope: [
      {
        required: true,
        message: window.i18n.t('生效范围必填'),
        trigger: 'blur',
      },
    ],
  };

  handleNameChange(value: string) {
    this.$emit('change', {
      ...this.formData,
      name: value,
    });
  }

  handleAliasChange(value: string) {
    this.$emit('change', {
      ...this.formData,
      alias: value,
    });
  }

  handleDeleteEffect(data) {
    this.handleEffectChange(this.formData.space_scope.filter(item => item !== data.id));
  }

  tagTpl(data) {
    return (
      <div class='tag'>
        <span class='tag-name'>{data.name}</span>
        {this.bizId !== data.bk_biz_id && data.bk_biz_id !== 'all' && (
          <i
            class='icon-monitor icon-mc-close'
            onClick={() => {
              this.handleDeleteEffect(data);
            }}
          />
        )}
      </div>
    );
  }

  handleEffectChange(value: (number | string)[]) {
    const space_scope = value;
    if (!value.includes(this.bizId)) {
      space_scope.unshift(this.bizId);
    }
    this.$emit('change', {
      ...this.formData,
      space_scope,
    });
  }

  handleDescChange(value: string) {
    this.$emit('change', {
      ...this.formData,
      description: value,
    });
  }

  validate() {
    return this.formRef.validate();
  }

  render() {
    return (
      <div class='basic-info'>
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
            label={this.$t('模板名称')}
            property='name'
            required
          >
            <bk-input
              disabled={this.scene === 'edit'}
              maxlength={50}
              placeholder={this.$t('1～50 字符，仅支持 英文小写、数字、下划线（保存后不可修改）')}
              value={this.formData.name}
              onChange={this.handleNameChange}
            />
          </bk-form-item>
          <bk-form-item
            class='w50'
            error-display-type='normal'
            label={this.$t('模板别名')}
          >
            <bk-input
              value={this.formData.alias}
              onChange={this.handleAliasChange}
            />
          </bk-form-item>
          <bk-form-item
            class='w100'
            error-display-type='normal'
            label={this.$t('生效范围')}
            property='space_scope'
            required
          >
            <bk-tag-input
              clearable={false}
              disabled={this.isGlobalTemplate}
              list={this.bizList}
              save-key='bk_biz_id'
              tag-tpl={this.tagTpl}
              trigger='focus'
              value={this.formData.space_scope}
              collapseTags
              onChange={this.handleEffectChange}
            />
          </bk-form-item>
          <bk-form-item
            class='w100'
            error-display-type='normal'
            label={this.$t('模板说明')}
            property='description'
          >
            <bk-input
              type='textarea'
              value={this.formData.description}
              onChange={this.handleDescChange}
            />
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
