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

import { computed, defineComponent, ref, watch } from "vue";
import VueDraggable from "vuedraggable";
import useLocale from "@/hooks/use-locale";
import "./index.scss";

export default defineComponent({
  name: "FieldsConfig",
  components: {
    VueDraggable,
  },
  props: {
    total: {
      type: Array<string>,
      required: true,
    },
    display: {
      type: Array<string>,
      required: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const fieldConfigRef = ref();
    const totalFieldNames = ref<string[]>([]); // 所有的字段名
    const displayFieldNames = ref<string[]>([]); // 展示的字段名
    const confirmLoading = ref(false);

    const restFieldNames = computed(() =>
      totalFieldNames.value.filter(
        (field) => !displayFieldNames.value.includes(field)
      )
    );
    const disabledRemove = computed(() => displayFieldNames.value.length <= 1);

    const dragOptions = {
      animation: 150,
      tag: "ul",
      handle: ".bklog-drag-dots",
      "ghost-class": "sortable-ghost-class",
    };

    watch(
      () => props.total,
      () => {
        totalFieldNames.value = [...props.total];
        displayFieldNames.value = [...props.display];
      },
      {
        immediate: true,
      }
    );

    /**
     * 移除某个显示字段
     */
    const removeItem = (index: number) => {
      !disabledRemove.value && displayFieldNames.value.splice(index, 1);
    };
    /**
     * 增加某个字段名
     */
    const addItem = (fieldName: string) => {
      displayFieldNames.value.push(fieldName);
    };

    const handleConfirm = () => {
      confirmLoading.value = true;
      emit("confirm", displayFieldNames.value);
    };

    const handleCancel = () => {
      emit("cancel");
    };

    expose({
      getDom: () => fieldConfigRef.value,
      closeConfirmLoading: () => {
        confirmLoading.value = false;
      },
    });

    return () => (
      <div style="display: none">
        <div class="fields-config-tippy" ref={fieldConfigRef}>
          <div class="config-title">{t("设置显示与排序")}</div>
          <div class="field-list-container">
            <div class="field-list">
              <div class="list-title">
                <i18n path="显示字段（已选 {0} 条)">
                  <span>{displayFieldNames.value.length}</span>
                </i18n>
              </div>
              <vue-draggable {...dragOptions} value={displayFieldNames.value}>
                <transition-group>
                  {displayFieldNames.value.map((field, index) => (
                    <li class="list-item display-item" key={index}>
                      <span class="icon bklog-icon bklog-drag-dots"></span>
                      <div class="field_name">{field}</div>
                      <div
                        class={[
                          "operate-button",
                          disabledRemove.value && "disabled",
                        ]}
                        on-click={() => removeItem(index)}
                      >
                        {t("删除")}
                      </div>
                    </li>
                  ))}
                </transition-group>
              </vue-draggable>
            </div>
            <div class="field-list">
              <div class="list-title">{t("其他字段")}</div>
              <ul>
                {restFieldNames.value.map((field, index) => (
                  <li class="list-item rest-item" key={index}>
                    <div class="field_name">{field}</div>
                    <div class="operate-button" on-click={() => addItem(field)}>
                      {t("添加")}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div class="config-buttons">
            <bk-button
              style="margin-right: 8px"
              size="small"
              theme="primary"
              loading={confirmLoading.value}
              on-click={handleConfirm}
            >
              {t("确定")}
            </bk-button>
            <bk-button
              style="margin-right: 24px"
              size="small"
              on-click={handleCancel}
            >
              {t("取消")}
            </bk-button>
          </div>
        </div>
      </div>
    );
  },
});
