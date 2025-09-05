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

import "./index.scss";

export default defineComponent({
  name: "TemporaryGroup",
  props: {
    fingerOperateData: {
      type: Object,
      require: true,
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const popoverRef = ref(null);
    const group = ref<string[]>([]);
    const isShowPopoverInstance = ref(false);
    const tippyOptions = ref({
      theme: "light",
      trigger: "manual",
      hideOnClick: false,
      offset: "16",
      interactive: true,
    });

    const groupList = computed(() =>
      props.fingerOperateData.groupList.filter(
        (item) =>
          !props.fingerOperateData.dimensionList.includes(item.id) &&
          !["dtEventTimeStamp", "time", "iterationIndex", "gseIndex"].includes(
            item.id
          )
      )
    );

    watch(
      () => props.fingerOperateData,
      () => {
        initLocalValue();
      },
      {
        deep: true,
      }
    );

    const closePopover = () => {
      isShowPopoverInstance.value = false;
      popoverRef.value.instance.hide();
    };

    const handleConfirm = () => {
      emit("handle-finger-operate", "fingerOperateData", {
        selectGroupList: group.value,
      });
      emit(
        "handle-finger-operate",
        "requestData",
        {
          group_by: [...group.value],
        },
        true
      );
      closePopover();
    };

    const initLocalValue = () => {
      const finger = props.fingerOperateData;
      group.value = finger.selectGroupList;
    };

    const handleShowPopover = () => {
      emit("click-trigger");
      if (!isShowPopoverInstance.value) {
        popoverRef.value.instance.show();
      } else {
        popoverRef.value.instance.hide();
      }
      isShowPopoverInstance.value = !isShowPopoverInstance.value;
    };

    expose({
      getValue: () => group.value,
      hide: () => {
        popoverRef.value.instance.hide();
        isShowPopoverInstance.value = false;
      },
      show: () => {
        popoverRef.value.instance.show();
        isShowPopoverInstance.value = true;
      },
    });

    return () => (
      <bk-popover
        ref={popoverRef}
        width={400}
        disabled={!props.clusterSwitch}
        on-show={initLocalValue}
        tippy-options={tippyOptions.value}
        placement="bottom-start"
      >
        <div class="quick-filter-trigger-main" on-click={handleShowPopover}>
          <log-icon type="group" class="trigger-icon" />
          <span>{t("临时分组")}</span>
        </div>
        <div slot="content">
          <div class="temporary-group-popover ">
            <div class="title-main">{t("临时分组")}</div>
            <bk-alert type="info" style="color: #4D4F56">
              <div slot="title">
                <i18n path="满足临时的分组需求，刷新不会保存（如需固化下来，请使用“{0}”功能)">
                  <bk-button
                    text
                    theme="primary"
                    style="font-size: 12px"
                    on-click={() => emit("open-dimension-split")}
                  >
                    {t("维度拆分")}
                  </bk-button>
                </i18n>
              </div>
            </bk-alert>
            <div class="piece-item">
              <span class="title">{t("分组")}</span>
              <bk-select
                value={group.value}
                scroll-height={140}
                ext-popover-cls="quick-filter-selected-ext"
                display-tag
                multiple
                searchable
                on-change={(val) => (group.value = val)}
              >
                {groupList.value.map((option) => (
                  <bk-option id={option.id} key={option.id} name={option.name}>
                    <bk-checkbox
                      checked={group.value.includes(option.id)}
                      title={option.name}
                    >
                      {option.name}
                    </bk-checkbox>
                  </bk-option>
                ))}
              </bk-select>
            </div>
            <div class="popover-button">
              <bk-button
                style="margin-right: 8px"
                size="small"
                theme="primary"
                on-click={handleConfirm}
              >
                {t("确定")}
              </bk-button>
              <bk-button size="small" theme="default" on-click={closePopover}>
                {t("取消")}
              </bk-button>
            </div>
          </div>
        </div>
      </bk-popover>
    );
  },
});
