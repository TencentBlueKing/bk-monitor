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

import "./index.scss";

export default defineComponent({
  name: "OccupyInput",
  setup(_, { expose, emit }) {
    const { t } = useLocale();

    const occupyRef = ref(null);
    const occupyFormRef = ref<any>(null);
    const occupyData = ref({
      textInputStr: "",
    });

    const occupyRules = {
      textInputStr: [
        {
          validator: (value: string) => !!value,
          message: t("必填项"),
          trigger: "blur",
        },
        {
          validator: (value: string) => /^[A-Z_-]+$/.test(value),
          message: t("{n}不规范, 包含特殊符号.", { n: t("占位符") }),
          trigger: "blur",
        },
      ],
    };

    const handleSubmitOccupy = () => {
      occupyFormRef.value
        .validate()
        .then(() => {
          emit("submit", occupyData.value.textInputStr);
        })
        .catch((e) => console.error("Validation failed:", e));
    };

    const handleCancelOccupy = () => {
      occupyData.value.textInputStr = "";
      emit("cancel");
    };

    expose({
      getRef: () => occupyRef.value,
      close: () => {
        occupyData.value.textInputStr = "";
        occupyFormRef.value.clearError();
      },
    });

    return () => (
      <div style="display: none">
        <div ref={occupyRef} class="occupy-popover">
          <bk-form
            ref={occupyFormRef}
            form-type="vertical"
            {...{
              props: {
                model: occupyData.value,
                rules: occupyRules,
              },
            }}
          >
            <bk-form-item label={t("占位符")} property="textInputStr" required>
              <bk-input
                value={occupyData.value.textInputStr}
                placeholder={t("请输入")}
                on-change={(value) =>
                  (occupyData.value.textInputStr = value.trim().toUpperCase())
                }
                onEnter={handleSubmitOccupy}
              />
            </bk-form-item>
            <div class="btn-box">
              <bk-button
                size="small"
                theme="primary"
                onClick={handleSubmitOccupy}
              >
                {t("确认提取")}
              </bk-button>
              <bk-button size="small" onClick={handleCancelOccupy}>
                {t("取消")}
              </bk-button>
            </div>
          </bk-form>
        </div>
      </div>
    );
  },
});
