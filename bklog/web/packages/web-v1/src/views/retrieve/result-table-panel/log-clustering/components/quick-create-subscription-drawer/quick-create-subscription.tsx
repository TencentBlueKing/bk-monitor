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
import { Component, Model, Prop } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';

import CreateSubscriptionForm from './create-subscription-form';

import type { TestSendingTarget } from './types';

import './quick-create-subscription.scss';

interface IProps {
  value: boolean;
}

@Component({
  components: {
    CreateSubscriptionForm,
  },
})
class QuickCreateSubscription extends tsc<IProps> {
  @Model('change', { type: Boolean }) value: IProps['value'];
  @Prop({ type: String, default: 'clustering' }) scenario: string;
  @Prop({ type: [Number, String], default: 0 }) indexSetId: number | string;

  isSaving = false;
  isSending = false;
  isShowSendingSuccessDialog = false;
  handleSave() {
    (this.$refs.refOfCreateSubscriptionForm as any)?.validateAllForms?.().then(response => {
      this.isSaving = true;
      (this as any).$http
        .request('newReport/createOrUpdateReport/', {
          data: response,
        })
        .then(() => {
          this.$bkMessage({
            theme: 'success',
            message: this.$t('保存成功'),
          });
          this.$emit('change', false);
        })
        .finally(() => {
          this.isSaving = false;
        });
    });
  }

  async testSending(to: TestSendingTarget) {
    const tempFormData = await (this.$refs.refOfCreateSubscriptionForm as any)?.validateAllForms?.();
    if (!tempFormData) {
      return;
    }
    const formData = structuredClone(tempFormData);
    if (to === 'self') {
      const selfChannels = [
        {
          is_enabled: true,
          subscribers: [
            {
              id: this.$store.state.userMeta?.username || '',
              type: 'user',
              is_enabled: true,
            },
          ],
          channel_name: 'user',
        },
      ];
      formData.channels = selfChannels;
    }
    this.isSending = true;
    await (this as any).$http
      .request('newReport/sendReport/', {
        data: formData,
      })
      .then(() => {
        this.isShowSendingSuccessDialog = true;
      })
      .finally(() => {
        this.isSending = false;
      });
  }

  render() {
    return (
      <div>
        <bk-sideslider
          width='960'
          ext-cls='quick-create-subscription-slider'
          before-close={() => {
            this.$emit('change', false);
          }}
          is-show={this.value}
          title={this.$t('新增订阅')}
          quick-close
          transfer
        >
          <div slot='content'>
            <div class='quick-create-subscription-slider-container'>
              {/* @ts-ignore */}
              <create-subscription-form
                ref='refOfCreateSubscriptionForm'
                index-set-id={this.indexSetId}
                mode='create'
                // 这里填 订阅场景、索引集 等已知参数
                scenario={this.scenario}
              />
            </div>
            <div class='footer-bar'>
              <bk-button
                style='width: 88px; margin-right: 8px;'
                loading={this.isSaving}
                theme='primary'
                onClick={this.handleSave}
              >
                {this.$t('保存')}
              </bk-button>
              <bk-button
                style='width: 88px; margin-right: 8px;'
                loading={this.isSending}
                theme='primary'
                outline
                onClick={() => this.testSending('self')}
              >
                {this.$t('测试发送')}
              </bk-button>
              {/* 20240305 若默认测试发送只给自己，那么没必要再出一次气泡窗选择了 */}
              {false}
              <bk-button
                style='width: 88px;'
                onClick={() => this.$emit('change', false)}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-sideslider>

        <bk-dialog
          ext-cls='test-sending-result-dialog'
          v-model={this.isShowSendingSuccessDialog}
          show-footer={false}
          theme='primary'
        >
          <div
            class='test-send-success-dialog-header'
            slot='header'
          >
            <i
              style='color: rgb(45, 202, 86);'
              class='bk-icon icon-check-circle-shape'
            />
            <span style='margin-left: 10px;'>{this.$t('发送测试邮件成功')}</span>
          </div>
          <div class='test-send-success-dialog-content'>{this.$t('邮件任务已生成, 请一分钟后到邮箱查看')}</div>
        </bk-dialog>
      </div>
    );
  }
}
export default ofType().convert(QuickCreateSubscription);
