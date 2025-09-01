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
import useStore from "@/hooks/use-store";
import useLocale from "@/hooks/use-locale";
import $http from "@/api";
import CreateTemplate from "./create-template";
import TemplateItem from "./template-item";
import { base64ToRuleArr } from "../../log-clustering/top-operation/cluster-config/edit-config/rule-operate/util";
import { type IResponseData } from "@/services/type";
import { type RuleTemplate } from "@/services/log-clustering";
import { type TemplateItem as TemplateItemType } from "../index";

import "./index.scss";

export default defineComponent({
  name: "TemplateManage",
  components: {
    CreateTemplate,
    TemplateItem,
  },
  props: {
    defaultId: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const currentTemplateIndex = ref(0);
    const searchValue = ref("");
    const templateList = ref<TemplateItemType[]>([]);

    const spaceUid = computed(() => store.state.spaceUid);
    const currentTemplate = computed(
      () => templateList.value[currentTemplateIndex.value],
    );

    let localTemplateList: TemplateItemType[] = [];
    let initDefaultSelect = false;

    watch(
      currentTemplate,
      () => {
        if (!currentTemplate.value) {
          return;
        }

        emit("choose-template", currentTemplate.value);
      },
      {
        immediate: true,
      },
    );

    const handleSearch = () => {
      if (!searchValue.value) {
        templateList.value = structuredClone(localTemplateList);
        return;
      }

      const searchRegExp = new RegExp(searchValue.value, "i");
      templateList.value = localTemplateList.filter((item) =>
        searchRegExp.test(item.template_name),
      );
    };

    /** 初始化模板列表 */
    const initTemplateList = async () => {
      const res = (await $http.request("logClustering/ruleTemplate", {
        params: {
          space_uid: spaceUid.value,
        },
      })) as IResponseData<RuleTemplate[]>;
      templateList.value = res.data.map((item) => ({
        ...item,
        ruleList: base64ToRuleArr(item.predefined_varibles),
      }));
      localTemplateList = structuredClone(templateList.value);
      if (props.defaultId && !initDefaultSelect) {
        initDefaultSelect = true;
        currentTemplateIndex.value = res.data.findIndex(
          (item) => item.id === props.defaultId,
        );
      }
    };

    const handleClickTemplateItem = (index: number) => {
      currentTemplateIndex.value = index;
    };

    const handleCreateTemplateSuccess = (id: number) => {
      initTemplateList().then(() => {
        currentTemplateIndex.value = templateList.value.findIndex(
          (item) => item.id === id,
        );
      });
    };

    initTemplateList();

    expose({
      refresh: async () => {
        await initTemplateList();
        nextTick(() => {
          emit("choose-template", currentTemplate.value);
        });
      },
    });

    return () => (
      <div class="template-list-main">
        <div class="search-main">
          <CreateTemplate on-success={handleCreateTemplateSuccess} />
          <bk-input
            clearable
            style="width: 168px"
            placeholder={t("搜索 模板名称")}
            right-icon="bk-icon icon-search"
            value={searchValue.value}
            on-change={(value) => (searchValue.value = value)}
            on-enter={handleSearch}
            on-clear={handleSearch}
            on-right-icon-click={handleSearch}
          />
        </div>
        <div class="template-list">
          {templateList.value.length > 0 ? (
            templateList.value.map((item, index) => (
              <template-item
                data={item}
                is-active={currentTemplateIndex.value === index}
                on-click={() => handleClickTemplateItem(index)}
                on-refresh={initTemplateList}
              />
            ))
          ) : (
            <div class="empty-main">
              {searchValue.value ? (
                <bk-exception type="search-empty" scene="part">
                  <span style="font-size:12px">{t("搜索为空")}</span>
                </bk-exception>
              ) : (
                <bk-exception type="empty" scene="part">
                  <span style="font-size:12px">{t("暂无数据")}，</span>
                </bk-exception>
              )}
            </div>
          )}
        </div>
      </div>
    );
  },
});
