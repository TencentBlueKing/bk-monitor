/* eslint-disable @typescript-eslint/no-misused-promises */
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

import { deepClone } from '../../../../../../components/monitor-echarts/utils';

import CreateSubscriptionForm from './create-subscription-form';
import './quick-create-subscription.scss';
import { TestSendingTarget } from './types';

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
  @Prop({ default: 'clustering', type: String }) scenario: string;
  @Prop({ default: 0, type: [Number, String] }) indexSetId: number | string;

  isSaving = false;
  isSending = false;
  isShowSendingSuccessDialog = false;
  handleSave() {
    (this.$refs.refOfCreateSubscriptionForm as any)
      ?.validateAllForms?.()
      .then((response) => {
        this.isSaving = true;
        (this as any).$http
          .request('newReport/createOrUpdateReport/', {
            data: response,
          })
          .then(() => {
            this.$bkMessage({
              message: this.$t('保存成功'),
              theme: 'success',
            });
            this.$emit('change', false);
          })
          .finally(() => {
            this.isSaving = false;
          });
      });
  }

  async testSending(to: TestSendingTarget) {
    const tempFormData = await (
      this.$refs.refOfCreateSubscriptionForm as any
    )?.validateAllForms?.();
    if (!tempFormData) return;
    const formData = deepClone(tempFormData);
    if (to === 'self') {
      const selfChannels = [
        {
          channel_name: 'user',
          is_enabled: true,
          subscribers: [
            {
              id: this.$store.state.userMeta?.username || '',
              is_enabled: true,
              type: 'user',
            },
          ],
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
          before-close={() => {
            this.$emit('change', false);
          }}
          ext-cls="quick-create-subscription-slider"
          is-show={this.value}
          quick-close
          title={this.$t('新增订阅')}
          transfer
          width="960"
        >
          <div slot="content">
            <div class="quick-create-subscription-slider-container">
              {/* @ts-ignore */}
              <create-subscription-form
                index-set-id={this.indexSetId}
                mode="create"
                ref="refOfCreateSubscriptionForm"
                // 这里填 订阅场景、索引集 等已知参数
                scenario={this.scenario}
              ></create-subscription-form>
            </div>
            <div class="footer-bar">
              <bk-button
                loading={this.isSaving}
                onClick={this.handleSave}
                style="width: 88px; margin-right: 8px;"
                theme="primary"
              >
                {this.$t('保存')}
              </bk-button>
              <bk-button
                loading={this.isSending}
                onClick={() => this.testSending('self')}
                outline
                style="width: 88px; margin-right: 8px;"
                theme="primary"
              >
                {this.$t('测试发送')}
              </bk-button>
              {/* 20240305 若默认测试发送只给自己，那么没必要再出一次气泡窗选择了 */}
              {false && (
                <bk-dropdown-menu placement="top-start" trigger="click">
                  <bk-button
                    loading={this.isSending}
                    outline
                    slot="dropdown-trigger"
                    style="width: 88px; margin-right: 8px;"
                    theme="primary"
                  >
                    {this.$t('测试发送')}
                  </bk-button>

                  <ul class="bk-dropdown-list" slot="dropdown-content">
                    <li>
                      <a
                        href="javascript:;"
                        onClick={() => this.testSending('self')}
                      >
                        {this.$t('给自己')}
                      </a>
                    </li>
                    {/* 2024.1.12 由于该按钮需要权限判断，但不好实现，这里直接去掉该功能。这里先保留 */}
                    {/* <li>
                    <a
                      href='javascript:;'
                      onClick={() => this.testSending('all')}
                    >
                      {this.$t('给全员')}
                    </a>
                  </li> */}
                  </ul>
                </bk-dropdown-menu>
              )}
              <bk-button
                onClick={() => this.$emit('change', false)}
                style="width: 88px;"
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-sideslider>

        <bk-dialog
          ext-cls="test-sending-result-dialog"
          show-footer={false}
          theme="primary"
          v-model={this.isShowSendingSuccessDialog}
        >
          <div class="test-send-success-dialog-header" slot="header">
            <i
              class="bk-icon icon-check-circle-shape"
              style="color: rgb(45, 202, 86);"
            ></i>
            <span style="margin-left: 10px;">
              {this.$t('发送测试邮件成功')}
            </span>
          </div>
          <div class="test-send-success-dialog-content">
            {this.$t('邮件任务已生成, 请一分钟后到邮箱查看')}
          </div>
        </bk-dialog>
      </div>
    );
  }
}
export default ofType().convert(QuickCreateSubscription);
