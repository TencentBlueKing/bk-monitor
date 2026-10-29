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

import { ref, type Ref } from 'vue';
import type { CreateElement } from '@legacy-vue';

import useLocale from '@/shared/composables/use-locale';
import { SPACE_TYPE_MAP } from '@/app/state/constant';

export interface SpaceSelectorOption<Id> {
  bk_biz_id: Id;
  is_use?: boolean;
  space_full_code_name: string;
  space_type_name?: string;
  tags: { id: keyof typeof SPACE_TYPE_MAP; name: string }[];
}
export interface SpaceSelectorOptions<Id> {
  spaceMultiple?: boolean;
  isUseMark?: boolean;
  onSelect?: (id: Id) => void;
}
export function useSpaceSelector<Id extends string | number>(
  visibleBkBiz: Ref<Id[]>,
  options: SpaceSelectorOptions<Id> = {},
) {
  const { t } = useLocale();
  const spaceMultiple = ref(options.spaceMultiple ?? true); // 空间多选
  const isUseMark = ref(options.isUseMark ?? true); // 是否展示正在使用的标记

  // 空间选择
  function handleSelectSpaceChange(bizId: Id) {
    if (visibleBkBiz.value.includes(bizId)) {
      visibleBkBiz.value = visibleBkBiz.value.filter(val => val !== bizId);
    } else {
      visibleBkBiz.value = [...visibleBkBiz.value, bizId];
    }
  }

  // 空间选择器下拉选择面板渲染
  function virtualscrollSpaceList(item: SpaceSelectorOption<Id>, h: CreateElement) {
    return h(
      'div',
      {
        class: `space-code-option ${spaceMultiple.value && visibleBkBiz.value.includes(item.bk_biz_id) ? 'is-selected' : ''}`,
        on: {
          click: (e: Event) => {
            e.stopPropagation();
            (options.onSelect ?? handleSelectSpaceChange)(item.bk_biz_id);
          },
        },
      },
      [
        h('div', { class: 'list-item-left' }, [
          isUseMark.value &&
            h('span', { class: `identify-icon ${isUseMark.value && item.is_use ? 'is-use' : 'not-use'}` }),
          h('span', { class: 'code-name' }, [
            item.space_full_code_name,
            isUseMark.value && item.is_use ? `（${t('正在使用')}）` : '',
          ]),
        ]),
        h('div', { class: 'list-item-right' }, [
          item.space_type_name &&
            item.tags.map(tag =>
              h(
                'span',
                {
                  class: 'list-item-tag light-theme',
                  style: {
                    ...SPACE_TYPE_MAP[tag.id].light,
                  },
                },
                tag.name,
              ),
            ),
          spaceMultiple.value &&
            h('span', {
              class: visibleBkBiz.value.includes(item.bk_biz_id) && 'bk-icon icon-check-1',
            }),
        ]),
      ],
    );
  }

  return {
    spaceMultiple,
    isUseMark,
    visibleBkBiz,
    handleSelectSpaceChange,
    virtualscrollSpaceList,
  };
}
