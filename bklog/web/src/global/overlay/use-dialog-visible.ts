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

import { getCurrentInstance, onUnmounted, ref } from 'vue';

import { createDialogVisibleState, overlayRegistry } from './overlay-registry';
import type { OverlayRegisterOptions } from './overlay-types';

let dialogSeq = 0;

const nextDialogId = () => {
  dialogSeq += 1;
  return `bklog-dialog-${dialogSeq}`;
};

/**
 * 修复 bk-dialog 单向 :value。内部 Esc / 遮罩 / 右上角关闭走 onValueChange 回写，
 * 避免父级仍为 true 导致再次打开无响应。
 */
export const useDialogVisible = (initial = false, options: OverlayRegisterOptions = {}) => {
  const id = options.id || nextDialogId();
  const visible = ref(Boolean(initial));
  const state = createDialogVisibleState(initial, {
    onOpen: () => overlayRegistry.open(id),
    onHide: () => overlayRegistry.hide(id),
  });

  overlayRegistry.register(id, {
    ...options,
    type: options.type || 'dialog',
    hide: () => {
      visible.value = false;
      state.setVisible(false);
    },
  });

  const setVisible = (next: boolean) => {
    visible.value = state.setVisible(next);
    return visible.value;
  };

  const onValueChange = (next: boolean) => {
    visible.value = state.onValueChange(next);
    return visible.value;
  };

  if (getCurrentInstance()) {
    onUnmounted(() => {
      overlayRegistry.dispose(id);
    });
  }

  return {
    id,
    visible,
    setVisible,
    onValueChange,
  };
};

export default useDialogVisible;
