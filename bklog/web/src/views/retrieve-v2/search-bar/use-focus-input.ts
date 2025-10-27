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

import { getCurrentInstance, onMounted, onUnmounted, ref, watch } from 'vue';

// @ts-expect-error
import { getCharLength } from '@/common/util';
import RetrieveHelper from '@/views/retrieve-helper';
import { isElement } from 'lodash-es';

import PopInstanceUtil from '../../../global/pop-instance-util';

export default (
  props,
  {
    formatModelValueItem,
    refContent,
    refTarget,
    refWrapper,
    onShowFn,
    onHiddenFn,
    arrow = true,
    newInstance = true,
    tippyOptions = {},
    onHeightChange,
    addInputListener = true,
    handleWrapperClick,
    onInputFocus,
    afterShowKeyEnter,
  },
) => {
  const modelValue = ref([]);
  const sectionHeight = ref(0);

  // 是否为父级容器元素点击操作
  // 避免容器元素点击时触发 hideOnclick多次渲染
  const isDocumentMousedown = ref(false);

  // 表示是否聚焦input输入框，如果聚焦在 input输入框，再次点击弹出内容不会重复渲染
  const isInputTextFocus = ref(false);

  let resizeObserver: ResizeObserver = null;
  const INPUT_MIN_WIDTH = 12;
  const popInstanceUtil = new PopInstanceUtil({ refContent, onShowFn, onHiddenFn, arrow, newInstance, tippyOptions });

  const uninstallInstance = () => popInstanceUtil.uninstallInstance();
  const getTippyInstance = () => popInstanceUtil.getTippyInstance();

  /**
   * 处理多次点击触发多次请求的事件
   */
  const delayShowInstance = target => {
    popInstanceUtil?.cancelHide();
    popInstanceUtil?.show(target);
  };

  const setIsInputTextFocus = (val: boolean) => {
    isInputTextFocus.value = val;
  };

  const setModelValue = val => {
    if (Array.isArray(val)) {
      modelValue.value = (val ?? []).map(formatModelValueItem);
      return;
    }

    modelValue.value = formatModelValueItem(val);
  };

  let instance: any;
  const getRoot = () => {
    return instance?.proxy?.$el;
  };
  const getTargetInput = () => {
    const target = refWrapper?.value ?? getRoot();
    const input = target?.querySelector('.tag-option-focus-input');
    return input as HTMLInputElement;
  };

  const isInstanceShown = () => popInstanceUtil.isShown();

  const handleContainerClick = (e?) => {
    const root = getRoot();
    if (root !== undefined && (e === undefined || root === e?.target)) {
      const input = root.querySelector('.tag-option-focus-input');

      input?.focus();
      input?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);

      if (!isInstanceShown()) {
        setIsInputTextFocus(true);
        onInputFocus?.();
        delayShowInstance(getPopTarget());
      }
      return input;
    }
  };

  const repositionTippyInstance = () => {
    if (isInstanceShown()) {
      popInstanceUtil.repositionTippyInstance();
    }
  };

  const handleFulltextInput = e => {
    const input = getTargetInput();
    if (input !== undefined && e.target === input) {
      const value = input.value;
      const charLen = getCharLength(value);
      const maxWidth = 500;
      const width = (charLen || 1) * INPUT_MIN_WIDTH;

      input.style.setProperty('width', `${width > maxWidth ? maxWidth : width}px`);
    }
  };

  const handleInputBlur = (e?) => {
    const input = getTargetInput();
    if (input !== undefined && (e === undefined || e.target === input)) {
      input.value = '';
      input?.style.setProperty('width', `${1 * INPUT_MIN_WIDTH}px`);
    }
  };

  const setDefaultInputWidth = () => {
    const input = getTargetInput();
    input?.style?.setProperty?.('width', `${1 * INPUT_MIN_WIDTH}px`);
  };

  const hideTippyInstance = () => {
    popInstanceUtil?.hide(180);
  };

  const resizeHeightObserver = target => {
    if (!target) {
      return;
    }

    // 创建一个 ResizeObserver 实例
    resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
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
    () => [props.value],
    () => {
      setModelValue(props.value);
    },
    { deep: true, immediate: true },
  );

  const handleWrapperClickCapture = e => {
    isDocumentMousedown.value = handleWrapperClick?.(e, { getTippyInstance }) ?? true;
  };

  const setIsDocumentMousedown = val => {
    isDocumentMousedown.value = val;
  };

  const getPopTarget = () => {
    if (refTarget?.value && isElement(refTarget.value)) {
      return refTarget.value;
    }

    return getRoot();
  };

  const handleKeydown = event => {
    RetrieveHelper.beforeSlashKeyKeyDown(event, () => {
      // 检查按下的键是否是斜杠 "/"（需兼容不同键盘布局）
      const isSlashKey = event.key === '/' || event.keyCode === 191;
      const isEscKey = event.key === 'Escape' || event.keyCode === 27;

      if (isSlashKey && !popInstanceUtil.isShown()) {
        // 阻止浏览器默认行为（如打开浏览器搜索栏）
        event.preventDefault();
        const targetElement = getPopTarget();

        if (refTarget?.value && isElement(refTarget.value)) {
          delayShowInstance(targetElement);
          setTimeout(() => {
            afterShowKeyEnter?.();
          });
          return;
        }

        targetElement?.click?.();
        setTimeout(() => {
          afterShowKeyEnter?.();
        });
        return;
      }

      if (isEscKey && popInstanceUtil.isShown()) {
        setIsInputTextFocus(false);
        popInstanceUtil.hide(100);
      }
    });
  };

  const getTippyUtil = () => popInstanceUtil;

  onMounted(() => {
    instance = getCurrentInstance();
    document.addEventListener('mousedown', handleWrapperClickCapture, { capture: true });
    document?.addEventListener('keydown', handleKeydown);
    document?.addEventListener('click', handleContainerClick);

    setDefaultInputWidth();

    if (addInputListener) {
      document?.addEventListener('input', handleFulltextInput);
    }
    resizeHeightObserver(instance?.proxy?.$el);
  });

  onUnmounted(() => {
    uninstallInstance();
    document?.removeEventListener('click', handleContainerClick);
    if (addInputListener) {
      document?.removeEventListener('input', handleFulltextInput);
    }

    document.removeEventListener('mousedown', handleWrapperClickCapture);
    document?.removeEventListener('keydown', handleKeydown);
    resizeObserver?.disconnect();
    resizeObserver = null;
  });

  return {
    modelValue,
    isDocumentMousedown,
    isInputTextFocus,
    setIsInputTextFocus,
    setIsDocumentMousedown,
    repositionTippyInstance,
    hideTippyInstance,
    getTippyInstance,
    handleContainerClick,
    handleInputBlur,
    delayShowInstance,
    isInstanceShown,
    getTippyUtil,
  };
};
