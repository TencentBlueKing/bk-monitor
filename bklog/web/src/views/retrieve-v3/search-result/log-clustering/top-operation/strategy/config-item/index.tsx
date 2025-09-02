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

import { computed, defineComponent, ref, type CreateElement } from "vue";
import useLocale from "@/hooks/use-locale";
import EditStrategy from "../edit-strategy";
import { bkInfoBox, bkMessage } from "bk-magic-vue";
import $http from "@/api";
import { StrategyType } from "../index";

import "./index.scss";

export default defineComponent({
  name: "ConfigItem",
  components: {
    EditStrategy,
  },
  props: {
    configData: {
      type: Object,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    configured: {
      type: Boolean,
      default: false,
    },
    type: {
      type: String,
      default: "new_cls_strategy",
    },
    bkBizId: {
      type: String,
      require: true,
    },
    labelName: {
      type: Array<string>,
      require: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const isShowDialog = ref(false);
    const isEdit = ref(false);

    const isNewClass = computed(() => props.type === StrategyType.NEW_CLASS);

    let h: CreateElement;

    const handleEditStrategy = () => {
      isEdit.value = true;
      isShowDialog.value = true;
    };

    const handleDeleteStrategy = () => {
      const strategyMapping = {
        [StrategyType.NEW_CLASS]: "new_cls_strategy",
        [StrategyType.SUDDEN_INCREASE]: "normal_strategy",
      };
      const strategyType = strategyMapping[props.type];
      bkInfoBox({
        title: t("是否删除该策略？"),
        confirmLoading: true,
        theme: "danger",
        okText: t("删除"),
        subHeader: h(
          "div",
          {
            style: {
              display: "flex",
              justifyContent: "center",
            },
          },
          [
            h(
              "span",
              {
                style: {
                  color: "#63656E",
                },
              },
              [t("策略：")]
            ),
            h(
              "span",
              t(isNewClass.value ? "新类告警策略" : "数量突增告警策略")
            ),
          ]
        ),
        confirmFn: async () => {
          try {
            const res = await $http.request("retrieve/deleteClusteringInfo", {
              params: {
                index_set_id: props.indexId,
              },
              data: { strategy_type: strategyType },
            });
            if (res.code === 0) {
              isShowDialog.value = false;
              bkMessage({
                theme: "success",
                message: t("操作成功"),
              });
              emit("refresh-strategy-info");
            }
            return true;
          } catch (e) {
            console.warn(e);
            return false;
          }
        },
      });
    };

    /** 跳转告警策略列表 */
    const handleViewStrategy = () => {
      window.open(
        `${window.MONITOR_URL}/?bizId=${
          props.bkBizId
        }#/strategy-config?strategyLabels=${JSON.stringify(props.labelName)}`,
        "_blank"
      );
    };

    const operationList = [
      {
        text: t("编辑策略"),
        icon: "edit",
        func: handleEditStrategy,
      },
      {
        text: t("查看策略"),
        icon: "audit",
        func: handleViewStrategy,
      },
      {
        text: t("删除策略"),
        icon: "log-delete",
        func: handleDeleteStrategy,
      },
    ];

    /** 点击新增告警 */
    const handleAddNewStrategy = () => {
      isShowDialog.value = true;
    };

    return (hFunc: CreateElement) => {
      h = hFunc;
      return (
        <div class="strategy-operate-main">
          <div class="icon-wraper">
            <log-icon
              type={isNewClass.value ? "xinleigaojing" : "tuzenggaojing"}
            />
          </div>
          <span class="type-title">
            {isNewClass.value ? t("新类告警策略") : t("数量突增策略")}：
          </span>
          {props.configured ? (
            <span class="configed">{t("已配置")}</span>
          ) : (
            <span class="not-config">{t("未配置")}</span>
          )}
          <bk-dropdown-menu align="right">
            <div slot="dropdown-trigger">
              <div class="more-icon-wraper">
                <log-icon class="more-icon" type="more" />
              </div>
            </div>
            <div slot="dropdown-content">
              <div
                class={[
                  "dropdown-list",
                  { "is-not-config": !props.configured },
                ]}
              >
                {props.configured ? (
                  operationList.map((item) => (
                    <div class="item" on-click={item.func}>
                      <log-icon type={item.icon} class="item-icon" />
                      <span class="item-title">{item.text}</span>
                    </div>
                  ))
                ) : (
                  <div class="item" on-click={handleAddNewStrategy}>
                    <log-icon
                      type="-celve"
                      style="font-size: 14px"
                      class="item-icon"
                    />
                    <span class="item-title">{t("新建策略")}</span>
                  </div>
                )}
              </div>
            </div>
          </bk-dropdown-menu>
          <edit-strategy
            type={props.type}
            isShow={isShowDialog.value}
            isEdit={isEdit.value}
            indexId={props.indexId}
            configData={props.configData}
            on-success={() => emit("refresh-strategy-info")}
            {...{
              on: {
                "update:isShow": (val: boolean) => {
                  isShowDialog.value = val;
                },
              },
            }}
          />
        </div>
      );
    };
  },
});
