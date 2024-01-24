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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import VerifyItem from '../../../../../components/verify-item/verify-item';
import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import CommonItem from '../components/common-item';
import Container from '../components/container';
import DynamicForm from '../components/dynamic-form/dynamic-form';

import { IPeripheral } from './meal-content-data';

import './peripheral-system.scss';

type PageType = 'add' | 'edit';
interface IProps {
  id?: number;
  peripheralData?: IPeripheral;
  isEdit?: boolean;
  type?: PageType;
  isInit?: boolean;
}
interface IEvents {
  onDebug?: void;
  onChange?: IPeripheral;
  onInit?: boolean;
}

@Component({
  name: 'PeripheralSystem'
})
export default class PeripheralSystem extends tsc<IProps, IEvents> {
  @Prop({ default: 0, type: Number }) id: number;
  @Prop({ default: () => ({}), type: Object }) peripheralData: IPeripheral;
  @Prop({ default: false, type: Boolean }) isEdit: Boolean;
  @Prop({ type: String, default: 'add' }) type: PageType;
  @Prop({ type: Boolean, default: true }) isInit: boolean;

  data: IPeripheral = {};
  isLoading = false;
  formLoading = false;

  // 周边系统的作业数据
  label = '';
  templates: any = [];
  newInfo: { tips?: string; url?: string } = {};

  formTitle = '';

  // 动态表单所需数据
  formModel = {};
  formRules = {};
  formList = [];

  errorMsg = {
    getFormTemplateId: ''
  };

  formTemplateId: string | number = '';

  get curLink() {
    const curLinkObj = this.templates.find(item => +item.id === +this.formTemplateId);
    return curLinkObj?.url;
  }

  @Ref('dynamicForm') readonly dynamicFormEl: DynamicForm;

  // @Watch('peripheralData', { immediate: true, deep: true })
  // handlePeripheralData(data: IPeripheral) {
  //   if (!this.templates.length && data && !data?.data?.formTemplateId) {
  //     console.log('ddd', this.templates, data, data?.data?.formTemplateId);
  //     this.id && this.getPluginTemplates(this.id);
  //   }
  //   return this.data = deepClone(data);
  // }

  created() {
    if (this.isEdit) {
      this.id && this.getPluginTemplates(this.id);
      this.id && this.formTemplateId && this.getTemplateDetail(this.id, +this.formTemplateId);
    }
  }

  // 周边系统校验
  async validator() {
    return new Promise((resolve, reject) => {
      if (!this.formTemplateId) {
        this.errorMsg.getFormTemplateId = this.$tc('必选项');
        reject(false);
      }
      if (this.dynamicFormEl) {
        resolve(this.dynamicFormEl.validator());
      }
      resolve(true);
    });
  }

  // 获取作业平台数据
  async getPluginTemplates(id: number) {
    this.isLoading = true;
    const data: any = await SetMealAddModule.getPluginTemplates(id).finally(() => (this.isLoading = false));
    this.label = data.name;
    this.templates = data.templates;
    this.newInfo = data.new_info;
  }

  // 获取动态form表单数据
  async getTemplateDetail(pluginId: number, templateId: number) {
    this.formLoading = true;
    const data: any = await SetMealAddModule.getTemplateDetail({ pluginId, templateId }).finally(
      () => (this.formLoading = false)
    );
    this.formTitle = data.name;
    this.handleDynamicFormData(data.params);
  }

  // 模版id变更
  handleFormDataChange(templateId: number | string) {
    if (!templateId) return;
    this.errorMsg.getFormTemplateId = '';
    this.formTitle = '';
    // 模版id
    this.formTemplateId = templateId;
    this.data = {
      ...this.peripheralData,
      data: {}
    };
    this.data.data = {};
    this.getTemplateDetail(this.id, templateId as any);
  }
  // 刷新操作
  handleRefreshTemplate() {
    this.getPluginTemplates(this.id);
  }
  // 跳转外链
  handleLinkTo() {
    if (this.curLink) window.open(this.curLink);
  }

  // 处理动态表单所需数据
  handleDynamicFormData(data) {
    try {
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
          if (this.type === 'edit' && this.isInit) {
            formModel[item.key] = '';
          } else {
            formModel[item.key] = item.value;
          }
          if (item.rules?.length) {
            formRules[item.key] = item.rules;
          } else if (item.formItemProps.required) {
            formRules[item.key] = [{ message: this.$tc('必填项'), required: true, trigger: 'blur' }];
          }
          formList.push(item);
        }
      });
      if (this.isInit) {
        this.handleInitChange();
      }
      this.formModel = formModel;
      this.formRules = formRules;
      this.formList = formList.map(item => {
        if (item.type === 'tag-input') {
          item.formChildProps['allow-auto-match'] = true;
        } else if (item.type === 'switcher') {
          item.formChildProps.size = 'small';
        }
        return item;
      });
      const templateDetailKeys = Object.keys(this.peripheralData.data.templateDetail || {});
      if (templateDetailKeys?.length) {
        templateDetailKeys.forEach(key => {
          const value = this.peripheralData.data.templateDetail?.[key];
          if (!!value && this.formModel[key] !== undefined) {
            this.formModel[key] = value;
          }
        });
      }
      if (!data.length) {
        this.data.data.templateDetail = {};
        this.handleDataChange();
      } else {
        this.handleFormDataChage(this.formModel);
      }
    } catch (error) {
      console.error(error);
    }
  }

  handleFormDataChage(data) {
    this.data.data.templateDetail = data;
    this.handleDataChange();
  }

  @Emit('change')
  handleDataChange() {
    this.data.data.formTemplateId = this.formTemplateId;
    return this.data;
  }

  @Emit('debug')
  handleDebug() {}

  @Emit('init')
  handleInitChange() {
    return false;
  }

  protected render() {
    return (
      <div
        class='peripheral-system-wrap'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <div class='form-item'>
          <CommonItem
            title={this.label}
            required
          >
            <div class='template-selsect-wrap'>
              <VerifyItem
                class='verify-item'
                errorMsg={this.errorMsg.getFormTemplateId}
              >
                <bk-select
                  class='select input-width'
                  clearable={false}
                  behavior='simplicity'
                  searchable={true}
                  placeholder={this.$tc('选择')}
                  value={this.formTemplateId}
                  onSelected={this.handleFormDataChange}
                >
                  {this.templates.map(option => (
                    <bk-option
                      key={option.id}
                      id={option.id}
                      name={option.name}
                    ></bk-option>
                  ))}
                  <div
                    slot='extension'
                    onClick={() => this.newInfo.url && window.open(this.newInfo.url)}
                    style='cursor: pointer;'
                  >
                    <i
                      class='bk-icon icon-plus-circle'
                      style={{ marginRight: '5px' }}
                    ></i>
                    {this.newInfo.tips}
                  </div>
                </bk-select>
              </VerifyItem>
              <span class='icon-btn'>
                {this.curLink ? (
                  <i
                    class='icon-monitor icon-mc-link'
                    onClick={this.handleLinkTo}
                  ></i>
                ) : undefined}
                <i
                  class='icon-monitor icon-shuaxin'
                  onClick={this.handleRefreshTemplate}
                ></i>
              </span>
            </div>
          </CommonItem>
          <div
            class='form-item-content'
            v-bkloading={{ isLoading: this.formLoading }}
          >
            {this.formTemplateId && this.formTitle ? (
              <Container
                style='margin-top: 24px;'
                title={this.formTitle}
              >
                {this.formList?.length && Object.keys(this.formModel).length ? (
                  <DynamicForm
                    ref='dynamicForm'
                    formList={this.formList}
                    formModel={this.formModel}
                    formRules={this.formRules}
                    on-change={this.handleFormDataChage}
                  ></DynamicForm>
                ) : (
                  [this.$t('当前{n}无需填写参数', { n: this.label }), <br />]
                )}
                {this.formList.length ? (
                  <bk-button
                    theme='primary'
                    outline
                    style={{ marginTop: '16px' }}
                    onClick={this.handleDebug}
                  >
                    {this.$t('调试')}
                  </bk-button>
                ) : undefined}
              </Container>
            ) : undefined}
            {this.formTemplateId && (
              <div class='sensitivity-failure-judgment'>
                <CommonItem
                  title={this.$tc('失败判断')}
                  class='failure'
                >
                  <i18n
                    path='当执行{0}分钟未结束按失败处理。'
                    class='failure-text'
                  >
                    <bk-input
                      class='input-inline'
                      v-model={this.data.timeout}
                      behavior={'simplicity'}
                      type={'number'}
                      showControls={false}
                      on-change={() => this.handleDataChange()}
                    ></bk-input>
                  </i18n>
                </CommonItem>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
