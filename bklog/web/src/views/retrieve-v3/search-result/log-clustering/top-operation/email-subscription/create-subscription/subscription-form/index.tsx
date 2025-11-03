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
import { mergeWith } from "lodash-es";
import { defineComponent, ref } from "vue";
import SubscriptionContent from "./subscription-content";
import EmailConfig from "./email-config";
import SendConfig from "./send-config";
import useStore from "@/hooks/use-store";
import { useRoute } from "vue-router/composables";
import "./index.scss";

export default defineComponent({
  name: "SubscriptionForm",
  components: {
    SubscriptionContent,
    EmailConfig,
    SendConfig,
  },
  props: {
    mode: {
      type: String,
      default: "edit",
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
  setup(props, { expose }) {
    const store = useStore();
    const route = useRoute();

    const subscriptionContentRef = ref<any>(null);
    const emailConfigRef = ref<any>(null);
    const sendConfigRef = ref<any>(null);

    const getValue = async () => {
      const formDataList = await Promise.all([
        subscriptionContentRef.value.getValue(),
        emailConfigRef.value.getValue(),
        sendConfigRef.value.getValue(),
      ]);
      const formData = formDataList.reduce(
        (data, item) => mergeWith(data, item),
        {},
      );

      const cloneFormData = structuredClone(formData);
      delete cloneFormData.scenario_config__log_display_count;
      delete cloneFormData.content_config__title;
      delete cloneFormData.timerange;
      if (cloneFormData.subscriber_type === "self") {
        cloneFormData.channels = [
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
      }
      cloneFormData.bk_biz_id = Number(route.query.bizId || 0);
      cloneFormData.scenario_config.index_set_id = Number(props.indexId || 0);
      return cloneFormData;
    };

    expose({
      getValue,
    });
    return () => (
      <div class="quick-create-subscription-slider-container">
        <subscription-content
          ref={subscriptionContentRef}
          index-id={props.indexId}
          mode="create"
          scenario={props.scenario}
        />
        <email-config ref={emailConfigRef} scenario={props.scenario} />
        <send-config
          ref={sendConfigRef}
          index-id={props.indexId}
          mode="create"
          scenario={props.scenario}
        />
      </div>
    );
  },
});
