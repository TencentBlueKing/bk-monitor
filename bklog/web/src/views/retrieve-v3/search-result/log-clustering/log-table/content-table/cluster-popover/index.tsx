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

import { defineComponent, ref, PropType } from "vue";
import useLocale from "@/hooks/use-locale";
import tippy from "tippy.js";
import RegexMatchDialog from "./regex-match";
import { copyMessage } from "@/common/util";
import { type LogPattern } from "@/services/log-clustering";
import "./index.scss";

export default defineComponent({
  name: "ClusterPopover",
  components: {
    RegexMatchDialog,
  },
  props: {
    rowData: {
      type: Object as PropType<LogPattern>,
      default: () => ({}),
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { slots, emit }) {
    const { t } = useLocale();
    const eventTippyRef = ref<HTMLElement>();

    const isShowRuleDialog = ref(false);
    let popoverInstance: any = null;
    let intersectionObserver: any = null;

    const handleClickPattern = (e: Event) => {
      destroyPopover();
      popoverInstance = tippy(e.target as Element, {
        appendTo: () => document.body,
        content: eventTippyRef.value,
        arrow: true,
        trigger: "click",
        theme: "light",
        placement: "bottom",
        interactive: true,
        allowHTML: true,
        onShow: handlePopoverShow,
        onHidden: handlePopoverHide,
      });
      popoverInstance.show(500);
    };

    const handleShowRegexDialog = () => {
      destroyPopover();
      isShowRuleDialog.value = true;
    };

    const destroyPopover = () => {
      popoverInstance?.hide();
      popoverInstance?.destroy();
      popoverInstance = null;
    };

    const handleCopy = () => {
      copyMessage(props.rowData.pattern);
    };

    const handleClick = (isLink = false) => {
      destroyPopover();
      emit("event-click", isLink);
    };

    const unregisterOberver = () => {
      if (intersectionObserver) {
        intersectionObserver.unobserve(eventTippyRef.value);
        intersectionObserver.disconnect();
        intersectionObserver = null;
      }
    };
    // 注册Intersection监听
    const registerObserver = () => {
      if (intersectionObserver) {
        unregisterOberver();
      }
      intersectionObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (intersectionObserver) {
            if (entry.intersectionRatio <= 0) {
              destroyPopover();
            }
          }
        });
      });
      intersectionObserver.observe(eventTippyRef.value);
    };

    const handlePopoverShow = () => {
      setTimeout(registerObserver, 20);
    };

    const handlePopoverHide = () => {
      unregisterOberver();
    };

    const popoverSlot = () => (
      <div style={{ display: "none" }}>
        <div ref={eventTippyRef} class="pattern-event-tippy">
          <div class="event-icons">
            <div class="event-box">
              <span class="event-btn" onClick={handleCopy}>
                <log-icon type="copy" class="icon copy-icon" />
                <span>{t("复制")}</span>
              </span>
            </div>
            <div class="event-box" on-click={handleShowRegexDialog}>
              <span class="event-btn">
                <log-icon type="zhengze" class="icon" />
                <span>{t("正则匹配")}</span>
              </span>
            </div>
            <div class="event-box">
              <span class="event-btn" onClick={() => handleClick(true)}>
                <log-icon type="audit" class="icon" />
                <span>{t("查询命中pattern的日志")}</span>
              </span>
              <div
                class="new-link"
                v-bk-tooltips={t("新开标签页")}
                onClick={(e) => {
                  e.stopPropagation();
                  handleClick(true);
                }}
              >
                <i class="bklog-icon bklog-jump"></i>
              </div>
            </div>
          </div>
        </div>
      </div>
    );

    return () => (
      <div class="pattern-line" onClick={handleClickPattern}>
        {slots.default?.()}
        {popoverSlot()}
        <RegexMatchDialog
          sampleStr={props.rowData.origin_log}
          indexId={props.indexId}
          value={isShowRuleDialog.value}
          on-change={(value) => (isShowRuleDialog.value = value)}
          on-open-cluster-config={() => emit("open-cluster-config")}
        />
      </div>
    );
  },
});
