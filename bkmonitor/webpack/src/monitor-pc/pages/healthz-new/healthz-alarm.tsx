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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getAlarmConfig, updateAlarmConfig } from 'monitor-api/modules/healthz';

import UserSelector from '../../components/user-selector/user-selector';

import './healthz-alarm.scss';

@Component
export default class HealthzAlarm extends tsc<object> {
  formData = {
    alarm_role: [],
    alarm_type: [],
  };
  rules = {};
  loading = false;
  created() {
    this.rules = {
      alarm_role: [
        {
          validator: this.checkAlarmRole,
          message: this.$t('必选项'),
          trigger: 'change',
        },
      ],
      alarm_type: [
        {
          validator: this.checkAlarmType,
          message: this.$t('必选项'),
          trigger: 'change',
        },
      ],
    };
    this.getAlarmConfig();
  }
  async getAlarmConfig() {
    this.loading = true;
    const data = await getAlarmConfig().catch(() => {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('获取通知设置失败'),
      });
      return false;
    });
    this.formData.alarm_role = data?.alarm_role || [];
    this.formData.alarm_type = data?.alarm_type || [];
    this.loading = false;
  }
  async checkAlarmRole() {
    return Array.isArray(this.formData.alarm_role) && this.formData.alarm_role.length > 0;
  }
  async checkAlarmType() {
    return Array.isArray(this.formData.alarm_type) && this.formData.alarm_type.length > 0;
  }
  async validate() {
    this.loading = true;
    const validate = await (this.$refs.validateForm as any)?.validate?.().catch(() => false);
    if (!validate) {
      this.loading = false;
      this.$bkMessage({
        theme: 'error',
        message: this.$t('校验失败，请检查参数'),
      });
      return;
    }
    this.setAlarmConfig();
  }
  async setAlarmConfig() {
    const success = await updateAlarmConfig({
      alarm_config: this.formData,
    })
      .then(() => true)
      .catch(() => false);
    this.$bkMessage({
      theme: success ? 'success' : 'error',
      message: success ? this.$t('保存成功') : this.$t('获取通知设置失败'),
    });
    this.loading = false;
  }
  render() {
    return (
      <div
        class='healthz-alarm'
        v-bkloading={{
          isLoading: this.loading,
        }}
      >
        <div class='healthz-alarm-title'>{this.$t('通知设置')}</div>
        <bk-form
          ref='validateForm'
          labelWidth={200}
          rules={this.rules}
        >
          <bk-form-item
            error-display-type='normal'
            label={this.$t('通知方式')}
            property='alarm_type'
            required
          >
            <bk-checkbox-group
              class='healthz-alarm-type'
              value={this.formData.alarm_type}
              onChange={v => (this.formData.alarm_type = v)}
            >
              {['mail', 'wechat', 'sms', 'rtx', 'phone']
                .filter(v => !!window.platform.te || v !== 'rtx')
                .map(key => (
                  <bk-checkbox
                    key={key}
                    label={key}
                  >
                    <span class={`image-${key}`} />
                  </bk-checkbox>
                ))}
            </bk-checkbox-group>
          </bk-form-item>
          <bk-form-item
            class='member-item healthz-alarm-role'
            error-display-type='normal'
            label={this.$t('通知人员')}
            property='alarm_role'
            required
          >
            <UserSelector
              style='width: 300px'
              userIds={this.formData.alarm_role}
              onChange={v => (this.formData.alarm_role = v)}
            />
            <span
              class='role-tips'
              v-bk-tooltips={{
                content: this.$t('当蓝鲸监控的进程状态异常或告警队列拥塞时会通知相关人员'),
              }}
            >
              <i class='icon-monitor icon-hint' />
            </span>
          </bk-form-item>
          <bk-form-item>
            <bk-button
              style='margin-right: 3px;'
              disabled={!this.formData.alarm_role?.length || !this.formData.alarm_type?.length}
              loading={this.loading}
              theme='primary'
              title='提交'
              onClick={this.validate}
            >
              {this.$t('保存')}
            </bk-button>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
