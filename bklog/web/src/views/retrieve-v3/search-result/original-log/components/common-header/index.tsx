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

import { defineComponent, ref, computed } from "vue";
import useLocale from "@/hooks/use-locale";

import "./index.scss";

export default defineComponent({
  name: "CommonHeader",
  props: {
    targetFields: {
      type: Array,
      default: () => [],
    },
    paramsInfo: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useLocale();

    const getTargetFieldsStr = computed(() =>
      props.targetFields.reduce((acc, cur) => {
        acc += `${cur}: ${props.paramsInfo[cur as string] || "/ "} `;
        return acc;
      }, "")
    );

    return () => (
      <div class="common-header-main">
        <span class="dialog-title">{t("上下文")}</span>
        {!props.targetFields.length ? (
          <div class="subtitle-list-main title-overflow">
            <div class="subtitle-main">
              <div class="title">IP： </div>
              <div class="content title-overflow">
                {props.paramsInfo.ip || props.paramsInfo.serverIp}
              </div>
            </div>
            <div class="subtitle-main">
              <div class="title">{t("日志路径")}： </div>
              <div class="content title-overflow" v-bk-overflow-tips>
                {props.paramsInfo.path || props.paramsInfo.logfile}
              </div>
            </div>
          </div>
        ) : (
          <div
            class="subtitle-list-main title-overflow"
            v-bk-tooltips={{
              content: getTargetFieldsStr.value,
              placement: "bottom",
            }}
          >
            {props.targetFields.map((item, index) => (
              <div class="subtitle-main" key={index}>
                <div class="title">{item}：</div>
                <div class="content title-overflow">
                  {props.paramsInfo[item as string] || "/"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  },
});
