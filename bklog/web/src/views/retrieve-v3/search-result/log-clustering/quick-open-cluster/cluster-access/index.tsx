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
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import $http from "@/api";
import FilterRule from "@/components/filter-rule";
import PreviewResult from "./preview-result";

import "./index.scss";

export default defineComponent({
  name: "QuickOpenCluster",
  components: {
    FilterRule,
    PreviewResult,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    indexSetId: {
      type: String,
      default: "",
    },
    totalFields: {
      type: Array<any>,
      required: true,
    },
  },
  setup(props, { emit }) {
    const initFormData = {
      clustering_fields: "",
      filter_rules: [] as any[],
    };
    let isInit = false;

    const formRules = {
      clustering_fields: [
        {
          required: true,
          trigger: "blur",
        },
      ],
    };

    const { t } = useLocale();
    const store = useStore();

    const previewResultRef = ref();
    const quickClusterFromRef = ref();
    const filterRuleRef = ref();
    const isShowDialog = ref(false);
    const confirmLoading = ref(false);
    const isPreviewed = ref(false);
    const isConfigChanged = ref(false);
    const isRecordEmpty = ref(false);
    const formData = ref(structuredClone(initFormData));

    const clusterField = computed(() =>
      props.totalFields
        .filter((item) => item.is_analyzed)
        .map((el) => {
          const { field_name: id, field_alias: alias } = el;
          return { id, name: alias ? `${id}(${alias})` : id };
        }),
    );

    watch(
      () => props.isShow,
      () => {
        isShowDialog.value = props.isShow;
      },
      {
        immediate: true,
      },
    );

    watch(
      formData,
      () => {
        if (isInit) {
          isInit = false;
          return;
        }
        isConfigChanged.value = true;
        handleSetPreviewWarn();
      },
      { deep: true },
    );

    const handleSetPreviewWarn = () => {
      previewResultRef.value.setWarn(true);
    };

    const handleConfirmSubmit = async () => {
      quickClusterFromRef.value.validate().then(async () => {
        confirmLoading.value = true;
        try {
          const rules = filterRuleRef.value.getValue();
          const data = {
            bk_biz_id: store.state.bkBizId,
            clustering_fields: formData.value.clustering_fields,
            filter_rules: rules.map((item) => ({
              fields_name: item.field_name,
              logic_operator: item.logic_operator,
              op: item.op,
              value: item.value,
            })),
          };
          const result = await $http.request(
            "retrieve/createClusteringConfig",
            {
              params: {
                index_set_id: props.indexSetId,
              },
              data,
            },
          );
          if (result.code === 0) {
            isShowDialog.value = false;
            emit("success");
          }
        } catch (error) {
          console.error(error);
        } finally {
          confirmLoading.value = false;
        }
      });
    };

    const handleOpenDialog = (isOpen: boolean) => {
      if (isOpen) {
        if (clusterField.value[0]?.id) {
          isInit = true;
          formData.value.clustering_fields = clusterField.value[0]?.id || "";
          const targetField = props.totalFields.find(
            (f) => f.field_name === clusterField.value[0]?.id,
          );
          formData.value.filter_rules.push({
            ...targetField,
            op: "contains",
            value: ["ERROR"],
            field_name: targetField.field_name,
          });
        }
      } else {
        formData.value = structuredClone(initFormData);
        emit("close");
      }
    };

    const handlePreviewSuccess = () => {
      isConfigChanged.value = false;
      isPreviewed.value = true;
    };

    const handleBeforeClose = () => {
      handleOpenDialog(false);
    };

    return () => (
      <bk-sideslider
        before-close={handleBeforeClose}
        width={1028}
        ext-cls="cluster-access-slider-main"
        is-show={isShowDialog.value}
        mask-close={false}
        theme="primary"
        title={t("日志聚类接入")}
        on-shown={() => handleOpenDialog(true)}
        on-hidden={() => handleOpenDialog(false)}
      >
        <div slot="content">
          <div class="cluster-access-main">
            <bk-alert
              type="info"
              title={t(
                "大量的日志会导致聚类结果过多，建议使用过滤规则将重要日志进行聚类；如：仅聚类 warn 日志",
              )}
            />
            <bk-form
              ref={quickClusterFromRef}
              form-type="vertical"
              {...{
                props: {
                  model: formData.value,
                  rules: formRules,
                },
              }}
            >
              <bk-form-item
                label={t("聚类字段")}
                property="clustering_fields"
                required
              >
                <div class="setting-item">
                  <bk-select
                    style="width: 482px"
                    value={formData.value.clustering_fields}
                    clearable={false}
                    on-change={(value) =>
                      (formData.value.clustering_fields = value)
                    }
                  >
                    {clusterField.value.map((option) => (
                      <bk-option id={option.id} name={option.name}></bk-option>
                    ))}
                  </bk-select>
                  <span class="field-tip-main">
                    <log-icon common style="color: #979BA5" type="info" />
                    <span class="tip">
                      {t(
                        "只能基于 1 个字段进行聚类，并且字段是为 text 的分词类型，默认为 log 字段",
                      )}
                    </span>
                  </span>
                </div>
              </bk-form-item>
              <bk-form-item label={t("过滤规则")} property="filter_rules">
                <filter-rule
                  ref={filterRuleRef}
                  data={formData.value.filter_rules}
                />
              </bk-form-item>
            </bk-form>
            <PreviewResult
              ref={previewResultRef}
              indexSetId={props.indexSetId}
              ruleList={formData.value.filter_rules}
              class="preview-wraper-main"
              on-preview-success={handlePreviewSuccess}
              on-record-empty={(value) => (isRecordEmpty.value = value)}
            />
          </div>
          <div class="bottom-operate">
            <span
              v-bk-tooltips={{
                placement: "bottom",
                content: !isPreviewed.value
                  ? t("请先完成预览，才可提交")
                  : isConfigChanged.value
                    ? t("配置有更新，请重新预览，才可提交")
                    : t("预览结果无数据，无法提交"),
                disabled:
                  isPreviewed.value &&
                  !isConfigChanged.value &&
                  !isRecordEmpty.value,
              }}
            >
              <bk-button
                theme="primary"
                disabled={
                  !isPreviewed.value ||
                  isConfigChanged.value ||
                  isRecordEmpty.value
                }
                loading={confirmLoading.value}
                on-click={handleConfirmSubmit}
              >
                {t("提交")}
              </bk-button>
            </span>
            <bk-button on-click={() => (isShowDialog.value = false)}>
              {t("取消")}
            </bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  },
});
