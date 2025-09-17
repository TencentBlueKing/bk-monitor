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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkDuplicateName, createApplication } from 'monitor-api/modules/apm_meta';

import { ETelemetryDataType } from '../../application/app-configuration/type';

import './add-app-form.scss';

interface IProps {
  onCancel?: () => void;
  onSuccess?: (v: string) => void;
}

@Component
export default class AddAppForm extends tsc<IProps> {
  list = [
    {
      id: ETelemetryDataType.metric,
      title: window.i18n.tc('指标'),
      content: window.i18n.tc('通过持续上报服务的关键性能指标，可以实时了解服务的运行状态，如响应时间、吞吐量等'),
      icon: 'icon-zhibiao',
    },
    {
      id: ETelemetryDataType.log,
      title: window.i18n.tc('日志'),
      content: window.i18n.tc('服务日志提供了详细的错误信息和上下文，有助于快速定位和解决问题'),
      icon: 'icon-rizhi',
    },
    {
      id: ETelemetryDataType.trace,
      title: window.i18n.tc('调用链'),
      content: window.i18n.tc(
        '从用户发起请求到服务响应的全链路追踪，追踪请求在多个服务之间的调用情况，帮助业务识别性能瓶颈和延迟原因'
      ),
      icon: 'icon-Tracing',
    },
    {
      id: ETelemetryDataType.profiling,
      title: window.i18n.tc('性能分析'),
      content: window.i18n.tc('通过分析函数调用栈和内存分配情况，找出性能瓶颈并进行针对性优化'),
      icon: 'icon-profiling',
    },
  ];

  formData = {
    appName: '',
    appAlias: '',
    description: '',
    [ETelemetryDataType.metric]: true,
    [ETelemetryDataType.log]: true,
    [ETelemetryDataType.trace]: true,
    [ETelemetryDataType.profiling]: false,
  };
  formDataErrMsg = {
    appName: '',
    appAlias: '',
  };
  saveLoading = false;
  saveToServiceLoading = false;
  isVerify = false;

  initForm() {
    this.formData = {
      appName: '',
      appAlias: '',
      description: '',
      [ETelemetryDataType.metric]: true,
      [ETelemetryDataType.log]: true,
      [ETelemetryDataType.trace]: true,
      [ETelemetryDataType.profiling]: false,
    };
  }

  emojiRegex(value: string) {
    return /(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(value);
  }

  /** 检查 应用名 是否重名 */
  async handleCheckDuplicateName(val: string) {
    const pass = await checkDuplicateName({ app_name: val })
      .then(data => !data.exists)
      .catch(() => false);
    return pass;
  }

  commonRule(value, key) {
    if (!value) {
      return this.$tc('必填项');
    }
    if (this.emojiRegex(value)) {
      return this.$tc('不能输入emoji表情');
    }
    if (!(value.length >= 1 && value.length <= 50)) {
      return window.i18n.tc('输入1-50个字符');
    }
    if (key === 'appName' && !/^[a-z0-9_-]+$/.test(value)) {
      return window.i18n.t('仅支持小写字母、数字、_- 中任意一条件即可');
    }
  }

  clearErrorMsg() {
    for (const key in this.formDataErrMsg) {
      this.formDataErrMsg[key] = '';
    }
  }
  isVerifyFn() {
    let is = true;
    for (const key in this.formDataErrMsg) {
      if (this.formDataErrMsg[key]) {
        is = false;
        break;
      }
    }
    return is;
  }
  async handleBlur(key) {
    const value = this.formData[key];
    let errMsg = this.commonRule(value, key);
    if (key === 'appName' && !errMsg && value) {
      const pass = await this.handleCheckDuplicateName(value);
      if (!pass) {
        errMsg = this.$t('应用名已存在');
      }
    }
    this.formDataErrMsg[key] = errMsg;
    this.isVerify = this.isVerifyFn();
  }

  async validateForm() {
    await this.handleBlur('appName');
    await this.handleBlur('appAlias');
    this.isVerify = this.isVerifyFn();
  }

  /* 保存 */
  async handleSave() {
    this.saveLoading = true;
    await this.validateForm();
    if (!this.isVerifyFn()) {
      this.saveLoading = false;
      this.saveToServiceLoading = false;
      return;
    }
    const params = {
      app_name: this.formData.appName,
      app_alias: this.formData.appAlias,
      description: this.formData.description,
      enabled_profiling: this.formData[ETelemetryDataType.profiling],
      enabled_trace: this.formData[ETelemetryDataType.trace],
      enabled_metric: this.formData[ETelemetryDataType.metric],
      enabled_log: this.formData[ETelemetryDataType.log],
      es_storage_config: null,
    };
    const res = await createApplication(params)
      .then(data => data)
      .catch(() => false);
    if (res) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('应用创建成功，你可以继续接入服务。'),
      });
      this.$emit('success', params.app_name as string, res.application_id || '');
      this.initForm();
    }
    this.saveLoading = false;
    this.saveToServiceLoading = false;
  }

  handleCancel() {
    this.initForm();
    this.$emit('cancel');
  }

  formItem(label: any | string, content: any, cls = '', err = '') {
    return (
      <div class={['form-item', cls]}>
        <span class={['form-item-label']}>{label}</span>
        <div>
          <span class='form-item-content'>{content}</span>
          {!!err && <div class='err-msg'>{err}</div>}
        </div>
      </div>
    );
  }
  render() {
    return (
      <div class='add-app-form-component'>
        {this.formItem(
          this.$t('应用名'),
          <bk-input
            class='input input-width'
            v-model={this.formData.appName}
            placeholder={this.$t('1-50字符，由小写字母、数字、下划线(_)、中划线(-)组成')}
            onBlur={() => this.handleBlur('appName')}
            onFocus={() => this.clearErrorMsg()}
          />,
          'required mb-24',
          this.formDataErrMsg.appName
        )}
        {this.formItem(
          this.$t('应用别名'),
          <bk-input
            class='input input-width'
            v-model={this.formData.appAlias}
            placeholder={this.$t('1-50字符')}
            onBlur={() => this.handleBlur('appAlias')}
            onFocus={() => this.clearErrorMsg()}
          />,
          'required mb-24',
          this.formDataErrMsg.appAlias
        )}
        {this.formItem(
          this.$t('描述'),
          <bk-input
            class='input input-width'
            v-model={this.formData.description}
            maxlength='100'
            type='textarea'
          />,
          'mb-24'
        )}
        {this.formItem(
          this.$t('上报类型'),
          this.list.map(item => (
            <div
              key={item.id}
              class='report-type-wrap'
            >
              <div class={['report-left-content', { 'is-disabled': !this.formData[item.id] }]}>
                <i class={['icon-monitor', item.icon]} />
              </div>
              <div class='report-middle-content'>
                <span class='middle-content-title'>{item.title}</span>
                <span class='middle-content-text'>{item.content}</span>
              </div>
              <div class='report-right-content'>
                <bk-switcher
                  v-model={this.formData[item.id]}
                  size='small'
                  theme='primary'
                />
              </div>
            </div>
          )),
          'mb-24'
        )}
        {this.formItem(
          '',
          <div>
            <bk-button
              class='mr-8'
              disabled={!this.isVerify}
              loading={this.saveLoading}
              theme='primary'
              onClick={() => this.handleSave()}
            >
              {this.$t('保存')}
            </bk-button>
            {/* <bk-button
              class='mr-8'
              disabled={!this.isVerify}
              loading={this.saveToServiceLoading}
              theme='primary'
              onClick={() => this.handleSave(true)}
            >
              {this.$t('保存并接入服务')}
            </bk-button> */}
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        )}
      </div>
    );
  }
}
