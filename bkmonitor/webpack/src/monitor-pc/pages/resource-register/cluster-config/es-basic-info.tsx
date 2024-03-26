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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import FormItem from './components/form-item';
import { validatePort } from './utils';

const systems = [
  { id: 'tencentcloud', name: '腾讯云' },
  { id: 'bk_log_search', name: 'bk_log_search' },
  { id: '_default', name: '_default' },
  { id: 'log-search-4', name: 'log-search-4' }
];

interface IProps {
  data?: any;
  onChange?: (v: any) => void;
}
@Component
export default class EsBasicInfo extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) data: any;

  localFormData = {
    registered_system: '', // 来源
    address: '', // ES地址
    port: '', // 端口
    schema: '', // 协议
    username: '', // 用户名
    password: '' // 密码
  };
  formErrMsg = {
    registered_system: '',
    address: '',
    port: '',
    username: '',
    password: ''
  };

  created() {
    if (this.data) {
      this.localFormData = this.data;
    }
  }
  /* 当前组件表单整体字段校验 */
  formValidate() {
    if (!this.localFormData.registered_system) {
      this.formErrMsg.registered_system = window.i18n.tc('必选项');
    } else if (!this.localFormData.address) {
      this.formErrMsg.address = window.i18n.tc('必填项');
    } else if (!validatePort.test(this.localFormData.port)) {
      this.formErrMsg.port = window.i18n.tc('请输入合法端口');
    } else if (!this.localFormData.username) {
      this.formErrMsg.username = window.i18n.tc('必填项');
    } else if (!this.localFormData.password) {
      this.formErrMsg.password = window.i18n.tc('必填项');
    }
    return Object.keys(this.formErrMsg).every(key => !this.formErrMsg[key]);
  }
  /* 清除校验错误提示 */
  clearError() {
    Object.keys(this.formErrMsg).forEach(key => {
      this.formErrMsg[key] = '';
    });
  }
  handleSelectToggle() {
    this.clearError();
  }

  @Emit('change')
  handleEmitChange() {
    return this.localFormData;
  }

  render() {
    return (
      <div>
        <div class='horizontal'>
          <FormItem
            title={this.$tc('来源')}
            require
            errMsg={this.formErrMsg.registered_system}
            width={120}
          >
            <bk-select
              v-model={this.localFormData.registered_system}
              onToggle={v => this.handleSelectToggle(v, this.localFormData.registered_system)}
              onChange={this.handleEmitChange}
            >
              {systems.map(option => (
                <bk-option
                  key={option.id}
                  id={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
          </FormItem>
          <FormItem
            title={this.$tc('ES地址')}
            require
            errMsg={this.formErrMsg.address}
            width={424}
          >
            <bk-input
              v-model={this.localFormData.address}
              onFocus={() => this.clearError()}
              onChange={this.handleEmitChange}
            ></bk-input>
          </FormItem>
        </div>
        <div class='horizontal'>
          <FormItem
            title={this.$tc('端口')}
            require
            errMsg={this.formErrMsg.port}
            width={270}
          >
            <bk-input
              v-model={this.localFormData.port}
              onFocus={() => this.clearError()}
              onChange={this.handleEmitChange}
            ></bk-input>
          </FormItem>
          <FormItem
            title={this.$tc('协议')}
            width={270}
          >
            <bk-input
              v-model={this.localFormData.schema}
              onFocus={() => this.clearError()}
              onChange={this.handleEmitChange}
            ></bk-input>
          </FormItem>
        </div>
        <div class='horizontal'>
          <FormItem
            title={this.$tc('用户名')}
            require
            errMsg={this.formErrMsg.username}
            width={270}
          >
            <bk-input
              v-model={this.localFormData.username}
              onFocus={() => this.clearError()}
              onChange={this.handleEmitChange}
            ></bk-input>
          </FormItem>
          <FormItem
            title={this.$tc('密码')}
            require
            errMsg={this.formErrMsg.password}
            width={270}
          >
            <bk-input
              v-model={this.localFormData.password}
              type='password'
              onFocus={() => this.clearError()}
              onChange={this.handleEmitChange}
            ></bk-input>
          </FormItem>
        </div>
      </div>
    );
  }
}
