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

import { defineComponent, ref, type PropType } from 'vue';

import BklogPopover from '@/components/bklog-popover';

export interface IRowMenuItem {
  key: string;
  label: string;
  disabled: boolean;
}

export default defineComponent({
  name: 'RowMoreMenu',
  props: {
    items: {
      type: Array as PropType<IRowMenuItem[]>,
      default: () => [],
    },
    hasPermission: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['select'],
  setup(props, { emit }) {
    const popoverRef = ref<{ hide: () => void } | null>(null);
    const isVisible = ref(false);

    const handleSelect = (item: IRowMenuItem) => {
      if (item.disabled) return;
      popoverRef.value?.hide();
      emit('select', item.key);
    };

    return () => (
      <BklogPopover
        ref={popoverRef}
        class='row-more-menu'
        trigger='click'
        options={
          {
            placement: 'bottom-end',
            theme: 'light table-menu-popover',
            interactive: true,
            hideOnClick: false,
            arrow: false,
            offset: [0, 4],
            appendTo: () => document.body,
            onShow: () => {
              isVisible.value = true;
            },
            onHide: () => {
              isVisible.value = false;
            },
          } as any
        }
        content={() => (
          <div class='row-menu-content'>
            {props.items.map(item => (
              <span
                key={item.key}
                v-cursor={{ active: !props.hasPermission }}
                class={{ 'menu-item': true, disabled: item.disabled }}
                on-click={() => handleSelect(item)}
              >
                {item.label}
              </span>
            ))}
          </div>
        )}
      >
        <span class={{ 'bk-icon icon-more more-btn table-more-btn': true, 'is-hover': isVisible.value }} />
      </BklogPopover>
    );
  },
});
