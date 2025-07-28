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
import { defineComponent, ref } from 'vue';

import { Button, Dropdown, Message } from 'bkui-vue';
import { createOrUpdateReport, sendReport } from 'monitor-api/modules/new_report';
import { deepClone } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import CreateSubscriptionForm from './components/create-subscription-form';
import TestSendSuccessDialog from './components/test-send-success-dialog';

import type { TestSendingTarget } from './types';

import './create-subscription.scss';

export default defineComponent({
  name: 'CreateSubscription',
  setup(prop, { emit }) {
    const { t } = useI18n();
    const router = useRouter();
    // 测试发送 按钮 loading
    const isSending = ref(false);
    const isShowDropdownMenu = ref(false);
    // 表格组件 实例
    const refOfCreateSubscriptionForm = ref(null);
    // 保存 按钮 loading
    const isSaving = ref(false);
    // 是否显示 测试发送 结果 dialog
    const isShowTestSendResult = ref(false);

    async function testSending(to: TestSendingTarget) {
      const tempFormData = await refOfCreateSubscriptionForm.value.validateAllForms();
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
                is_enabled: true,
              },
            ],
            channel_name: 'user',
          },
        ];
        formData.channels = selfChannels;
      }
      isSending.value = true;
      await sendReport(formData)
        .then(() => {
          isShowTestSendResult.value = true;
        })
        .finally(() => {
          isSending.value = false;
          isShowDropdownMenu.value = false;
        });
    }

    function handleSave() {
      refOfCreateSubscriptionForm.value.validateAllForms().then(response => {
        isSaving.value = true;
        createOrUpdateReport(response)
          .then(() => {
            Message({
              theme: 'success',
              message: t('保存成功'),
            });
            emit('saveSuccess');
          })
          .finally(() => {
            isSaving.value = false;
          });
      });
    }

    /**
     * 跳转到 订阅管理 页，并用 reportId 请求详情，最后打开编辑抽屉
     * 凑出一个 URL 即可
     * 所需 URL 查询参数 isShowEditSlider, reportId,
     */
    function handleGoToReportListPage(reportId) {
      router.push({
        name: 'report',
        query: {
          reportId,
          isShowEditSlider: 'true',
        },
      });
    }

    return {
      t,
      router,
      isSaving,
      isSending,
      testSending,
      handleSave,
      refOfCreateSubscriptionForm,
      isShowTestSendResult,
      isShowDropdownMenu,
      handleGoToReportListPage,
      emit,
    };
  },
  render() {
    return (
      <div style='position: relative;'>
        <div class='create-subscription-container'>
          <CreateSubscriptionForm
            ref='refOfCreateSubscriptionForm'
            mode='create'
            onSelectExistedReport={this.handleGoToReportListPage}
          />
        </div>
        <div class='footer-bar'>
          <Button
            style='width: 88px;margin-right: 8px;'
            loading={this.isSaving}
            theme='primary'
            onClick={this.handleSave}
          >
            {this.t('保存')}
          </Button>
          <Dropdown
            v-slots={{
              content: () => {
                return (
                  <Dropdown.DropdownMenu>
                    <Dropdown.DropdownItem onClick={() => this.testSending('self')}>
                      {this.t('给自己')}
                    </Dropdown.DropdownItem>
                    <Dropdown.DropdownItem onClick={() => this.testSending('all')}>
                      {this.t('给全员')}
                    </Dropdown.DropdownItem>
                  </Dropdown.DropdownMenu>
                );
              },
            }}
            isShow={this.isShowDropdownMenu}
            placement='top-start'
            trigger='manual'
          >
            <Button
              style='width: 88px;margin-right: 8px;'
              loading={this.isSending}
              theme='primary'
              outline
              onClick={() => {
                this.isShowDropdownMenu = !this.isShowDropdownMenu;
              }}
            >
              {this.t('测试发送')}
            </Button>
          </Dropdown>
          <Button
            style='width: 88px;'
            onClick={() => {
              this.emit('closeCreateSubscriptionSlider');
            }}
          >
            {this.t('取消')}
          </Button>
        </div>

        <TestSendSuccessDialog v-model={this.isShowTestSendResult} />
      </div>
    );
  },
});
