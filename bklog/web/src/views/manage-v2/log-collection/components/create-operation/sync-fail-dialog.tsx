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
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { computed, defineComponent, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import './sync-fail-dialog.scss';

export interface SyncFailItem {
  name: string;
  message: string;
}

export interface SyncFailDetail {
  items: SyncFailItem[];
  summary: string;
}

export default defineComponent({
  name: 'CleanTemplateSyncFailDialog',
  props: {
    value: {
      type: Boolean,
      default: false,
    },
    items: {
      type: Array as PropType<SyncFailItem[]>,
      default: () => [],
    },
    summary: {
      type: String,
      default: '',
    },
  },
  emits: ['cancel'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const hint = computed(() => {
      if (props.items.length) {
        return t('共 {n} 个采集项同步失败', { n: props.items.length });
      }
      return props.summary;
    });

    const handleCancel = () => {
      emit('cancel');
    };

    return () => (
      <bk-dialog
        width={560}
        ext-cls='clean-template-sync-fail-dialog'
        header-position='left'
        mask-close={false}
        theme='primary'
        title={t('同步失败')}
        value={props.value}
        on-cancel={handleCancel}
        on-confirm={handleCancel}
      >
        <div class='sync-fail-dialog-content'>
          {hint.value && <p class='sync-fail-hint'>{hint.value}</p>}
          {props.items.length > 0 && (
            <ul class='sync-fail-list'>
              {props.items.map((item, index) => (
                <li
                  key={`${item.name}-${index}`}
                  class='sync-fail-item'
                >
                  <div class='sync-fail-name'>{item.name}</div>
                  <div class='sync-fail-message'>{item.message}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </bk-dialog>
    );
  },
});
