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
import { defineComponent, ref, type PropType, onMounted, onUnmounted } from 'vue';

import PopInstanceUtil from '../../global/pop-instance-util';

import type { Props as TippyProps } from 'tippy.js';

import './index.scss';

export default defineComponent({
  props: {
    options: {
      type: Object as PropType<TippyProps>,
      default: () => ({}),
    },
    trigger: {
      type: String as PropType<'click' | 'hover'>,
      default: 'click',
    },
    delegateTarget: {
      type: Object as PropType<HTMLElement>,
      default: null,
    },
    contentClass: {
      type: String,
      default: '',
    },
    beforeHide: {
      type: Function as PropType<(e: MouseEvent) => boolean>,
      default: () => true,
    },
    content: {
      type: [String, Function] as PropType<(() => JSX.Element) | JSX.Element | string>,
      default: undefined,
    },
  },
  setup(props, { slots, expose }) {
    const refContentElement = ref(null);
    const refTargetElement = ref(null);
    let isDocumentClickBinded = false;
    let instance: PopInstanceUtil = null;

    const hanldeDocumentClick = (e: MouseEvent) => {
      if (refContentElement.value?.contains(e.target as HTMLElement)) {
        return;
      }

      if (instance?.isShown()) {
        const target = e.target as HTMLElement;
        if (target === refTargetElement.value) {
          return;
        }

        if (refTargetElement.value.contains(target)) {
          return;
        }

        if (props.beforeHide?.(e) ?? true) {
          instance?.hide();
        }
      }
    };

    instance = new PopInstanceUtil({
      refContent: () => refContentElement.value,
      tippyOptions: {
        ...props.options,
        trigger: 'manual',
        onShown: (...args) => {
          props.options.onShown?.(...args);

          if (props.options.hideOnClick === false && props.trigger === 'click' && !isDocumentClickBinded) {
            document.addEventListener('click', hanldeDocumentClick);
            isDocumentClickBinded = true;
          }
        },
        onHidden: (...args) => {
          props.options.onHidden?.(...args);
          if (props.options.hideOnClick === false && props.trigger === 'click' && isDocumentClickBinded) {
            document.removeEventListener('click', hanldeDocumentClick);
            isDocumentClickBinded = false;
          }
        },
      },
    });

    const handleRootElementClick = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();

      if (instance.isShown()) {
        instance.hide();
        return;
      }
      instance.show(props.delegateTarget ?? refTargetElement.value);
    };

    const handleRootElementMouseenter = () => {
      if (instance.isShown()) {
        return;
      }
      instance.show(props.delegateTarget ?? refTargetElement.value);
    };

    const handleRootElementMouseleave = () => {
      instance?.hide(120);
    };

    const handleContentElementMouseenter = () => {
      instance.cancelHide();
    };

    const handleContentElementMouseleave = () => {
      instance.hide();
    };

    const resolveOptions = () => {
      if (props.trigger === 'click') {
        refTargetElement.value?.addEventListener?.('click', handleRootElementClick);
      }

      if (props.trigger === 'hover') {
        refTargetElement.value?.addEventListener?.('mouseenter', handleRootElementMouseenter);
        refTargetElement.value?.addEventListener?.('mouseleave', handleRootElementMouseleave);

        refContentElement.value?.addEventListener?.('mouseenter', handleContentElementMouseenter);
        refContentElement.value?.addEventListener?.('mouseleave', handleContentElementMouseleave);
      }
    };

    const show = (target?: HTMLElement) => {
      instance.cancelHide();
      instance.show(target ?? props.delegateTarget ?? refTargetElement.value);
    };

    const hide = (delay?: number) => {
      instance.hide(delay);
    };

    const setProps = (prop: TippyProps) => {
      instance.setProps(prop);
    };

    onMounted(() => {
      resolveOptions();
    });

    onUnmounted(() => {
      if (props.trigger === 'click') {
        refTargetElement.value?.removeEventListener('click', handleRootElementClick);
      }

      if (props.trigger === 'hover') {
        refTargetElement.value?.removeEventListener('mouseenter', handleRootElementMouseenter);
        refTargetElement.value?.removeEventListener('mouseleave', handleRootElementMouseleave);

        refContentElement.value?.removeEventListener('mouseenter', handleContentElementMouseenter);
        refContentElement.value?.removeEventListener('mouseleave', handleContentElementMouseleave);
      }

      if (isDocumentClickBinded) {
        document.removeEventListener('click', hanldeDocumentClick);
        isDocumentClickBinded = false;
      }
    });

    expose({ show, hide, setProps });
    const renderSlot = () => {
      if (typeof props.content === 'function') {
        return props.content();
      }

      return props.content;
    };

    return () => (
      <div ref={refTargetElement}>
        {slots.default?.()}
        <div style='display: none;'>
          <div
            ref={refContentElement}
            class={props.contentClass}
          >
            {slots.content?.() ?? renderSlot()}
          </div>
        </div>
      </div>
    );
  },
});
