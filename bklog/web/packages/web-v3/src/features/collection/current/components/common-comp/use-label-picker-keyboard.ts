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

import {nextTick, onBeforeUnmount, ref, watch, type Ref} from 'vue';

type LabelOption = {tag_id?: number | string; disabled?: boolean};
type PickerOptions = {
  open: Readonly<Ref<boolean>>;
  disabled: Readonly<Ref<boolean>>;
  options: Readonly<Ref<LabelOption[]>>;
  searchInput: Readonly<Ref<{blur(): void} | null>>;
  select: (id: number | string) => void;
};

/** V2 custom-select keyboard contract: skip disabled options and wrap arrows. */
export default function useLabelPickerKeyboard({open, disabled, options, searchInput, select}: PickerOptions) {
  const activeId = ref<number | string>('');
  const handleKeydown = (event: KeyboardEvent) => {
    if (!open.value || disabled.value) return;
    const available = options.value.filter(option => !option.disabled);
    if (event.code === 'ArrowDown' || event.code === 'ArrowUp') {
      if (!available.length) return;
      event.preventDefault();
      event.stopPropagation();
      searchInput.value?.blur();
      const index = available.findIndex(option => option.tag_id === activeId.value);
      const nextIndex = event.code === 'ArrowDown'
        ? (index >= available.length - 1 ? 0 : index + 1)
        : (index === 0 ? available.length - 1 : index - 1);
      activeId.value = available[nextIndex]?.tag_id ?? '';
      nextTick(() => document.querySelector('.collection-label-picker .is-keyboard-active')?.scrollIntoView({block: 'nearest'}));
    } else if ((event.code === 'Enter' || event.code === 'NumpadEnter') && !(event.target as HTMLElement)?.closest('.collection-label-search')) {
      select(activeId.value);
    }
  };
  watch(open, visible => {
    document.removeEventListener('keydown', handleKeydown);
    if (!visible) return;
    activeId.value = options.value.find(option => !option.disabled)?.tag_id ?? '';
    document.addEventListener('keydown', handleKeydown);
  });
  onBeforeUnmount(() => document.removeEventListener('keydown', handleKeydown));
  return activeId;
}
