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
import { defineComponent, ref } from "vue";
import useLocale from "@/hooks/use-locale";
import { bkMessage } from "bk-magic-vue";
import useStore from "@/hooks/use-store";
import SubscriptionForm from "./subscription-form";
import $http from "@/api";

import "./index.scss";

type TestSendingTarget = "all" | "self";

export default defineComponent({
  name: "CreateSubscription",
  components: {
    SubscriptionForm,
  },
  props: {
    value: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
    scenario: {
      type: String,
      default: "clustering",
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const createSubscriptionFormRef = ref<any>(null);
    const isSaving = ref(false);
    const isSending = ref(false);
    const isShowSendingSuccessDialog = ref(false);

    const handleSave = () => {
      createSubscriptionFormRef.value
        .getValue()
        .then(async (formData) => {
          isSaving.value = true;
          try {
            await $http.request("newReport/createOrUpdateReport/", {
              data: formData,
            });
            bkMessage({
              theme: "success",
              message: t("保存成功"),
            });
            emit("change", false);
          } finally {
            isSaving.value = false;
          }
        })
        .catch((err) => {
          console.error(err);
        });
    };

    const testSending = (to: TestSendingTarget) => {
      createSubscriptionFormRef.value
        .getValue()
        .then(async (tempFormData) => {
          if (!tempFormData) {
            return;
          }
          const formData = structuredClone(tempFormData);
          if (to === "self") {
            const selfChannels = [
              {
                is_enabled: true,
                subscribers: [
                  {
                    id: store.state.userMeta?.username || "",
                    type: "user",
                    is_enabled: true,
                  },
                ],
                channel_name: "user",
              },
            ];
            formData.channels = selfChannels;
          }
          try {
            isSending.value = true;
            await $http.request("newReport/sendReport/", {
              data: formData,
            });
            isShowSendingSuccessDialog.value = true;
          } finally {
            isSending.value = false;
          }
        })
        .catch((err) => {
          console.error(err);
        });
    };

    return () => (
      <div>
        <bk-sideslider
          width="960"
          ext-cls="quick-create-subscription-slider"
          before-close={() => {
            emit("change", false);
          }}
          is-show={props.value}
          title={t("新增订阅")}
          quick-close
          transfer
        >
          <div slot="content">
            <subscription-form
              ref={createSubscriptionFormRef}
              index-id={props.indexId}
              mode="create"
              scenario={props.scenario}
            />
            <div class="footer-bar">
              <bk-button
                style="width: 88px;"
                loading={isSaving.value}
                theme="primary"
                onClick={handleSave}
              >
                {t("保存")}
              </bk-button>
              <bk-button
                style="width: 88px;"
                loading={isSending.value}
                theme="primary"
                outline
                onClick={() => testSending("self")}
              >
                {t("测试发送")}
              </bk-button>
              <bk-button
                style="width: 88px;"
                onClick={() => emit("change", false)}
              >
                {t("取消")}
              </bk-button>
            </div>
          </div>
        </bk-sideslider>

        <bk-dialog
          ext-cls="test-sending-result-dialog"
          value={isShowSendingSuccessDialog.value}
          show-footer={false}
          theme="primary"
        >
          <div class="test-send-success-dialog-header" slot="header">
            <i
              style="color: rgb(45, 202, 86);"
              class="bk-icon icon-check-circle-shape"
            ></i>
            <span style="margin-left: 10px;">{t("发送测试邮件成功")}</span>
          </div>
          <div class="test-send-success-dialog-content">
            {t("邮件任务已生成, 请一分钟后到邮箱查看")}
          </div>
        </bk-dialog>
      </div>
    );
  },
});
