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
import { copyText } from "@/components/monitor-echarts/utils";
import { defineComponent, ref, onMounted } from "vue";
import { bkMessage } from "bk-magic-vue";
import useLocale from "@/hooks/use-locale";
import $http from "@/api";
import { type VariableList } from "@/services/new-report";
import "./index.scss";

export default defineComponent({
  name: "EmailConfig",
  props: {
    scenario: {
      type: String,
      default: "clustering",
    },
  },
  setup(props, { expose }) {
    const { t } = useLocale();

    const formRef = ref<any>(null);
    const variableTableData = ref<VariableList>([]);
    const formData = ref({
      content_config: {
        title: "",
        is_link_enabled: true,
      },
      content_config__title: "",
    });

    const rules = {
      content_config__title: [
        {
          required: true,
          message: t("必填项"),
          trigger: "change",
        },
      ],
    };

    const handleCopy = (text: string) => {
      copyText(`{{${text}}}`, (msg) => {
        bkMessage({
          message: msg,
          theme: "error",
        });
        return;
      });
      bkMessage({
        message: t("复制成功"),
        theme: "success",
      });
    };

    /**
     * 给 邮件标题 和 订阅名称 添加默认变量
     * 以及从 url 中提取并赋值 展示同比 和 Pattern 。
     */
    const setFormDefaultValue = () => {
      const nameMapping = {
        clustering: t("{0}-日志聚类统计报表-{1}", [
          "{{business_name}}",
          "{{time}}",
        ]),
      };
      const targetName = nameMapping[props.scenario] || "";
      formData.value.content_config.title = targetName;
      formData.value.content_config__title = targetName;
    };

    /** 获取变量列表 */
    const getVariablesList = () => {
      $http
        .request("newReport/getVariables", {
          query: {
            scenario: props.scenario,
          },
        })
        .then((response) => {
          variableTableData.value = response.data as VariableList;
        });
    };

    const getValue = async () => {
      await formRef.value.validate();
      return formData.value;
    };

    onMounted(() => {
      getVariablesList();
      setFormDefaultValue();
    });

    expose({ getValue });

    return () => (
      <div class="email-config-container">
        <div class="title">{t("邮件配置")}</div>
        <bk-form
          ref={formRef}
          class="email-config-form"
          {...{
            props: {
              model: formData.value,
              rules,
            },
          }}
          label-width={200}
        >
          <bk-form-item
            error-display-type="normal"
            label={t("邮件标题")}
            property="content_config__title"
            required
          >
            <div>
              <div style="display: flex;">
                <bk-input
                  style="width: 465px;"
                  value={formData.value.content_config.title}
                  placeholder={t("请输入")}
                  onChange={(value) => {
                    formData.value.content_config.title = value;
                    formData.value.content_config__title =
                      formData.value.content_config.title;
                  }}
                ></bk-input>

                <bk-popover
                  width={435}
                  placement="bottom-start"
                  theme="light"
                  trigger="click"
                >
                  <bk-button theme="primary" size="small" text>
                    {t("变量列表")}
                  </bk-button>
                  <div slot="content">
                    <bk-table data={variableTableData.value} stripe>
                      <bk-table-column
                        width={160}
                        scopedSlots={{
                          default: ({ row }) => {
                            return (
                              <div style="display: flex; align-items: center;">
                                <span style="width: calc(100% - 20px);">
                                  {row.name}
                                </span>
                                <i
                                  style="font-size: 16px; margin-left: 5px; color: #3A84FF; cursor: pointer;"
                                  class="bklog-icon bklog-copy-2"
                                  onClick={() => handleCopy(row.name)}
                                ></i>
                              </div>
                            );
                          },
                        }}
                        label={t("变量名")}
                        prop="variable"
                      ></bk-table-column>
                      <bk-table-column
                        width={90}
                        label={t("变量说明")}
                        prop="description"
                      ></bk-table-column>
                      <bk-table-column
                        width={160}
                        label={t("示例")}
                        prop="example"
                      ></bk-table-column>
                    </bk-table>
                  </div>
                </bk-popover>
              </div>
              <bk-checkbox
                value={formData.value.content_config.is_link_enabled}
                on-change={(value) =>
                  (formData.value.content_config.is_link_enabled = value)
                }
              >
                {t("附带链接")}
              </bk-checkbox>
            </div>
          </bk-form-item>
        </bk-form>
      </div>
    );
  },
});
