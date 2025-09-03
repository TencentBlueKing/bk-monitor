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

import { defineComponent, ref } from "vue";
import useLocale from "@/hooks/use-locale";
import "./index.scss";

export default defineComponent({
  name: "FilterOperate",
  props: {
    list: {
      type: Array<{
        id: number;
        name: string;
      }>,
      default: () => [],
    },
    searchable: {
      type: Boolean,
      default: true,
    },
    multiple: {
      type: Boolean,
      default: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const selectRef = ref<any>(null);
    const localValue = ref<number[]>([]);

    const handleConfirm = () => {
      emit("confirm", localValue.value);
      selectRef.value?.close();
    };

    const handleReset = () => {
      localValue.value = [];
      emit("confirm", []);
      selectRef.value?.close();
    };

    const handleSelectChange = (list: number[]) => {
      if (props.multiple) {
        localValue.value = list;
        return;
      }
      if (list.length > 1) {
        localValue.value = [list[list.length - 1]];
      } else {
        localValue.value = list;
      }
    };

    expose({
      reset: () => {
        localValue.value = [];
      },
    });

    return () => (
      <div class="filter-main">
        <bk-select
          ref={selectRef}
          value={localValue.value}
          size="small"
          class="filter-select"
          multiple
          searchable={props.searchable}
          popover-min-width={150}
          scroll-height={280}
          ext-popover-cls="filter-select-ext-popover"
          on-change={handleSelectChange}
        >
          <div slot="trigger">
            <log-icon
              common
              type="funnel"
              class={{
                "funnel-icon": true,
                "is-funnel-active": localValue.value.length > 0,
              }}
            />
          </div>
          {props.list.map((option) => (
            <bk-option key={option.id} id={option.id} name={option.name}>
              <bk-checkbox checked={localValue.value.includes(option.id)} />
              <span class="option-name">{option.name}</span>
            </bk-option>
          ))}
          <div slot="extension" class="operate-btns">
            <bk-button
              size="small"
              theme="primary"
              text
              on-click={handleConfirm}
            >
              {t("确定")}
            </bk-button>
            <bk-button size="small" theme="primary" text on-click={handleReset}>
              {t("重置")}
            </bk-button>
          </div>
        </bk-select>
      </div>
    );
  },
});
