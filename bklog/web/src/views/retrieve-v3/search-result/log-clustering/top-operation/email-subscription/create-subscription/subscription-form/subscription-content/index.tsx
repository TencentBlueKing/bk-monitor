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
import { useRoute } from "vue-router/composables";
import { defineComponent, ref, computed, onMounted, watch } from "vue";
import useLocale from "@/hooks/use-locale";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import { type IndexSetDataList } from "@/services/retrieve";
import { transformDataKey } from "@/components/monitor-echarts/utils";

import "./index.scss";

export default defineComponent({
  name: "SubscriptionContent",
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
    const route = useRoute();
    const store = useStore();

    const formRef = ref<any>(null);
    const formData = ref({
      scenario_config: {
        index_set_id: 0,
        log_display_count: 30,
        year_on_year_hour: 1,
        generate_attachment: true,
        is_show_new_pattern: false,
        // 这个同比配置也不需要前端展示，暂不开放配置入口 （不用管）
        year_on_year_change: "all",
        pattern_level: "05",
      },
      frequency: {
        data_range: null,
      },
      // 表单的验证的 bug ，后期再考虑删掉
      scenario_config__log_display_count: 0,
    });
    const indexSetIDList = ref<IndexSetDataList>([]);
    const isShowAdvancedOption = ref(false);
    const isShowYOY = ref(true);
    const dataRange = ref("5minutes");

    const indexSetName = computed(
      () =>
        indexSetIDList.value.find(
          (item) => item.index_set_id === Number(props.indexId || 0)
        )?.index_set_name || ""
    );

    const Scenario = {
      clustering: t("日志聚类"),
      dashboard: t("仪表盘"),
      scene: t("观测场景"),
    };

    const timeOptions = [
      { id: "5minutes", n: 5, unit: t("分钟") },
      { id: "15minutes", n: 15, unit: t("分钟") },
      { id: "30minutes", n: 30, unit: t("分钟") },
      { id: "1hours", n: 1, unit: t("小时") },
      { id: "3hours", n: 3, unit: t("小时") },
      { id: "6hours", n: 6, unit: t("小时") },
      { id: "12hours", n: 12, unit: t("小时") },
      { id: "24hours", n: 24, unit: t("小时") },
      { id: "2days", n: 2, unit: t("天") },
      { id: "7days", n: 7, unit: t("天") },
      { id: "30days", n: 30, unit: t("天") },
    ];

    const YOYList = [
      { id: 0, name: t("不比对") },
      ...[1, 2, 3, 6, 12, 24].map((hour) => ({
        id: hour,
        name: t("{0}小时前", [hour]),
      })),
    ];

    const timeRangeOption = timeOptions.map(({ id, n, unit }) => ({
      id,
      name: t(`近{n}${unit}`, { n }),
    }));

    const rules = {
      scenario_config__log_display_count: [
        {
          required: true,
          message: t("必填项"),
          trigger: "change",
        },
        {
          validator: (value: number) => {
            return Number(value) >= 0 && !/^-?\d+\.\d+$/.test(String(value));
          },
          message: t("必需为正整数"),
          trigger: "change",
        },
      ],
    };

    const getTimeRangeObj = (str: string) => {
      if (str === "none") return undefined;
      let res = {
        timeLevel: "hours",
        number: 24,
      };
      const isMatch = str.match(/(\d+)(minutes|hours|days)/);
      if (isMatch) {
        const [, date, level] = isMatch;
        res = {
          timeLevel: level,
          number: +date,
        };
      }
      return transformDataKey(res, true);
    };

    watch(
      dataRange,
      () => {
        formData.value.frequency.data_range = getTimeRangeObj(dataRange.value);
      },
      {
        immediate: true,
      }
    );

    /** 获取索引集 列表，需要取其中的 name */
    const getIndexSetList = () => {
      $http
        .request("retrieve/getIndexSetList", {
          query: {
            space_uid: store.state.space.space_uid,
          },
        })
        .then((response) => {
          indexSetIDList.value = response.data as IndexSetDataList;
        });
    };

    /**
     * 给 邮件标题 和 订阅名称 添加默认变量
     * 以及从 url 中提取并赋值 展示同比 和 Pattern 。
     */
    const setFormDefaultValue = () => {
      const clusterRouteParams = JSON.parse(
        (route.query.clusterRouteParams as string) || "{}"
      );
      if (clusterRouteParams?.requestData?.year_on_year_hour) {
        formData.value.scenario_config.year_on_year_hour =
          clusterRouteParams?.requestData?.year_on_year_hour;
      } else {
        isShowYOY.value = false;
        formData.value.scenario_config.year_on_year_hour = 0;
      }
    };

    const handleLogDisplayCountChange = (value: number) => {
      formData.value.scenario_config.log_display_count = value;
      formData.value.scenario_config__log_display_count = value;
    };

    const handleIsShowYoyChange = (value: boolean) => {
      isShowYOY.value = value;
      formData.value.scenario_config.year_on_year_hour = value ? 1 : 0;
    };

    const getValue = async () => {
      await formRef.value.validate();
      return formData.value;
    };

    onMounted(() => {
      getIndexSetList();
      setFormDefaultValue();
    });

    expose({ getValue });

    return () => (
      <div class="subscription-content-container">
        <div class="title">{t("订阅内容")}</div>
        <bk-form
          ref={formRef}
          class="form-container"
          {...{
            props: {
              model: formData.value,
              rules,
            },
          }}
          label-width={200}
        >
          {props.mode === "create" && (
            <bk-form-item class="text-content" label={t("订阅场景")}>
              {Scenario[props.scenario]}
            </bk-form-item>
          )}
          {props.mode === "create" && (
            <bk-form-item class="text-content" label={t("索引集")}>
              {indexSetName.value}
            </bk-form-item>
          )}

          <div class="advanced-option">
            <bk-button
              theme="primary"
              size="small"
              text
              onClick={() =>
                (isShowAdvancedOption.value = !isShowAdvancedOption.value)
              }
            >
              <div style="display: flex; align-items: center;">
                {props.mode === "create" && t("高级配置")}
                <i
                  style="font-size: 20px;"
                  class={[
                    "icon-monitor",
                    !isShowAdvancedOption.value
                      ? "bklog-icon bklog-expand-small"
                      : "bklog-icon bklog-collapse-small",
                  ]}
                ></i>
              </div>
            </bk-button>
          </div>

          {/* 高级设置 */}
          {isShowAdvancedOption.value && (
            <div>
              {props.mode === "create" && (
                <div>
                  <bk-form-item label={t("时间范围")} required>
                    <bk-select
                      style="width: 465px;"
                      value={dataRange.value}
                      on-change={(value) => (dataRange.value = value)}
                      clearable={false}
                    >
                      {timeRangeOption.map((item) => {
                        return (
                          <bk-option id={item.id} name={item.name}></bk-option>
                        );
                      })}
                    </bk-select>
                    <div class="time-range-tip">
                      <log-icon common type="info-circle" />
                      <span class="tip">
                        {t("当前日志查询时间范围不支持静态区间")}
                      </span>
                    </div>
                  </bk-form-item>
                </div>
              )}

              <bk-form-item
                error-display-type="normal"
                label={t("最大展示数量")}
                property="scenario_config__log_display_count"
                style="margin-top: 24px;"
                required
              >
                <bk-input
                  style="width: 198px;"
                  value={formData.value.scenario_config.log_display_count}
                  max={500}
                  min={0}
                  type="number"
                  on-change={handleLogDisplayCountChange}
                >
                  <div class="group-text" slot="append">
                    {t("条")}
                  </div>
                </bk-input>
              </bk-form-item>
              <div class="mix-operate-main">
                <div class="yoy-main">
                  <bk-checkbox
                    value={isShowYOY.value}
                    on-change={handleIsShowYoyChange}
                  >
                    {t("展示同比")}
                  </bk-checkbox>
                  <bk-select
                    style="width: 116px;margin-left: 12px;"
                    value={formData.value.scenario_config.year_on_year_hour}
                    clearable={false}
                    disabled={!isShowYOY.value}
                    on-change={(value) =>
                      (formData.value.scenario_config.year_on_year_hour = value)
                    }
                  >
                    {YOYList.map((item) => {
                      return (
                        <bk-option
                          id={item.id}
                          v-show={isShowYOY.value && item.id !== 0}
                          name={item.name}
                        ></bk-option>
                      );
                    })}
                  </bk-select>
                </div>
                <div style="margin-top: 8px;">
                  <bk-checkbox
                    value={formData.value.scenario_config.generate_attachment}
                    on-change={(value) =>
                      (formData.value.scenario_config.generate_attachment =
                        value)
                    }
                  >
                    {t("生成附件")}
                  </bk-checkbox>
                </div>
                <div style="margin-top: 12px;">
                  <bk-checkbox
                    value={formData.value.scenario_config.is_show_new_pattern}
                    on-change={(value) =>
                      (formData.value.scenario_config.is_show_new_pattern =
                        value)
                    }
                  >
                    {t("只展示新类 Pattern")}
                  </bk-checkbox>
                </div>
              </div>
            </div>
          )}
        </bk-form>
      </div>
    );
  },
});
