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

import { defineComponent, ref, onMounted, onBeforeUnmount, PropType } from 'vue';
import { roundArrow } from 'tippy.js';
import { createRawTippyOverlay } from '@/shared/global/overlay/index';
import useLocale from '@/shared/composables/use-locale';
import CreateTemplate from '../create-template/index';
import EditTemplate from './edit-template/index';
import { random } from '@/shared/lib/util';
import DeleteTemplate from './delete-template/index';

import { type TemplateItem } from '../../index';

import './index.scss';
import 'tippy.js/dist/svg-arrow.css';
import 'tippy.js/themes/light.css';

export default defineComponent({
  emits: ["refresh","click"],

  name: 'TemplateManage',
  components: {
    CreateTemplate,
    EditTemplate,
    DeleteTemplate,
  },
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
      emit('refresh');
      handleEditTemplateCancel();
    };

    const handleDeleteTemplateSuccess = () => {
      emit('refresh');
      handleDeleteTemplateCancel();
    };

    const initTippyInstance = () => {
      editTippyInstance = createRawTippyOverlay(
        `#${CSS.escape(triggerId)}`,
        {
          content: editTemplateRef.value.$el,
          allowHTML: true,
          trigger: 'manual',
          interactive: true,
          placement: 'bottom',
          arrow: roundArrow,
          theme: 'light',
        },
        {
          id: `template-edit-${triggerId}`,
          group: `template-item-${triggerId}`,
          type: 'popover',
        },
      );

      deleteTippyInstance = createRawTippyOverlay(
        `#${CSS.escape(triggerId)}`,
        {
          content: deleteTemplateRef.value.$el,
          allowHTML: true,
          trigger: 'manual',
          interactive: true,
          placement: 'bottom',
          arrow: roundArrow,
          theme: 'light',
        },
        {
          id: `template-delete-${triggerId}`,
          group: `template-item-${triggerId}`,
          type: 'popover',
        },
      );
    };

    const handleClickMain = () => {
      emit('click');
    };

    onMounted(() => {
      initTippyInstance();
    });

    onBeforeUnmount(() => {
      editTippyInstance?.[0]?.destroy?.();
      deleteTippyInstance?.[0]?.destroy?.();
      editTippyInstance = null;
      deleteTippyInstance = null;
    });

    return () => (
      <div
        class={['template-item-main', { 'is-active': props.isActive }]}
        onClick={handleClickMain}
      >
        <div class='item-title'>{props.data.template_name}</div>
        <div class='item-count'>{props.data.ruleList.length}</div>
        <bk-dropdown-menu
          v-slots={{
            'dropdown-trigger': () => (
              <div>
                <div
                  class='template-list-more-btn'
                  id={triggerId}
                >
                  <log-icon
                    type='more'
                    class='more-icon'
                  />
                </div>
              </div>
            ),
            'dropdown-content': () => (
              <ul class='bk-dropdown-list'>
                <li>
                  <a
                    href='javascript:;'
                    onClick={handleClickRename}
                  >
                    {t('重命名')}
                  </a>
                </li>

                <li>
                  <a
                    href='javascript:;'
                    onClick={handleClickDelete}
                  >
                    {t('删除')}
                  </a>
                </li>
              </ul>
            ),
          }}
          trigger='click'
          ref='largeDropdown'
        ></bk-dropdown-menu>
        <div style='display: none;'>
          <EditTemplate
            ref={editTemplateRef}
            data={props.data}
            onCancel={handleEditTemplateCancel}
            onSuccess={handleEditTemplateSuccess}
          />
        </div>
        <div style='display: none;'>
          <delete-template
            ref={deleteTemplateRef}
            data={props.data}
            onCancel={handleDeleteTemplateCancel}
            onSuccess={handleDeleteTemplateSuccess}
          />
        </div>
      </div>
    );
  },
});
