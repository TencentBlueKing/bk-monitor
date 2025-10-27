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

import { defineComponent, onMounted, ref } from "vue";

import OtherImport from "@/components/import-from-other-index-set";
import RuleConfigOperate from "@/components/rule-config-operate";
import RuleTable from "@/components/rule-table";
import useLocale from "@/hooks/use-locale";
import { type RuleTemplate } from "@/services/log-clustering";
import { bkMessage } from "bk-magic-vue";
import dayjs from "dayjs";
import { useRoute, useRouter } from "vue-router/composables";

import $http from "@/api";
import CreateTemplate from "./create-template";
import IndexSetList from "./index-set-list";
import TemplateList from "./template-list";

import "./index.scss";

export type TemplateItem = RuleTemplate & { ruleList: Record<string, any>[] };

export default defineComponent({
  name: "TemplateManage",
  components: {
    CreateTemplate,
    RuleConfigOperate,
    RuleTable,
    OtherImport,
    IndexSetList,
    TemplateList,
  },
  setup() {
    const { t } = useLocale();
    const route = useRoute();
    const router = useRouter();

    const templateListRef = ref<any>(null);
    const ruleConfigOperateRef = ref<any>(null);
    const ruleTableRef = ref<any>(null);
    const isShowOtherImport = ref(false);
    const searchPlaceholderValue = ref("");
    const currentRuleList = ref<TemplateItem["ruleList"]>([]);
    const currentTemplate = ref<TemplateItem>();

    const { collectorConfigId, templateId } = route.query;

    let inputDocument: HTMLInputElement;

    const handleChooseTemplate = (item: TemplateItem) => {
      currentTemplate.value = item;
      currentRuleList.value = item.ruleList;
    };

    const inputFileEvent = () => {
      // 检查文件是否选择:
      if (!inputDocument.value) return;
      const file = inputDocument.files![0];
      // 读取文件:
      const reader = new FileReader();
      reader.onload = (e: any) => {
        try {
          const list = Object.values(JSON.parse(e.target.result)).map(
            (item: any, index: number) => {
              if (!item.placeholder || !String(item.rule))
                throw new Error("无效的json");
              return {
                [item.placeholder]: String([item.rule]),
                __Index__: index,
              };
            }
          );
          currentRuleList.value = list;
        } catch (err) {
          console.error(err);
          bkMessage({
            theme: "error",
            message: t("不是有效的json文件"),
          });
        }
      };
      // 以Text的形式读取文件:
      reader.readAsText(file);
    };

    const handleSearchPlaceholder = () => {
      ruleTableRef.value.search(searchPlaceholderValue.value);
    };

    const handleReset = () => {
      currentRuleList.value = currentTemplate.value!.ruleList;
    };

    /** 导出规则 */
    const handleExportRule = () => {
      const ruleList = ruleTableRef.value.getRuleList();
      if (!ruleList.length) {
        bkMessage({
          theme: "error",
          message: t("聚类规则为空，无法导出规则"),
        });
        return;
      }
      const eleLink = document.createElement("a");
      const time = `${dayjs().format("YYYYMMDDHHmmss")}`;
      eleLink.download = `bk_log_search_download_${time}.json`;
      eleLink.style.display = "none";
      const jsonStr = ruleList.reduce((pre, cur, index) => {
        const entriesArr = Object.entries(cur);
        pre[index] = {
          placeholder: entriesArr[0][0],
          rule: entriesArr[0][1],
        };
        return pre;
      }, {});
      // 字符内容转变成blob地址
      const blob = new Blob([JSON.stringify(jsonStr, null, 4)]);
      eleLink.href = URL.createObjectURL(blob);
      // 触发点击
      document.body.appendChild(eleLink);
      eleLink.click();
      document.body.removeChild(eleLink);
    };

    const initInputType = () => {
      const uploadEl = document.createElement("input");
      uploadEl.type = "file";
      uploadEl.style.display = "none";
      uploadEl.addEventListener("change", inputFileEvent);
      inputDocument = uploadEl;
    };

    const handleConfirmFromOtherIndexSet = (list: any) => {
      currentRuleList.value = list;
    };

    const handleClickRouteBack = () => {
      router.push({
        name: "retrieve",
        query: {
          tab: "clustering",
        },
      });
    };

    const handleSubmit = () => {
      $http
        .request("logClustering/updateTemplateName", {
          params: {
            regex_template_id: currentTemplate.value?.id,
          },
          data: {
            predefined_varibles: ruleTableRef.value.getRuleListBase64(),
            template_name: currentTemplate.value?.template_name,
          },
        })
        .then((res) => {
          if (res.code === 0) {
            bkMessage({
              message: t("更新成功"),
              theme: "success",
            });
            handleTemplateListRefresh();
          }
        })
        .catch((err) => {
          console.error(err);
        })
        .finally(() => {
          ruleConfigOperateRef.value?.setSaveLoading(false);
        });
    };

    const handleTemplateListRefresh = () => {
      templateListRef.value.refresh();
    };

    onMounted(() => {
      initInputType();
    });

    return () => (
      <div class="retrieve-template-manage-page">
        <div class="header-main">
          <span on-click={handleClickRouteBack}>
            <log-icon class="back-icon" type="arrows-left" common />
          </span>
          <span class="title">{t("模板管理")}</span>
        </div>
        <div class="content-main">
          <TemplateList
            ref={templateListRef}
            defaultId={Number(templateId)}
            on-choose-template={handleChooseTemplate}
          />
          <div class="config-main">
            <div class="template-config-main">
              <div class="rule-config-main">
                <div class="config-title">
                  <div class="title">{t("模板配置")}</div>
                  <div class="split-line"></div>
                  <div class="template-name">
                    {currentTemplate.value?.template_name}
                  </div>
                </div>
                <div class="rule-operate-main">
                  <div class="operate-btns">
                    <bk-dropdown-menu>
                      <div slot="dropdown-trigger">
                        <bk-button
                          class="operate-btn"
                          data-test-id="LogCluster_button_addNewRules"
                        >
                          {t("导入")}
                        </bk-button>
                      </div>
                      <ul class="bk-dropdown-list" slot="dropdown-content">
                        <li>
                          <a
                            href="javascript:;"
                            on-click={() => inputDocument.click()}
                          >
                            {t("本地导入")}
                          </a>
                        </li>
                        <li>
                          <a
                            href="javascript:;"
                            on-click={() => (isShowOtherImport.value = true)}
                          >
                            {t("其他索引集导入")}
                          </a>
                        </li>
                      </ul>
                    </bk-dropdown-menu>
                    <bk-button class="operate-btn" on-click={handleExportRule}>
                      {t("导出")}
                    </bk-button>
                  </div>
                  <bk-input
                    style="width: 480px"
                    placeholder={t("搜索 占位符")}
                    right-icon="bk-icon icon-search"
                    value={searchPlaceholderValue.value}
                    clearable
                    on-change={(value) =>
                      (searchPlaceholderValue.value = value)
                    }
                    on-clear={handleSearchPlaceholder}
                    on-enter={handleSearchPlaceholder}
                    on-right-icon-click={handleSearchPlaceholder}
                  />
                </div>
                <rule-table
                  ref={ruleTableRef}
                  ruleList={currentRuleList.value}
                  on-rule-list-change={(list) => (currentRuleList.value = list)}
                />
              </div>
              <index-set-list
                list={currentTemplate.value?.related_index_set_list}
                on-refresh={handleTemplateListRefresh}
              />
            </div>
            <rule-config-operate
              ref={ruleConfigOperateRef}
              collectorConfigId={collectorConfigId}
              ruleList={currentRuleList.value}
              on-reset={handleReset}
              on-submit={handleSubmit}
            />
          </div>
        </div>
        <other-import
          isShow={isShowOtherImport.value}
          on-show-change={(value) => (isShowOtherImport.value = value)}
          on-success={handleConfirmFromOtherIndexSet}
        />
      </div>
    );
  },
});
