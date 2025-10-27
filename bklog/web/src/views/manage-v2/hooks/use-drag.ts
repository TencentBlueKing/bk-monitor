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

import { ref } from 'vue';

import useStore from '@/hooks/use-store';

export function useDrag() {
  const store = useStore();

  const minIntroWidth = ref(300); // 最小宽度
  const maxIntroWidth = ref(480); // 默认最大宽度
  const introWidth = ref(1); // 侧边栏宽度
  const isDraging = ref(false); // 是否正在拖拽
  const currentTreeBoxWidth = ref<null | number>(null); // 当前侧边宽度
  const currentScreenX = ref<null | number>(null); // 当前鼠标位置

  function dragBegin(e: MouseEvent) {
    currentTreeBoxWidth.value = introWidth.value;
    currentScreenX.value = e.screenX;
    window.addEventListener('mousemove', dragMoving, { passive: true });
    window.addEventListener('mouseup', dragStop, { passive: true });
  }

  function dragMoving(e: MouseEvent) {
    isDraging.value = true;
    const newTreeBoxWidth = (currentTreeBoxWidth.value ?? 0) - e.screenX + (currentScreenX.value ?? 0);
    if (newTreeBoxWidth < minIntroWidth.value) {
      introWidth.value = minIntroWidth.value;
    } else if (newTreeBoxWidth >= maxIntroWidth.value) {
      introWidth.value = maxIntroWidth.value;
    } else {
      introWidth.value = newTreeBoxWidth;
    }
  }

  function dragStop() {
    isDraging.value = false;
    currentTreeBoxWidth.value = null;
    currentScreenX.value = null;
    window.removeEventListener('mousemove', dragMoving);
    window.removeEventListener('mouseup', dragStop);
    store.commit('updateChartSize');
  }

  return {
    minIntroWidth,
    maxIntroWidth,
    introWidth,
    isDraging,
    dragBegin,
    dragMoving,
    dragStop,
  };
}
