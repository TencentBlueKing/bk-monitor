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

import { computed, defineComponent, ref } from "vue";
import TextHighlight from "vue-text-highlight";

import { base64Encode } from "@/common/util";
import useLocale from "@/hooks/use-locale";

import $http from "@/api";
import { type RowData } from "../regex-table";
import CustomHighlight from "./custom-highlight";

import "./index.scss";

export default defineComponent({
  name: "RegexPreview",
  components: {
    TextHighlight,
    CustomHighlight,
  },
  props: {
    log: {
      type: String,
      default: "",
    },
    regexList: {
      type: Array<RowData>,
      default: () => [],
    },
  },
  setup(props, { expose, emit }) {
    const { t } = useLocale();

    const regexPreviewRef = ref(null);
    const effectOriginal = ref("");
    const previewLoading = ref(false);

    const occupyColorMap = computed(() =>
      props.regexList.reduce<Record<string, string>>(
        (map, item) =>
          Object.assign(map, {
            [`#${item.occupy}#`]: item.highlight,
          }),
        {}
      )
    );

    const handleClose = () => {
      emit("close");
    };

    const ruleArrToBase64 = () => {
      try {
        const ruleNewList = props.regexList.reduce<string[]>((list, item) => {
          const rulesStr = JSON.stringify(`${item.occupy}:${item.pattern}`);
          list.push(rulesStr);
          return list;
        }, []);
        const ruleArrStr = `[${ruleNewList.join(" ,")}]`;
        return base64Encode(ruleArrStr);
      } catch (err) {
        console.error(err);
        return "";
      }
    };

    const getHeightLightList = (str: string) => str.match(/#.*?#/g) || [];

    const handleSelfShow = () => {
      effectOriginal.value = "";
      const predefinedVariables = ruleArrToBase64();
      const query = {
        input_data: props.log,
        predefined_varibles: predefinedVariables,
        max_log_length: 10000,
      };
      previewLoading.value = true;
      $http
        .request("/logClustering/debug", { data: { ...query } })
        .then((res) => {
          effectOriginal.value = res.data;
        })
        .finally(() => {
          previewLoading.value = false;
        });
    };

    expose({
      getRef: () => regexPreviewRef.value,
      onShow: handleSelfShow,
    });

    return () => (
      <div style="display:none">
        <div ref={regexPreviewRef} class="regex-preview-main">
          <div class="header-main">
            <div class="title-main">{t("预览结果")}</div>
            <div class="close-main" on-click={handleClose}>
              <log-icon type="close" />
            </div>
          </div>
          <div
            class="preview-main"
            v-bkloading={{ isLoading: previewLoading.value }}
          >
            <text-highlight
              style="word-break: break-all"
              colorMap={occupyColorMap.value}
              highlightComponent={CustomHighlight}
              queries={getHeightLightList(effectOriginal.value)}
            >
              {effectOriginal.value}
            </text-highlight>
          </div>
        </div>
      </div>
    );
  },
});
