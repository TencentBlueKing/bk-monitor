/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { defineComponent, onMounted, onScopeDispose } from 'vue';

import { getCmdShortcutKey } from 'monitor-common/utils/navigator';

export function isSelectorShortcut(event: KeyboardEvent) {
  return event.key?.toLowerCase() === 'o' && (event.metaKey || event.ctrlKey);
}

export function selectorShortcutLabel() {
  return `${getCmdShortcutKey()} + O`;
}

/** enabled 为 false 时不拦截按键，交给当前页面的其他监听。 */
export function useSelectorShortcut(action: () => void, enabled: () => boolean = () => true) {
  function onKeydown(event: KeyboardEvent) {
    if (!enabled() || !isSelectorShortcut(event)) return;
    event.preventDefault();
    action();
  }
  onMounted(() => window.addEventListener('keydown', onKeydown));
  onScopeDispose(() => window.removeEventListener('keydown', onKeydown));
}

export default defineComponent({
  name: 'SelectorShortcut',
  render() {
    return <span class='select-shortcut-keys'>{selectorShortcutLabel()}</span>;
  },
});
