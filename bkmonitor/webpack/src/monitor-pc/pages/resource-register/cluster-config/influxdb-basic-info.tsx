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

interface IProps {
  data?: any;
  onChange?: (v: any) => void;
}

@Component
export default class InfluxdbBasicInfo extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) data: any;
  localFormData = {
    domain: '', // Proxy集群域名
    port: '', // 端口
    username: '', // 用户名
    password: '', // 密码
  };
  formErrMsg = {
    domain: '',
    port: '',
  };

  created() {
    if (this.data) {
      this.localFormData = this.data;
    }
  }

  /* 当前组件表单整体字段校验 */
  formValidate() {
    if (!this.localFormData.domain) {
      this.formErrMsg.domain = window.i18n.tc('必填项');
    } else if (!validatePort.test(this.localFormData.port)) {
      this.formErrMsg.port = window.i18n.tc('请输入合法端口');
    }
    return Object.keys(this.formErrMsg).every(key => !this.formErrMsg[key]);
  }
  /* 清除校验错误提示 */
  clearError() {
    Object.keys(this.formErrMsg).forEach(key => {
      this.formErrMsg[key] = '';
    });
  }

  @Emit('change')
  handleEmitChange() {
    return this.localFormData;
  }

  render() {
    return (
      <div>
        <FormItem
          errMsg={this.formErrMsg.domain}
          title={this.$tc('proxy集群域名')}
          require
        >
          <bk-input
            v-model={this.localFormData.domain}
            onChange={this.handleEmitChange}
            onFocus={() => this.clearError()}
          />
        </FormItem>
        <FormItem
          errMsg={this.formErrMsg.port}
          title={this.$tc('端口')}
          require
        >
          <bk-input
            v-model={this.localFormData.port}
            onChange={this.handleEmitChange}
            onFocus={() => this.clearError()}
          />
        </FormItem>
        <div class='horizontal'>
          <FormItem
            width={270}
            title={this.$tc('用户名')}
          >
            <bk-input
              v-model={this.localFormData.username}
              onChange={this.handleEmitChange}
            />
          </FormItem>
          <FormItem
            width={270}
            title={this.$tc('密码')}
          >
            <bk-input
              v-model={this.localFormData.password}
              type='password'
              onChange={this.handleEmitChange}
            />
          </FormItem>
        </div>
      </div>
    );
  }
}
