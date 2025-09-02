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

import { computed, defineComponent, ref, nextTick, watch } from "vue";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import tippy from "tippy.js";
import RegexTable, { type RowData } from "./regex-table";
import { bkMessage } from "bk-magic-vue";
import $http from "@/api";
import OccupyInput from "./occupy-input";
import RegexPreview from "./regex-preview";
import SecondConfirm from "./second-confirm";
import { type ConfigInfo } from "@/services/log-clustering";
import { type IResponseData } from "@/services/type";
import { base64Encode } from "@/common/util";
import { base64ToRuleList } from "@/utils";

import "./index.scss";

export default defineComponent({
  name: "RegexMatch",
  components: {
    RegexTable,
    OccupyInput,
    RegexPreview,
    SecondConfirm,
  },
  props: {
    sampleStr: {
      type: String,
      default: "",
    },
    value: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const previewBtnRef = ref<HTMLElement>();
    const secondConfirmRef = ref<any>(null);
    const confirmBtnRef = ref<HTMLElement>();
    const logSampleRef = ref<HTMLElement>();
    const regexPreviewRef = ref<any>(null);
    const tableRef = ref<any>(null);
    const occupyRef = ref<any>(null);
    const isShowRuleDialog = ref(false);
    const isConfigChanged = ref(false);
    const isConfirmLoading = ref(false);
    const regexList = ref<RowData[]>([]);

    const indexSetItem = computed(() => store.state.indexItem.items[0]);
    const configId = computed(
      () =>
        store.state.indexSetFieldConfig.clean_config?.extra.collector_config_id
    );
    // 选中的划词
    let occupyOriginStr = "";
    let occupyPopoverInstance: any = null;
    let regexPreviewPopoverInstance: any = null;
    let secondConfirmPopoverInstance: any = null;
    let currentChoosedTextBackgroundColor = "";
    let logConfigInfo = {
      id: 0,
      type: "",
    };
    let highlightColorIndex = 0;

    const defaultHighlightColorList = [
      "rgb(255, 235, 204)",
      "rgb(206, 235, 222)",
      "rgb(215, 235, 245)",
      "rgb(224, 229, 255)",
      "rgb(249, 219, 255)",
      "rgb(255, 224, 230)",
      "rgb(226, 240, 211)",
      "rgb(235, 221, 192)",
      "rgb(188, 214, 206)",
      "rgb(187, 207, 227)",
      "rgb(193, 193, 239)",
      "rgb(224, 195, 224)",
      "rgb(239, 193, 193)",
      "rgb(199, 215, 190)",
      "rgb(247, 208, 148)",
      "rgb(155, 223, 191)",
      "rgb(177, 225, 249)",
      "rgb(172, 177, 255)",
      "rgb(242, 174, 255)",
      "rgb(255, 171, 185)",
      "rgb(192, 240, 137)",
    ];

    watch(
      () => props.value,
      () => {
        if (props.value) {
          isShowRuleDialog.value = true;
        }
      }
    );

    // 数据指纹请求
    const requestCluster = async (isDefault = false) => {
      try {
        const params = {
          index_set_id: props.indexId,
        };
        const data = { collector_config_id: configId.value };
        const baseUrl = "/logClustering";
        const requestBehindUrl = isDefault ? "/getDefaultConfig" : "/getConfig";
        const requestUrl = `${baseUrl}${requestBehindUrl}`;
        const res = (await $http.request(
          requestUrl,
          !isDefault && { params, data }
        )) as IResponseData<ConfigInfo>;
        const { regex_rule_type, regex_template_id, predefined_varibles } =
          res.data;
        const ruleList = base64ToRuleList(predefined_varibles);
        const tableList = ruleList.map((item) => {
          const key = Object.keys(item)[0];
          const value = item[key];
          return {
            pattern: value,
            occupy: key,
            occupyOriginStr: "",
            highlight: "#e6e9f0",
            disabled: true,
          };
        });
        regexList.value = tableList;
        tableRef.value.setDataList(tableList);
        logConfigInfo = {
          id: regex_template_id,
          type: regex_rule_type,
        };
      } catch (e) {
        console.warn(e);
      } finally {
      }
    };

    const handleCancel = () => {
      isShowRuleDialog.value = false;
      emit("change", false);
    };

    const handleConfirm = () => {
      tableRef.value
        .getData()
        .then((data) => {
          isConfirmLoading.value = true;
          if (logConfigInfo.type === "template") {
            secondConfirmPopoverInstance = tippy(confirmBtnRef.value!, {
              appendTo: () => document.body,
              content: secondConfirmRef.value.getRef(),
              maxWidth: 360,
              arrow: true,
              trigger: "manual",
              theme: "light second-confirm-popover",
              placement: "bottom-start",
              hideOnClick: false,
              interactive: true,
              allowHTML: true,
            });
            secondConfirmPopoverInstance.show();
          } else {
            // 直接调用更新聚类配置接口
            const predefinedVaribles = tableArrToBase64(data);
            updateLogConfig("customize", predefinedVaribles);
          }
        })
        .catch((e) => {
          console.error(e);
        });
    };

    const destroyOccupyPopover = () => {
      occupyOriginStr = "";
      occupyRef.value.close();
      occupyPopoverInstance?.hide();
      occupyPopoverInstance?.destroy();
      occupyPopoverInstance = null;
    };

    const handleMouseUpSample = () => {
      const selection = window.getSelection()!;
      const selectedText = selection.toString();
      if (selectedText) {
        const range = selection.getRangeAt(0);
        const wrapper = document.createElement("span");
        wrapper.classList.add("choosed-wrapper");
        currentChoosedTextBackgroundColor = getHighlightColor();
        wrapper.style.background = currentChoosedTextBackgroundColor;
        wrapper.appendChild(range.extractContents());
        range.insertNode(wrapper);
        selection.removeAllRanges();
        nextTick(() => {
          wrapper.addEventListener("popoverShowEvent", (e) =>
            occupyTargetEvent(e, wrapper)
          );
          wrapper.dispatchEvent(new Event("popoverShowEvent"));
        });
      }
    };

    const occupyTargetEvent = (e: Event, wrapper: HTMLSpanElement) => {
      destroyOccupyPopover();
      occupyPopoverInstance = tippy(e.target as Element, {
        appendTo: () => document.body,
        content: occupyRef.value.getRef(),
        arrow: true,
        trigger: "manual",
        theme: "light",
        placement: "bottom-start",
        hideOnClick: false,
        interactive: true,
        allowHTML: true,
      });
      occupyOriginStr = wrapper.innerText;
      occupyPopoverInstance.show();
    };

    const getRandomColor = (alpha = 0.3) => {
      const r = Math.floor(Math.random() * 256);
      const g = Math.floor(Math.random() * 256);
      const b = Math.floor(Math.random() * 256);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    };

    const getHighlightColor = () => {
      if (highlightColorIndex >= defaultHighlightColorList.length) {
        return getRandomColor();
      }

      return defaultHighlightColorList[highlightColorIndex++];
    };

    const handleSubmitOccupy = (inputValue: string) => {
      tableRef.value.addItem({
        pattern: "",
        occupy: inputValue,
        occupyOriginStr: occupyOriginStr,
        highlight: currentChoosedTextBackgroundColor,
      });
      destroyOccupyPopover();
    };

    const getChoosedTextDomList = () => {
      const doms = logSampleRef.value!.querySelectorAll(".choosed-wrapper");
      return Array.from(doms) as HTMLElement[];
    };

    const handleCancelOccupy = () => {
      const choosedSpanList = getChoosedTextDomList();
      const removeDom = choosedSpanList.find(
        (node) => node.style.background === currentChoosedTextBackgroundColor
      );
      if (removeDom) {
        const textNode = document.createTextNode(removeDom.innerText);
        removeDom.replaceWith(textNode);
      }
      occupyPopoverInstance.hide();
    };

    const handleDeleteRow = (row: RowData) => {
      const choosedSpanList = getChoosedTextDomList();
      const removeDom = choosedSpanList.find(
        (node) => node.style.background === row.highlight
      );
      if (removeDom) {
        const textNode = document.createTextNode(removeDom.innerText);
        removeDom.replaceWith(textNode);
      }
    };

    const handleClickPreview = () => {
      tableRef.value
        .getData()
        .then(() => {
          isConfigChanged.value = false;
          regexPreviewPopoverInstance = tippy(previewBtnRef.value!, {
            appendTo: () => document.body,
            content: regexPreviewRef.value.getRef(),
            maxWidth: 962,
            arrow: true,
            trigger: "manual",
            theme: "light",
            placement: "bottom-start",
            hideOnClick: false,
            interactive: true,
            allowHTML: true,
            offset: [170, 20],
          });
          regexPreviewPopoverInstance.show();
          regexPreviewRef.value.onShow();
        })
        .catch((err) => {
          console.error(err);
        });
    };

    const handleCloseRegexPreview = () => {
      regexPreviewPopoverInstance?.hide();
    };

    const handleRegexTableChange = (list: RowData[]) => {
      regexList.value = list;
      isConfigChanged.value = true;
      regexPreviewPopoverInstance?.hide();
    };

    const handleDialogChangeShow = (isShow: boolean) => {
      if (isShow) {
        requestCluster();
      } else {
        highlightColorIndex = 0;
        destroyOccupyPopover();
        handleCloseRegexPreview();
        handleCancel();
      }
    };

    const handleCloseSecondConfirm = () => {
      secondConfirmPopoverInstance?.hide();
      isConfirmLoading.value = false;
    };

    const tableArrToBase64 = (dataList: RowData[]) => {
      try {
        const ruleList = dataList.reduce<string[]>((pre, cur) => {
          const key = cur.occupy;
          const val = cur.pattern;
          const rulesStr = JSON.stringify(`${key}:${val}`);
          pre.push(rulesStr);
          return pre;
        }, []);
        const ruleArrStr = `[${ruleList.join(" ,")}]`;
        return base64Encode(ruleArrStr);
      } catch (error) {
        console.error(error);
        return "";
      }
    };

    const updateLogConfig = (type: string, predefinedVaribles: string) => {
      const { index_set_id, bk_biz_id } = indexSetItem.value;
      $http
        .request("retrieve/updateClusteringConfig", {
          params: {
            index_set_id,
          },
          data: {
            predefined_varibles: predefinedVaribles,
            regex_rule_type: type,
            regex_template_id: logConfigInfo.id,
            signature_enable: true,
            collector_config_id: configId.value,
            index_set_id,
            bk_biz_id,
          },
        })
        .then((res) => {
          if (res.code === 0) {
            bkMessage({
              message: t("更新成功"),
              theme: "success",
            });
            handleConfirmSuccess();
          }
        });
    };

    const handleConfirmSuccess = () => {
      isConfirmLoading.value = false;
      secondConfirmRef.value.close();
      secondConfirmPopoverInstance?.hide();
      handleCancel();
    };

    const updateTemplate = (predefinedVaribles: string) => {
      $http
        .request("logClustering/updateTemplateName", {
          params: {
            regex_template_id: logConfigInfo.id,
          },
          data: {
            predefined_varibles: predefinedVaribles,
          },
        })
        .then((res) => {
          if (res.code === 0) {
            bkMessage({
              message: t("更新成功"),
              theme: "success",
            });
            handleConfirmSuccess();
          }
        })
        .catch((err) => {
          console.error(err);
        });
    };

    const handleConfirmSecond = (type: string) => {
      tableRef.value
        .getData()
        .then((data: RowData[]) => {
          const predefinedVaribles = tableArrToBase64(data);
          if (type === "sync") {
            // 同步更新模板
            updateTemplate(predefinedVaribles);
          } else {
            // 与模板解除绑定
            updateLogConfig("customize", predefinedVaribles);
          }
        })
        .catch((e) => {
          console.error(e);
        });
    };

    return () => (
      <div>
        <bk-dialog
          width={960}
          mask-close={false}
          render-directive="if"
          ext-cls="regex-match-dialog-main"
          value={isShowRuleDialog.value}
          header-position="left"
          on-value-change={handleDialogChangeShow}
          title={t("正则匹配")}
        >
          <div class="sample-box">
            <div class="title">{t("日志样例")}</div>
            <bk-alert
              type="info"
              title={t("鼠标左键框选字段，可提取并生成正则表达式。")}
            />
            <div
              ref={logSampleRef}
              class="sample-content"
              onMouseup={handleMouseUpSample}
            >
              {props.sampleStr}
            </div>
            {regexList.value.length > 0 && (
              <div class="title" style="margin-top: 20px;">
                {t("正则")}
              </div>
            )}
            <regex-table
              style={{ display: regexList.value.length > 0 ? "block" : "none" }}
              ref={tableRef}
              on-delete={handleDeleteRow}
              on-change={handleRegexTableChange}
              on-open-cluster-config={() => emit("open-cluster-config")}
            />
          </div>
          <div slot="footer" class="bottom-operations">
            {isConfigChanged.value && regexList.value.length > 0 && (
              <div class="tips-main">
                <log-icon type="circle-alert-filled" class="tip-icon" />
                <span class="tips-text">
                  {t("配置有变更，请重新点击“预览”")}
                </span>
              </div>
            )}
            <span ref={previewBtnRef}>
              <bk-button
                theme="primary"
                outline
                size="small"
                disabled={!regexList.value.length}
                on-click={handleClickPreview}
              >
                {t("预览")}
              </bk-button>
            </span>
            <span ref={confirmBtnRef}>
              <bk-button
                theme="primary"
                size="small"
                disabled={!regexList.value.length}
                loading={isConfirmLoading.value}
                on-click={handleConfirm}
              >
                {t("确定")}
              </bk-button>
            </span>
            <bk-button size="small" on-click={handleCancel}>
              {t("取消")}
            </bk-button>
          </div>
        </bk-dialog>
        <OccupyInput
          ref={occupyRef}
          on-cancel={handleCancelOccupy}
          on-submit={handleSubmitOccupy}
        />
        <RegexPreview
          ref={regexPreviewRef}
          regexList={regexList.value}
          log={props.sampleStr}
          on-close={handleCloseRegexPreview}
        />
        <SecondConfirm
          ref={secondConfirmRef}
          on-confirm={handleConfirmSecond}
          on-cancel={handleCloseSecondConfirm}
        />
      </div>
    );
  },
});
