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
import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

//
import { createEventPluginInstance, getEventPluginInstance } from '../../../monitor-api/modules/event_plugin';
import DynamicForm from '../setting/set-meal/set-meal-add/components/dynamic-form/dynamic-form';

import './install-plugin-dialog.scss';

type InstallType = 'current' | 'multi';

export interface IData {
  version: string;
  pluginId: string;
  paramsSchema: any;
  pluginDisplayName: string;
}

interface IInstallPluginDialogProps {
  // value: boolean
  data: IData;
}

interface IInstallPluginDialogEvents {
  onChange: (value: boolean) => void;
  onSuccess: () => void;
}

@Component({ name: 'InstallPluginDialog' })
export default class InstallPluginDialog extends tsc<IInstallPluginDialogProps, IInstallPluginDialogEvents> {
  @Prop({ type: Object, default: () => ({}) }) readonly data: IData;

  @Model('change', { type: Boolean, default: false }) readonly value: boolean;
  @Ref('dynamicForm') dynamicFormRef: DynamicForm;

  biz: number | number[] = [];
  type: InstallType = 'current';
  count = 12;

  // 动态表单所需数据
  formModel = {};
  formRules = {};
  formList = [];

  loading = false;
  formLoading = false;

  @Watch('value')
  async handleShow(val) {
    if (val) {
      if (this.data.paramsSchema) {
        this.handleDynamicFormData(this.data.paramsSchema);
      } else {
        this.formLoading = true;
        const detail = await getEventPluginInstance(this.data.pluginId, { version: this.data.version }).catch(
          () => null
        );
        if (detail) {
          this.handleDynamicFormData(detail.params_schema);
        }
        this.formLoading = false;
      }
    }
  }

  handleDynamicFormData(data) {
    const formModel = {};
    const formRules = {};
    const formList = [];
    data.forEach(item => {
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

  @Emit('change')
  handleValueChange(value: boolean) {
    return value;
  }

  async handleConfirm() {
    const valid = this.formList.length ? await this.dynamicFormRef.validator() : true;
    if (!valid) return;
    this.loading = true;
    const data = await createEventPluginInstance(this.data.pluginId, {
      version: this.data.version,
      config_params: this.formModel
    }).catch(() => null);
    if (data) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('安装成功')
      });
      this.$emit('change', false);
      this.$emit('success');
    }
    this.loading = false;
  }

  handleClose() {
    this.$emit('change', false);
  }

  render() {
    return (
      <bk-dialog
        value={this.value}
        header-position='left'
        title={this.$t('安装插件')}
        ok-text={this.$t('安装')}
        auto-close={false}
        ext-cls='integrated-install-plugin-dialog'
        on-value-change={this.handleValueChange}
      >
        <div
          class='dialog-form-content'
          v-bkloading={{ isLoading: this.formLoading }}
        >
          {this.formList.length ? (
            <DynamicForm
              ref='dynamicForm'
              formList={this.formList}
              formModel={this.formModel}
              formRules={this.formRules}
            ></DynamicForm>
          ) : (
            <span>{this.$t('确定要安装事件源{0}吗', [`【${this.data?.pluginDisplayName || ''}】`])}?</span>
          )}
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            class='mr10'
            loading={this.loading}
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button onClick={this.handleClose}>{this.$t('取消')}</bk-button>
        </div>
        {/* <div class="dialog-content">
          <div>{this.$t('安装至')}</div>
          <bk-radio-group v-model={this.type} class="mt15">
            <bk-radio value="current">{this.$t('当前空间')}</bk-radio>
            <bk-radio value="multi" class="all-biz">
              <div class="biz-select">
                {this.$t('多个业务')}
                <bk-select size="small" behavior="simplicity" clearable v-model={this.biz}></bk-select>
              </div>
            </bk-radio>
          </bk-radio-group>
          <i18n path="已安装本插件业务" class="installed-tips">
            <span class="count">{this.count}</span>
            <bk-button text size="small">
              {this.$t('点击查看')}
            </bk-button>
          </i18n>
        </div> */}
      </bk-dialog>
    );
  }
}
