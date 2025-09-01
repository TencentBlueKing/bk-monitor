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
import BkUserSelector from "@blueking/user-selector";
import { defineComponent, ref, onMounted, nextTick, watch } from "vue";
import { bkMessage } from "bk-magic-vue";
import useLocale from "@/hooks/use-locale";
import $http from "@/api";
import dayjs from "dayjs";
import useStore from "@/hooks/use-store";
import { type VariableList } from "@/services/new-report";
import "./index.scss";

export default defineComponent({
  name: "SendConfig",
  components: {
    BkUserSelector,
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
    const { t } = useLocale();
    const store = useStore();

    const formRef = ref<any>(null);
    const variableTableData = ref<VariableList>([]);
    const effectiveEndRef = ref();
    const isIncludeWeekend = ref(true);
    const frequencyHourRef = ref();
    const customHourInput = ref("");
    const formData = ref({
      scenario: "clustering",
      name: "",
      start_time: 0 as number | null,
      end_time: 0 as number | null,
      // 给他人/自己 订阅 。self, others 仅自己/给他人
      subscriber_type: "self",
      // 这里不可以直接对组件赋值，不然最后会带上不必要的参数。
      frequency: {
        type: 5,
        hour: 0.5,
        run_time: "",
        week_list: [],
        day_list: [],
      },
      channels: [
        {
          is_enabled: true,
          subscribers: [],
          channel_name: "user",
        },
        {
          is_enabled: false,
          subscribers: [],
          send_text: "",
          channel_name: "email",
        },
        {
          is_enabled: false,
          subscribers: [],
          channel_name: "wxbot",
        },
      ] as any[],
      timerange: [] as unknown as [string, string],
    });
    /** 针对 订阅人 一项进行特殊的校验异常提醒。因为该项内容有三个输入框要分别处理。 */
    const errorTips = ref({
      user: {
        message: "",
        defaultMessage: t("内部邮件不可为空"),
        isShow: false,
      },
      email: {
        message: "",
        defaultMessage: t("外部邮件不可为空"),
        isShow: false,
      },
      wxbot: {
        message: "",
        defaultMessage: t("企业微信群不可为空"),
        isShow: false,
      },
    });
    /** 订阅人 项相关变量。这里会监听该变量变化动态修改 formData 中 channels 。 */
    const subscriberInput = ref({
      user: [],
      email: "",
      wxbot: "",
    });
    /** 任务有效期，视图绑定用。 */
    const timerange = ref({
      start: "",
      end: "",
    });

    /** 发送频率相关。该对象最后会把该对象数据copy到 formData 上，因为其中 run_time 的日期格式不同导致 日期组件 报异常，所以这里单独抽出整个对象。 */
    const frequency = ref({
      type: 5,
      hour: 0.5,
      run_time: dayjs().format("HH:mm:ss"),
      only_once_run_time: dayjs().format("YYYY-MM-DD HH:mm:ss"),
      week_list: [],
      day_list: [],
    });
    const emailRegex =
      /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

    const rules = {
      frequency: [
        {
          validator: () => {
            switch (formData.value.frequency.type) {
              case FrequencyType.weekly:
                return frequency.value.week_list.length > 0;
              case FrequencyType.monthly:
                return frequency.value.day_list.length > 0;
              default:
                return true;
            }
          },
          message: t("必填项"),
          trigger: "change",
        },
      ],
      channels: [
        {
          validator: () => {
            if (formData.value.subscriber_type === "self") return true;
            const enabledList = formData.value.channels.filter(
              (item) => item.is_enabled,
            );
            if (enabledList.length === 0) {
              // 提醒用户，三个输入框都没有选中，必须选中一个。
              Object.keys(errorTips.value).forEach((key) => {
                errorTips.value[key].message = t("请至少选择一种订阅方式");
                errorTips.value[key].isShow = true;
              });
              return false;
            }
            Object.keys(errorTips.value).forEach((key) => {
              errorTips.value[key].isShow = false;
            });

            if (enabledList.length === 0) return false;
            const subscriberList = enabledList.filter(
              (item) => item.subscribers.length,
            );

            let isInvalid = false;
            // 选中了，但是输入框没有添加任何订阅内容，将选中的输入框都显示提示。
            enabledList.forEach((item) => {
              if (!item.subscribers.length) {
                errorTips.value[item.channel_name].message =
                  errorTips.value[item.channel_name].defaultMessage;
                errorTips.value[item.channel_name].isShow = true;
                isInvalid = true;
              } else {
                if (item.channel_name === "email") {
                  // 需要对邮箱格式校验
                  item.subscribers.forEach((subscriber) => {
                    const result = String(subscriber.id || "")
                      .toLowerCase()
                      .match(emailRegex);
                    if (!result) {
                      isInvalid = true;
                      errorTips.value[item.channel_name].isShow = true;
                      errorTips.value[item.channel_name].message =
                        t("邮件格式有误");
                    }
                  });
                } else {
                  errorTips.value[item.channel_name].isShow = false;
                }
              }
            });
            if (isInvalid || !subscriberList.length) {
              return false;
            }
            return true;
          },
          message: " ",
          trigger: "blur",
        },
      ],
      timerange: [
        {
          validator: () => {
            return (
              formData.value.timerange.length === 2 &&
              !!formData.value.timerange[0]
            );
          },
          message: t("生效起始时间必填"),
          trigger: "change",
        },
        {
          validator: () => {
            const [start, end] = formData.value.timerange;
            // end 为空串时说明是无期限。不需要再做后续计算。
            if (!end) return true;
            const result = dayjs(start).diff(end);
            return result < 0;
          },
          message: t("生效结束时间不能小于生效起始时间"),
          trigger: "change",
        },
      ],
      name: [
        {
          required: true,
          message: t("必填项"),
          trigger: "change",
        },
      ],
    };

    /** 按天频率 包含周末 */
    const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
    /** 按天频率 不包含周末 */
    const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];
    const hours = [0.5, 1, 2, 6, 12];
    /** 发送频率 中 按小时 的小时选项。 */
    const hourOption = hours.map((hour) => ({
      id: hour,
      name: t("{0}小时", [hour]),
    }));
    const daysOfWeek = [
      "星期一",
      "星期二",
      "星期三",
      "星期四",
      "星期五",
      "星期六",
      "星期日",
    ];
    const weekList = daysOfWeek.map((day, index) => ({
      name: t(day),
      id: index + 1,
    }));

    const enum FrequencyType {
      /** 按天 */
      dayly = 2,
      /** 按小时 */
      hourly = 5,
      /** 按月 */
      monthly = 4,
      /** 仅一次 */
      onlyOnce = 1,
      /** 按周 */
      weekly = 3,
    }

    const frequencyList = [
      {
        label: FrequencyType.hourly,
        text: t("按小时"),
      },
      {
        label: FrequencyType.dayly,
        text: t("按天"),
      },
      {
        label: FrequencyType.weekly,
        text: t("按周"),
      },
      {
        label: FrequencyType.monthly,
        text: t("按月"),
      },
      {
        label: FrequencyType.onlyOnce,
        text: t("仅一次"),
      },
    ];

    watch(
      () => subscriberInput.value.email,
      () => {
        const result = subscriberInput.value.email
          .split(",")
          .map((item) => {
            return {
              id: item,
              is_enabled: true,
            };
          })
          .filter((item) => item.id);
        formData.value.channels[1].subscribers = result;
      },
    );

    watch(
      () => subscriberInput.value.wxbot,
      () => {
        const result = subscriberInput.value.wxbot
          .split(",")
          .map((item) => {
            return {
              id: item,
              is_enabled: true,
            };
          })
          .filter((item) => item.id);
        formData.value.channels[2].subscribers = result;
      },
    );

    watch(
      () => formData.value.frequency.type,
      () => {
        if (formData.value.frequency.type === FrequencyType.onlyOnce) {
          formData.value.start_time = null;
          formData.value.end_time = null;
          // 点击 仅一次 时刷新一次时间。
          frequency.value.only_once_run_time = dayjs().format(
            "YYYY-MM-DD HH:mm:ss",
          );
        } else {
          // 把丢掉的 start_time 和 end_time 补回去
          const [startTime, endTime] = formData.value.timerange;
          formData.value.start_time = dayjs(startTime).unix();
          formData.value.end_time = dayjs(endTime).unix();
        }
      },
    );

    /**
     * 给 邮件标题 和 订阅名称 添加默认变量
     * 以及从 url 中提取并赋值 展示同比 和 Pattern 。
     */
    const setFormDefaultValue = () => {
      const spaceList = store.state.mySpaceList;
      const bizId = store.state.bkBizId;
      const bizName =
        spaceList.find((item) => item.bk_biz_id === bizId)?.space_name || "";
      const currentDate = dayjs(new Date()).format("YYYY-MM-DD HH:mm");
      const titleMapping = {
        clustering: t("{0}-日志聚类统计报表-{1}", [bizName, currentDate]),
      };
      const targetTitle = titleMapping[props.scenario] || "";
      formData.value.name = `${targetTitle}-${
        store.state.userMeta?.username || ""
      }`;
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

    /** 任务有效期 调整时间格式 */
    const handleTimeRangeChange = (range: [string, string]) => {
      formData.value.timerange = structuredClone(range);
      const result = range.map((date) => {
        // 结束时间可能是空串（代表 无期限），这里用 undefined 代替，即不需要提交。
        return date ? dayjs(date).unix() : undefined;
      });
      const [startTime, endTime] = result;
      formData.value.start_time = startTime!;
      formData.value.end_time = endTime!;
    };

    /** 取消按钮文本设置为永久 */
    const handleDatePickerOpen = (state: boolean) => {
      if (state) {
        const ele = effectiveEndRef.value.$el.querySelector(
          ".bk-picker-confirm a:nth-child(2)",
        );
        ele.innerText = t("永久");
        ele.setAttribute("class", "confirm");
      }
    };

    const handleEnterCustomHour = () => {
      // 添加自定义 发送频率 ，如果输入有重复要直接选中。
      let inputNumber = Number(customHourInput.value);
      if (!inputNumber) {
        return bkMessage({
          theme: "warning",
          message: t("请输入有效数值"),
        });
      }
      const minNum = 0.5;
      const maxNum = 24;
      if (inputNumber > maxNum) {
        inputNumber = maxNum;
        customHourInput.value = String(inputNumber);
      }
      if (inputNumber < minNum) {
        inputNumber = minNum;
        customHourInput.value = String(inputNumber);
      }
      const isHasDuplicatedNum = hourOption.find(
        (item) => item.id === inputNumber,
      );
      if (!isHasDuplicatedNum) {
        hourOption.push({ id: inputNumber, name: t("{0}小时", [inputNumber]) });
      }
      frequency.value.hour = inputNumber;
      customHourInput.value = "";
      frequencyHourRef.value?.close?.();
    };

    const getValue = async () => {
      await formRef.value.validate();
      // 先手动重置一遍
      Object.assign(formData.value.frequency, {
        hour: 0,
        run_time: "",
        week_list: [],
        day_list: [],
      });
      switch (formData.value.frequency.type) {
        case FrequencyType.hourly:
          Object.assign(formData.value.frequency, {
            hour: frequency.value.hour,
          });
          break;
        case FrequencyType.dayly:
          Object.assign(formData.value.frequency, {
            run_time: frequency.value.run_time,
            week_list: isIncludeWeekend.value
              ? INCLUDES_WEEKEND
              : EXCLUDES_WEEKEND,
          });
          break;
        case FrequencyType.weekly:
          Object.assign(formData.value.frequency, {
            run_time: frequency.value.run_time,
            week_list: frequency.value.week_list,
          });
          break;
        case FrequencyType.monthly:
          Object.assign(formData.value.frequency, {
            run_time: frequency.value.run_time,
            day_list: frequency.value.day_list,
          });
          break;
        case FrequencyType.onlyOnce:
          Object.assign(formData.value.frequency, {
            run_time: dayjs(frequency.value.only_once_run_time).format(
              "YYYY-MM-DD HH:mm:ss",
            ),
          });
          break;
        default:
          break;
      }
      return formData.value;
    };

    onMounted(() => {
      getVariablesList();
      setFormDefaultValue();
    });

    expose({ getValue });

    return () => (
      <div class="send-config-container">
        <div class="title">{t("发送配置")}</div>

        <bk-form
          ref={formRef}
          class="send-config-form"
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
            label={t("订阅名称")}
            property="name"
            required
          >
            <bk-input
              style="width: 465px;"
              value={formData.value.name}
              on-change={(value) => (formData.value.name = value)}
            ></bk-input>
          </bk-form-item>

          {/* 需要自定义校验规则 */}
          <bk-form-item
            id="subscriptor-item"
            error-display-type="normal"
            label={t("订阅人")}
            property="channels"
            tabindex="1"
            required
          >
            {props.mode === "create" && (
              <div>
                <bk-radio-group
                  style="display: inline;"
                  value={formData.value.subscriber_type}
                  on-change={(value) =>
                    (formData.value.subscriber_type = value)
                  }
                >
                  <bk-radio-button value="self">{t("仅自己")}</bk-radio-button>
                  <bk-radio-button value="others">
                    {t("给他人")}
                  </bk-radio-button>
                </bk-radio-group>
                {formData.value.subscriber_type === "others" && (
                  <span style="margin-left: 10px;">
                    <i
                      style="margin-right: 10px; color: #EA3636; font-size: 14px;"
                      class="bklog-icon bklog-info-fill"
                    ></i>
                    <span style="color: #63656E; font-size: 12px;">
                      {t("给他人订阅需要经过管理员审批")}
                    </span>
                  </span>
                )}
              </div>
            )}

            {formData.value.subscriber_type === "others" && (
              <div>
                <bk-checkbox
                  value={formData.value.channels[0].is_enabled}
                  on-change={(value) =>
                    (formData.value.channels[0].is_enabled = value)
                  }
                >
                  {t("内部邮件")}
                </bk-checkbox>
                <br />
                <div
                  data-is-show-error-msg={String(errorTips.value.user.isShow)}
                >
                  <bk-user-selector
                    ref="user-input"
                    style="width: 465px; display: block;"
                    value={subscriberInput.value.user}
                    api={window.BK_LOGIN_URL}
                    empty-text={t("无匹配人员")}
                    placeholder={t("选择通知对象")}
                    tag-type="avatar"
                    on-change={(v) => {
                      subscriberInput.value.user = v;
                      const userChannel = formData.value.channels.find(
                        (item) => item.channel_name === "user",
                      );
                      userChannel!.subscribers = v.map((username) => {
                        return {
                          id: username,
                          type: "user",
                          is_enabled: true,
                        };
                      });
                      nextTick(() => {
                        rules.channels[0].validator();
                      });
                    }}
                    on-remove-selected={() => {}}
                    on-select-user={() => {}}
                  ></bk-user-selector>
                  {errorTips.value.user.isShow && (
                    <div class="form-error-tip">
                      {errorTips.value.user.message}
                    </div>
                  )}
                </div>

                <div style="margin-top: 10px;">
                  <bk-checkbox
                    style="margin-top: 10px;"
                    value={formData.value.channels[1].is_enabled}
                    on-change={(value) =>
                      (formData.value.channels[1].is_enabled = value)
                    }
                  >
                    {t("外部邮件")}
                  </bk-checkbox>
                </div>
                <div>
                  <bk-popover
                    content={t("多个邮箱使用逗号隔开")}
                    placement="right"
                    theme="light"
                    trigger="click"
                  >
                    <div
                      data-is-show-error-msg={String(
                        errorTips.value.email.isShow,
                      )}
                    >
                      <bk-input
                        ref="email-input"
                        style="width: 465px;"
                        value={subscriberInput.value.email}
                        disabled={!formData.value.channels[1].is_enabled}
                        on-change={(value) =>
                          (subscriberInput.value.email = value)
                        }
                      >
                        <template slot="prepend">
                          <div class="group-text">{t("邮件列表")}</div>
                        </template>
                      </bk-input>
                    </div>
                  </bk-popover>

                  <div data-is-show-error-msg="false">
                    <bk-input
                      style="width: 465px; margin-top: 10px;"
                      value={formData.value.channels[1].send_text}
                      disabled={!formData.value.channels[1].is_enabled}
                      placeholder={t(
                        "请遵守公司规范，切勿泄露敏感信息，后果自负！",
                      )}
                      on-change={(value) =>
                        (formData.value.channels[1].send_text = value)
                      }
                    >
                      <template slot="prepend">
                        <div class="group-text">{t("提示文案")}</div>
                      </template>
                    </bk-input>
                  </div>
                </div>
                {errorTips.value.email.isShow && (
                  <div class="form-error-tip">
                    {errorTips.value.email.message}
                  </div>
                )}

                <div style="margin-top: 10px;">
                  <bk-checkbox
                    style="margin-top: 10px;"
                    value={formData.value.channels[2].is_enabled}
                    on-change={(value) =>
                      (formData.value.channels[2].is_enabled = value)
                    }
                  >
                    {t("企业微信群")}
                  </bk-checkbox>
                </div>

                <div
                  data-is-show-error-msg={String(errorTips.value.wxbot.isShow)}
                >
                  <bk-popover
                    placement="bottom-start"
                    theme="light"
                    trigger="click"
                  >
                    <bk-input
                      ref="wxbot-input"
                      style="width: 465px;"
                      value={subscriberInput.value.wxbot}
                      disabled={!formData.value.channels[2].is_enabled}
                      on-change={(value) =>
                        (subscriberInput.value.wxbot = value)
                      }
                    >
                      <template slot="prepend">
                        <div class="group-text">{t("群ID")}</div>
                      </template>
                    </bk-input>

                    <div slot="content">
                      {t("获取会话ID方法")}: <br />
                      {t("1.群聊列表右键添加群机器人: 蓝鲸监控上云")}
                      <br />
                      {t(`2.手动 @蓝鲸监控上云 并输入关键字'会话ID'`)}
                      <br />
                      {t("3.将获取到的会话ID粘贴到输入框,使用逗号分隔")}
                    </div>
                  </bk-popover>
                </div>
                {errorTips.value.wxbot.isShow && (
                  <div class="form-error-tip">
                    {errorTips.value.wxbot.message}
                  </div>
                )}
              </div>
            )}
          </bk-form-item>

          {/* 需要自定义校验规则 */}
          <bk-form-item
            class="no-relative"
            error-display-type="normal"
            label={t("发送频率")}
            property="frequency"
            required
          >
            <bk-radio-group
              class="frequency-radio-group"
              value={formData.value.frequency.type}
              on-change={(value) => (formData.value.frequency.type = value)}
            >
              {frequencyList.map((item) => (
                <bk-radio label={item.label}>{item.text}</bk-radio>
              ))}
            </bk-radio-group>
            {formData.value.frequency.type === FrequencyType.hourly && (
              <bk-select
                ref="frequencyHourRef"
                style="width: 200px;"
                value={frequency.value.hour}
                clearable={false}
                on-change={(value) => (frequency.value.hour = value)}
              >
                {hourOption.map((item) => {
                  return <bk-option id={item.id} name={item.name} />;
                })}
                <div style="padding: 10px 0;" slot="extension">
                  <bk-input
                    value={customHourInput.value}
                    max={24}
                    min={1}
                    placeholder={t("输入自定义小时，按 Enter 确认")}
                    precision={0}
                    size="small"
                    type="number"
                    onEnter={handleEnterCustomHour}
                    // 只允许输入正整数
                    oninput={(value) => {
                      customHourInput.value = value.replace(
                        /^(0+)|[^\d]+/g,
                        "",
                      );
                    }}
                  ></bk-input>
                </div>
              </bk-select>
            )}

            {[
              FrequencyType.monthly,
              FrequencyType.weekly,
              FrequencyType.dayly,
            ].includes(formData.value.frequency.type) && (
              <div style="display: flex; align-items: center;">
                {formData.value.frequency.type === 3 && (
                  <bk-select
                    style="width: 160px; margin-right: 10px; height: 32px;"
                    value={frequency.value.week_list}
                    clearable={false}
                    multiple
                    on-change={(value) => (frequency.value.week_list = value)}
                  >
                    {weekList.map((item) => {
                      return (
                        <bk-option id={item.id} name={item.name}></bk-option>
                      );
                    })}
                  </bk-select>
                )}
                {formData.value.frequency.type === FrequencyType.monthly && (
                  <bk-select
                    style="width: 160px; margin-right: 10px; height: 32px;"
                    value={frequency.value.day_list}
                    clearable={false}
                    multiple
                    on-change={(value) => (frequency.value.day_list = value)}
                  >
                    {Array(31)
                      .fill("")
                      .map((_, index) => {
                        return (
                          <bk-option
                            id={index + 1}
                            name={index + 1 + t("号").toString()}
                          ></bk-option>
                        );
                      })}
                  </bk-select>
                )}
                <bk-time-picker
                  style="width: 130px;"
                  value={frequency.value.run_time}
                  clearable={false}
                  placeholder={t("选择时间范围")}
                  transfer
                />
                {/* 该复选值不需要提交，后续在编辑的时候需要通过 INCLUDES_WEEKEND 和 weekList 去判断即可 */}
                {formData.value.frequency.type === FrequencyType.dayly && (
                  <bk-checkbox
                    style="margin-left: 10px;"
                    value={isIncludeWeekend.value}
                    on-change={(value) => (isIncludeWeekend.value = value)}
                  >
                    {t("包含周末")}
                  </bk-checkbox>
                )}
              </div>
            )}

            {formData.value.frequency.type === FrequencyType.onlyOnce && (
              <div>
                <bk-date-picker
                  style="width: 168px;"
                  value={frequency.value.only_once_run_time}
                  clearable={false}
                  type="datetime"
                  on-change={(value) =>
                    (frequency.value.only_once_run_time = value)
                  }
                />
              </div>
            )}
          </bk-form-item>

          {formData.value.frequency.type !== FrequencyType.onlyOnce && (
            <bk-form-item
              class="no-relative"
              desc={t(
                "有效期内，订阅任务将正常发送；超出有效期，则任务失效，停止发送。",
              )}
              error-display-type="normal"
              label={t("任务有效期")}
              property="timerange"
              required
            >
              <bk-date-picker
                style="width: 220px;"
                value={timerange.value.start}
                clearable={false}
                placeholder={`${t("如")}: 2019-01-30 12:12:21`}
                type="datetime"
                onChange={(value) => {
                  timerange.value.start = value;
                  handleTimeRangeChange([
                    timerange.value.start,
                    timerange.value.end,
                  ]);
                }}
              ></bk-date-picker>
              <span style="padding:0 6px;color:#4D4F56;font-size:12px">~</span>
              <bk-date-picker
                ref={effectiveEndRef}
                style="width: 227px;"
                class="effective-end"
                value={timerange.value.end}
                placeholder={t("永久")}
                type="datetime"
                clearable
                onChange={(value) => {
                  timerange.value.end = value;
                  handleTimeRangeChange([
                    timerange.value.start,
                    timerange.value.end,
                  ]);
                }}
                on-open-change={handleDatePickerOpen}
              ></bk-date-picker>
            </bk-form-item>
          )}
        </bk-form>
      </div>
    );
  },
});
