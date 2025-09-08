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

import { defineComponent, ref, computed, watch } from "vue";
import useLocale from "@/hooks/use-locale";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import { bkMessage } from "bk-magic-vue";
import { StrategyType } from "../index";
import { type UserGroupList } from "@/services/retrieve";
import { type IResponseData } from "@/services/type";

import "./index.scss";

export default defineComponent({
  name: "EditStrategy",
  props: {
    configData: {
      type: Object,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    type: {
      type: String,
      default: "new_cls_strategy",
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const rules = {
      interval: [
        {
          required: true,
          message: t("必填项"),
          trigger: "blur",
        },
      ],
      threshold: [
        {
          required: true,
          message: t("必填项"),
          trigger: "blur",
        },
      ],
      level: [
        {
          required: true,
          message: t("必填项"),
          trigger: "blur",
        },
      ],
      user_groups: [
        {
          required: true,
          message: t("必填项"),
          trigger: "blur",
        },
      ],
    };

    const levelSelectList = [
      { id: 1, name: t("致命") },
      { id: 2, name: t("预警") },
      { id: 3, name: t("提醒") },
    ];

    const levelIconMap = {
      1: {
        icon: "weixian",
        color: "#E71818",
      },
      2: {
        icon: "circle-alert-filled",
        color: "#F59500",
      },
      3: {
        icon: "info-fill",
        color: "#3A84FF",
      },
    };

    const strategyFromRef = ref<any>(null);
    const isShowDialog = ref(false);
    const formLoading = ref(false);
    const levelPanelShow = ref(false);
    const groupSelectList = ref<
      {
        id: number;
        name: string;
      }[]
    >([]);
    const formData = ref({} as any);

    const isAlarmType = computed(() => props.type === StrategyType.NEW_CLASS);
    const bkBizId = computed(() => store.state.bkBizId);

    watch(
      () => [props.configData, isAlarmType.value, isShowDialog.value],
      () => {
        if (!isShowDialog.value) {
          return;
        }

        if (props.configData) {
          formData.value = isAlarmType.value
            ? structuredClone(props.configData[StrategyType.NEW_CLASS])
            : structuredClone(props.configData[StrategyType.SUDDEN_INCREASE]);
        }
      },
      {
        deep: true,
        immediate: true,
      },
    );

    watch(
      () => props.isShow,
      () => {
        isShowDialog.value = props.isShow;
      },
      { immediate: true },
    );

    const handleConfirmSubmit = async () => {
      try {
        await strategyFromRef.value.validate();
        const submitPostStr = isAlarmType.value
          ? "retrieve/newClsStrategy"
          : "retrieve/normalStrategy";
        const { label_name, ...otherData } = formData.value;
        const res = await $http.request(submitPostStr, {
          params: {
            index_set_id: props.indexId,
          },
          data: otherData,
        });
        if (res.code === 0) {
          bkMessage({
            theme: "success",
            message: t("操作成功"),
          });
          handleDialogClose();
          emit("success");
        }
      } catch (e) {
        console.error(e);
      }
    };

    /** 给索引集添加标签 */
    const requestGetUserGroup = () => {
      formLoading.value = true;
      $http
        .request("retrieve/userGroup", {
          data: {
            bk_biz_id: bkBizId.value,
          },
        })
        .then((res: IResponseData<UserGroupList>) => {
          groupSelectList.value = res.data.map((item) => ({
            id: item.id,
            name: item.name,
          }));
        })
        .finally(() => {
          formLoading.value = false;
        });
    };

    const handleOpenDialog = (isOpen: boolean) => {
      isShowDialog.value = isOpen;
      if (isOpen) {
        requestGetUserGroup();
      } else {
        strategyFromRef.value.clearError();
      }
    };

    const handleCreateUserGroups = () => {
      window.open(
        `${window.MONITOR_URL}/?bizId=${bkBizId.value}#/alarm-group/add`,
        "_blank",
      );
    };

    const handleDialogClose = () => {
      emit("update:isShow", false);
      isShowDialog.value = false;
    };

    return () => (
      <bk-dialog
        width={480}
        ext-cls="strategy-dialog"
        value={isShowDialog.value}
        confirm-fn={handleConfirmSubmit}
        header-position="left"
        mask-close={false}
        on-cancel={handleDialogClose}
        theme="primary"
        on-value-change={handleOpenDialog}
      >
        <div slot="header">
          <div class="header-main">
            <span class="title-main">
              {t(props.isEdit ? "编辑策略" : "新建策略")}
            </span>
            <span class="split-line"></span>
            <span class="title-sub">
              {isAlarmType.value ? t("新类告警") : t("数量突增告警")}
            </span>
          </div>
        </div>
        <bk-form
          ref={strategyFromRef}
          v-bkloading={{ isLoading: formLoading.value }}
          form-type="vertical"
          {...{
            props: {
              model: formData.value,
              rules,
            },
          }}
        >
          <bk-form-item
            v-show={isAlarmType.value}
            desc-type={"icon"}
            label={t("新类告警间隔（天）")}
            property="interval"
            required
          >
            <bk-input
              value={formData.value.interval}
              placeholder={t(
                "每隔 n（整数）天数，再次产生的日志模式将视为新类",
              )}
              show-controls={false}
              type="number"
              on-change={(value) => (formData.value.interval = value)}
            />
            <div class="form-item-tip">
              {t(
                "表示近一段时间内新增日志模式，可自定义判定的时间区间，如：近 30 天内新增",
              )}
            </div>
          </bk-form-item>
          <bk-form-item
            v-show={isAlarmType.value}
            desc-type={"icon"}
            label={t("新类告警阈值")}
            property="threshold"
            required
          >
            <bk-input
              value={formData.value.threshold}
              placeholder={t("新类对应日志触发告警的条数")}
              show-controls={false}
              type="number"
              on-change={(value) => (formData.value.threshold = value)}
            />
            <div class="form-item-tip">
              {t("表示某日志模式数量突然异常增长，可能某些模块突发风险")}
            </div>
          </bk-form-item>
          <bk-form-item label={t("告警级别")} property="level" required>
            <bk-select
              value={formData.value.level}
              clearable={false}
              on-change={(value) => (formData.value.level = value)}
              on-toggle={(isOpen) => (levelPanelShow.value = isOpen)}
            >
              <div slot="trigger" class="level-trigger-main">
                <div class="dispaly-main">
                  <log-icon
                    type={levelIconMap[formData.value.level]?.icon || ""}
                    style={{
                      color: levelIconMap[formData.value.level]?.color,
                      fontSize: "14px",
                    }}
                  />
                  <span style="margin-left:4px">
                    {
                      levelSelectList.find(
                        (item) => item.id === formData.value.level,
                      )?.name
                    }
                  </span>
                </div>
                <div
                  class={{
                    "trigger-icon": true,
                    "is-rotate": levelPanelShow.value,
                  }}
                >
                  <log-icon common type="angle-down" />
                </div>
              </div>
              {levelSelectList.map((item) => (
                <bk-option id={item.id} name={item.name}>
                  <log-icon
                    type={levelIconMap[item.id].icon}
                    style={{
                      color: levelIconMap[item.id].color,
                      fontSize: "14px",
                    }}
                  />
                  <span style="margin-left:4px">{item.name}</span>
                </bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            v-show={!isAlarmType.value}
            label={t("变化敏感度")}
            property="sensitivity"
            required
          >
            <div class="level-box">
              <bk-slider
                value={formData.value.sensitivity}
                max-value={10}
                min-value={0}
                on-change={(value) => (formData.value.sensitivity = value)}
              >
                <span style="margin-right: 10px;" slot="start">
                  {t("低")}
                </span>
                <span style="margin-left: 10px;" slot="end">
                  {t("高")}
                </span>
              </bk-slider>
            </div>
          </bk-form-item>
          <bk-form-item label={t("告警组")} property="user_groups" required>
            <bk-select
              value={formData.value.user_groups}
              ext-popover-cls="strategy-create-groups"
              display-tag
              multiple
              searchable
              on-change={(value) => (formData.value.user_groups = value)}
            >
              {groupSelectList.value.map((item) => (
                <bk-option id={item.id} name={item.name}></bk-option>
              ))}
              <div
                class="groups-btn"
                slot="extension"
                onClick={handleCreateUserGroups}
              >
                <i class="bk-icon icon-plus-circle"></i>
                {t("新增告警组")}
              </div>
            </bk-select>
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  },
});
