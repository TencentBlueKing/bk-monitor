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
import { ref, watch, onMounted, getCurrentInstance, onUnmounted } from 'vue';

// @ts-ignore
import { getCharLength } from '@/common/util';

import PopInstanceUtil from './pop-instance-util';

export default (
  props,
  {
    formatModelValueItem,
    refContent,
    onShowFn,
    onHiddenFn,
    arrow = true,
    newInstance = true,
    tippyOptions = {},
    onHeightChange,
  },
) => {
  const modelValue = ref([]);
  const inputValue = ref('');
  const sectionHeight = ref(0);

  let resizeObserver = null;
  const INPUT_MIN_WIDTH = 12;
  const popInstanceUtil = new PopInstanceUtil({ refContent, onShowFn, onHiddenFn, arrow, newInstance, tippyOptions });

  const uninstallInstance = () => popInstanceUtil.uninstallInstance();
  const getTippyInstance = () => popInstanceUtil.getTippyInstance();

  /**
   * 处理多次点击触发多次请求的事件
   */
  const delayShowInstance = target => popInstanceUtil.show(target);

  const setModelValue = val => {
    modelValue.value = (val ?? []).map(formatModelValueItem);
  };

  let instance = undefined;

  const getTargetInput = () => {
    const target = instance?.proxy?.$el;
    const input = target?.querySelector('.tag-option-focus-input');
    return input as HTMLInputElement;
  };

  const getRoot = () => {
    return instance?.proxy?.$el;
  };

  const handleContainerClick = (e?) => {
    const root = getRoot();
    if (root !== undefined && (e === undefined || root === e?.target)) {
      const input = root.querySelector('.tag-option-focus-input');

      input?.focus();
      input?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);
      return input;
    }
  };

  const repositionTippyInstance = () => popInstanceUtil.repositionTippyInstance();

  const handleFulltextInput = e => {
    const input = getTargetInput();
    if (input !== undefined && e.target === input) {
      const value = input.value;
      const charLen = getCharLength(value);
      input.style.setProperty('width', `${charLen * INPUT_MIN_WIDTH}px`);
    }
  };

  const handleInputBlur = e => {
    const input = getTargetInput();
    if (input !== undefined && e.target === input) {
      input.value = '';
      input?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);
    }
  };

  const hideTippyInstance = () => popInstanceUtil.hide();

  const resizeHeightObserver = target => {
    if (!target) {
      return;
    }

    // 创建一个 ResizeObserver 实例
    resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        // 获取元素的新高度
        const newHeight = entry.contentRect.height;

        if (newHeight !== sectionHeight.value) {
          sectionHeight.value = newHeight;
          repositionTippyInstance();
          onHeightChange?.(newHeight);
        }
      }
    });

    // 开始监听元素
    resizeObserver.observe(target);
  };

  watch(
    props,
    () => {
      setModelValue(props.value);
      // setFocusInputItem();
    },
    { deep: true, immediate: true },
  );

  onMounted(() => {
    instance = getCurrentInstance();

    document?.addEventListener('click', handleContainerClick);
    document?.addEventListener('input', handleFulltextInput);
    resizeHeightObserver(instance?.proxy?.$el);
  });

  onUnmounted(() => {
    uninstallInstance();
    document?.removeEventListener('click', handleContainerClick);
    document?.removeEventListener('input', handleFulltextInput);
    resizeObserver?.disconnect();
  });

  return {
    modelValue,
    inputValue,
    hideTippyInstance,
    getTippyInstance,
    handleContainerClick,
    handleInputBlur,
    delayShowInstance,
  };
};
