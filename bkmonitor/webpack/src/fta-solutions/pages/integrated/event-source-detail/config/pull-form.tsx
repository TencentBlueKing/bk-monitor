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

import { updateEventPluginInstance } from '../../../../../monitor-api/modules/event_plugin';
import DynamicForm from '../../../setting/set-meal/set-meal-add/components/dynamic-form/dynamic-form';

import './pull-form.scss';

interface IProps {
  formData?: any[];
  instanceId?: string | number;
}

@Component
export default class PullForm extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) formData: any[];
  @Prop({ type: [String, Number], default: () => ({}) }) instanceId: string | number;
  @Ref('dynamicForm') dynamicFormRef: DynamicForm;

  loading = false;

  formModel = {};
  formRules = {};
  formList = [];

  created() {
    const formModel = {};
    const formRules = {};
    const formList = [];
    this.formData.forEach(item => {
      const { key } = item;
      if (key === 'ENABLED_NOTICE_WAYS') {
        console.error(item);
      } else if (key === 'MESSAGE_QUEUE_DSN') {
        console.error(item);
      } else {
        formModel[item.key] = item.value || '';
        if (item.rules?.length) {
          formRules[item.key] = item.rules;
        } else if (item.formItemProps.required) {
          formRules[item.key] = [{ message: this.$tc('必填项'), required: true, trigger: 'blur' }];
        }
        formList.push(item);
      }
    });
    this.formModel = formModel;
    this.formRules = formRules;
    this.formList = formList;
  }

  async handleSave() {
    const valid = await this.dynamicFormRef.validator();
    if (valid) {
      this.loading = true;
      const data = await updateEventPluginInstance(this.instanceId, { config_params: this.formModel }).catch(
        () => null
      );
      if (data) {
        this.$bkMessage({
          extCls: 'event-source-detail-config-pull-form-message',
          theme: 'success',
          message: this.$t('保存成功')
        });
      }
      this.loading = false;
    }
  }

  render() {
    return (
      <div class='event-source-detail-config-pull-form'>
        <DynamicForm
          ref='dynamicForm'
          formList={this.formList}
          formModel={this.formModel}
          formRules={this.formRules}
        ></DynamicForm>
        <bk-button
          theme='primary'
          class='submit'
          loading={this.loading}
          onClick={this.handleSave}
        >
          {this.$t('保存配置')}
        </bk-button>
      </div>
    );
  }
}
