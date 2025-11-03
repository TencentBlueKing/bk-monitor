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

import { computed, defineComponent, PropType } from "vue";
import useLocale from "@/hooks/use-locale";
import { type TemplateItem } from "../index";
import "./index.scss";

export default defineComponent({
  name: "IndexSetList",
  props: {
    list: {
      type: Array as PropType<TemplateItem["related_index_set_list"]>,
      default: () => [],
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const showList = computed(() => props.list.length > 0);

    const openLinkUrl = (indexId: number) => {
      const url = new URL(window.location.href);
      const hostname = url.hostname;
      window.open(`https://${hostname}#/retrieve/${indexId}`);
    };

    const handleRefresh = () => {
      emit("refresh");
    };

    return () => (
      <div class="index-set-list-main">
        <div class="title-main">
          <div class="title">{t("索引集列表")}</div>
          {showList.value && (
            <div class="refresh-main" on-click={handleRefresh}>
              <log-icon type="log-refresh" />
            </div>
          )}
        </div>
        {showList.value ? (
          <div class="list-main">
            {props.list.map((item) => (
              <div class="item-main">
                <div class="item-title" v-bk-overflow-tips>
                  {item.index_set_name}
                </div>
                <span on-click={() => openLinkUrl(item.index_set_id)}>
                  <log-icon class="link-icon" type="tiaozhuan" />
                </span>
              </div>
            ))}
          </div>
        ) : (
          <bk-exception type="empty" ext-cls="empty-tip-main">
            <span style="font-size:12px">{t("暂无使用该模板的索引集")}</span>
          </bk-exception>
        )}
      </div>
    );
  },
});
