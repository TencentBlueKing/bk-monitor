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

import { defineComponent, ref, onMounted, PropType } from "vue";
import tippy, { roundArrow } from "tippy.js";
import useLocale from "@/hooks/use-locale";
import CreateTemplate from "../create-template";
import EditTemplate from "./edit-template";
import { random } from "@/common/util";
import DeleteTemplate from "./delete-template";

import { type TemplateItem } from "../../index";

import "./index.scss";
import "tippy.js/dist/svg-arrow.css";
import "tippy.js/themes/light.css";

export default defineComponent({
  name: "TemplateManage",
  props: {
    data: {
      type: Object as PropType<TemplateItem>,
      default: () => ({}),
    },
    isActive: {
      type: Boolean,
      default: false,
    },
  },
  components: {
    CreateTemplate,
    EditTemplate,
    DeleteTemplate,
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const editTemplateRef = ref<any>(null);
    const deleteTemplateRef = ref<any>(null);

    const triggerId = random(10);

    let editTippyInstance: any;
    let deleteTippyInstance: any;

    const handleClickRename = () => {
      editTippyInstance[0].show();
    };

    const handleClickDelete = () => {
      deleteTippyInstance[0].show();
    };

    const handleEditTemplateCancel = () => {
      editTippyInstance[0].hide();
    };

    const handleDeleteTemplateCancel = () => {
      deleteTippyInstance[0].hide();
    };

    const handleEditTemplateSuccess = () => {
      emit("refresh");
      handleEditTemplateCancel();
    };

    const handleDeleteTemplateSuccess = () => {
      emit("refresh");
      handleDeleteTemplateCancel();
    };

    const initTippyInstance = () => {
      editTippyInstance = tippy(`#${CSS.escape(triggerId)}`, {
        content: editTemplateRef.value.$el,
        appendTo: () => document.body,
        allowHTML: true,
        trigger: "manual",
        interactive: true,
        placement: "bottom",
        arrow: roundArrow,
        theme: "light",
      });

      deleteTippyInstance = tippy(`#${CSS.escape(triggerId)}`, {
        content: deleteTemplateRef.value.$el,
        appendTo: () => document.body,
        allowHTML: true,
        trigger: "manual",
        interactive: true,
        placement: "bottom",
        arrow: roundArrow,
        theme: "light",
      });
    };

    const handleClickMain = () => {
      emit("click");
    };

    onMounted(() => {
      initTippyInstance();
    });

    return () => (
      <div
        class={["template-item-main", { "is-active": props.isActive }]}
        on-click={handleClickMain}
      >
        <div class="item-title">{props.data.template_name}</div>
        <div class="item-count">{props.data.ruleList.length}</div>
        <bk-dropdown-menu trigger="click" ref="largeDropdown">
          <div slot="dropdown-trigger">
            <div class="template-list-more-btn" id={triggerId}>
              <log-icon type="more" class="more-icon" />
            </div>
          </div>
          <ul class="bk-dropdown-list" slot="dropdown-content">
            <li>
              <a href="javascript:;" on-click={handleClickRename}>
                {t("重命名")}
              </a>
            </li>

            <li>
              <a href="javascript:;" on-click={handleClickDelete}>
                {t("删除")}
              </a>
            </li>
          </ul>
        </bk-dropdown-menu>
        <div style="display: none;">
          <EditTemplate
            ref={editTemplateRef}
            data={props.data}
            on-cancel={handleEditTemplateCancel}
            on-success={handleEditTemplateSuccess}
          />
        </div>
        <div style="display: none;">
          <delete-template
            ref={deleteTemplateRef}
            data={props.data}
            on-cancel={handleDeleteTemplateCancel}
            on-success={handleDeleteTemplateSuccess}
          />
        </div>
      </div>
    );
  },
});
