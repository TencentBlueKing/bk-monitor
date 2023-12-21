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
import { defineComponent, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { createOrUpdateReport, sendReport } from '@api/modules/new_report';
import { deepClone } from '@common/utils';
import { Button, Dialog, Dropdown, Message } from 'bkui-vue';

import CreateSubscriptionForm from './components/create-subscription-form';

import './create-subscription.scss';

export default defineComponent({
  name: 'CreateSubscription',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const isSending = ref(false);
    async function testSending(to) {
      const tempFormData = await refOfCreateSubscriptionForm.value.validateAllForms().catch(console.log);
      console.log('testSending', tempFormData);
      if (!tempFormData) return;
      const formData = deepClone(tempFormData);
      if (to === 'self') {
        const selfChannels = [
          {
            is_enabled: true,
            subscribers: [
              {
                id: window.user_name || window.username,
                type: 'user',
                is_enabled: true
              }
            ],
            channel_name: 'user'
          }
        ];
        formData.channels = selfChannels;
      }
      if (to === 'all') {
        console.log(refOfCreateSubscriptionForm.value);
      }
      isSending.value = true;
      await sendReport(formData)
        .then(() => {
          isShowTestSendResult.value = true;
        })
        .catch(console.log)
        .finally(() => {
          isSending.value = false;
        });
    }
    const refOfCreateSubscriptionForm = ref(null);
    const isSaving = ref(false);
    function handleSave() {
      refOfCreateSubscriptionForm.value
        .validateAllForms()
        .then(response => {
          // TODO: 提交数据即可
          console.log(response);
          isSaving.value = true;
          createOrUpdateReport(response)
            .then(() => {
              Message({
                theme: 'success',
                message: window.i18n.t('保存成功')
              });
              router.go(-1);
            })
            .catch(console.log)
            .finally(() => {
              isSaving.value = false;
            });
        })
        .catch(console.log());
    }

    const isShowTestSendResult = ref(false);

    return {
      t,
      router,
      isSaving,
      isSending,
      testSending,
      handleSave,
      refOfCreateSubscriptionForm,
      isShowTestSendResult
    };
  },
  render() {
    return (
      <div style='position: relative;'>
        <div class='create-subscription-container'>
          <CreateSubscriptionForm
            ref='refOfCreateSubscriptionForm'
            mode='normal'
          ></CreateSubscriptionForm>
        </div>
        <div class='footer-bar'>
          <Button
            theme='primary'
            loading={this.isSaving}
            style={{ width: '88px', marginRight: '8px' }}
            onClick={this.handleSave}
          >
            {window.i18n.t('保存')}
          </Button>
          <Dropdown
            trigger='click'
            placement='top-start'
            v-slots={{
              content: () => {
                return (
                  <Dropdown.DropdownMenu>
                    <Dropdown.DropdownItem onClick={() => this.testSending('self')}>
                      {window.i18n.t('给自己')}
                    </Dropdown.DropdownItem>
                    <Dropdown.DropdownItem onClick={() => this.testSending('all')}>
                      {window.i18n.t('给全员')}
                    </Dropdown.DropdownItem>
                  </Dropdown.DropdownMenu>
                );
              }
            }}
          >
            <Button
              theme='primary'
              outline
              loading={this.isSending}
              style={{ width: '88px', marginRight: '8px' }}
            >
              {window.i18n.t('测试发送')}
            </Button>
          </Dropdown>
          <Button
            style={{ width: '88px' }}
            onClick={() => {
              this.router.go(-1);
            }}
          >
            {window.i18n.t('取消')}
          </Button>
        </div>

        <Dialog
          isShow={this.isShowTestSendResult}
          dialog-type='show'
          ext-cls='test-send-result-dialog'
          onClosed={() => {
            this.isShowTestSendResult = false;
          }}
          v-slots={{
            default: () => {
              return (
                <div
                  style={{
                    marginLeft: '30px'
                  }}
                >
                  {window.i18n.t('邮件任务已生成, 请一分钟后到邮箱查看')}
                </div>
              );
            },
            header: () => {
              return (
                <div>
                  <i
                    class='icon-monitor icon-mc-check-fill'
                    style='color: #2dca56;'
                  />
                  <span
                    style={{
                      marginLeft: '10px',
                      fontWeight: 'bold'
                    }}
                  >
                    {window.i18n.t('发送测试邮件成功')}
                  </span>
                </div>
              );
            }
          }}
        ></Dialog>
      </div>
    );
  }
});
