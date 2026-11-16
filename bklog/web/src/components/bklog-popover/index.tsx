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
import { defineComponent, ref, type PropType, onMounted, onUnmounted, type VNode } from 'vue';
import { overlayRegistry, shouldHideOnOutsideClick } from '../../global/overlay';
import PopInstanceUtil from '../../global/pop-instance-util';
import type { Props as TippyProps } from 'tippy.js';
import './index.scss';

let bklogPopoverSeq = 0;

// 导出theme类型
export type BklogPopoverTheme = 'bklog-light' | 'bklog-dark' | 'bklog-basic-light' | 'bklog-basic-dark';

export default defineComponent({
  props: {
    options: {
      type: Object as PropType<TippyProps>,
      default: () => ({}),
    },
    trigger: {
      type: String as PropType<'click' | 'hover' | 'manual'>,
      default: 'click',
    },
    /**
     * hover 触发模式下，鼠标移出后延迟隐藏的时间（ms）
     */
    hideDelay: {
      type: Number,
      default: 120,
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
      type: Function as PropType<(_e: MouseEvent) => boolean>,
      default: () => true,
    },
    content: {
      type: [String, Function] as PropType<(() => VNode) | VNode | string>,
      default: undefined,
    },
    overlayId: {
      type: String,
      default: '',
    },
    overlayGroup: {
      type: String,
      default: '',
    },
    overlayParentId: {
      type: String,
      default: '',
    },
    ignoreSelector: {
      type: String,
      default: '.bklog-popover-stop, .bk-selector-list, .bk-select-dropdown',
    },
  },
  setup(props, { slots, expose }) {
    const refContentElement = ref(null);
    const refTargetElement = ref(null);
    let isDocumentClickBinded = false;
    let instance: PopInstanceUtil = null;
    bklogPopoverSeq += 1;
    const resolvedOverlayId = props.overlayId || `bklog-popover-${bklogPopoverSeq}`;
    const overlayRootSelector = `[data-overlay-id="${resolvedOverlayId}"]`;

    const hideViaRegistry = () => {
      overlayRegistry.hide(resolvedOverlayId);
    };

    const hanldeDocumentClick = (e: MouseEvent) => {
      if (!instance?.isShown()) {
        return;
      }

      const target = e.target as HTMLElement;
      if (target === refTargetElement.value || refTargetElement.value?.contains(target)) {
        return;
      }

      if (overlayRegistry.isClickInsideRecord(e, resolvedOverlayId)) {
        return;
      }

      if (
        !shouldHideOnOutsideClick(e, {
          rootSelector: overlayRootSelector,
          ignoreSelector: props.ignoreSelector,
        })
      ) {
        return;
      }

      if (props.beforeHide?.(e) ?? true) {
        hideViaRegistry();
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
          // 重建实例时旧实例被销毁也会触发 onHidden，此时新实例即将显示，不能改登记状态或解绑监听
          if (instance.isDestroyingInstance(args[0])) {
            return;
          }
          overlayRegistry.hide(resolvedOverlayId);
          if (props.options.hideOnClick === false && props.trigger === 'click' && isDocumentClickBinded) {
            document.removeEventListener('click', hanldeDocumentClick);
            isDocumentClickBinded = false;
          }
        },
      },
    });

    overlayRegistry.register(resolvedOverlayId, {
      type: 'popover',
      group: props.overlayGroup || undefined,
      parentId: props.overlayParentId || undefined,
      rootSelector: overlayRootSelector,
      ignoreSelector: props.ignoreSelector,
      hide: () => instance.hide(),
    });

    const openInstance = (target?: HTMLElement) => {
      const anchor = target ?? props.delegateTarget ?? refTargetElement.value;
      const parentId = props.overlayParentId || overlayRegistry.findParentIdByElement(anchor);
      overlayRegistry.register(resolvedOverlayId, {
        type: 'popover',
        group: props.overlayGroup || undefined,
        parentId: parentId || undefined,
        rootSelector: overlayRootSelector,
        ignoreSelector: props.ignoreSelector,
        hide: () => instance.hide(),
        anchor,
      });
      overlayRegistry.open(resolvedOverlayId, { anchor });
      instance.show(anchor);
    };

    const handleRootElementClick = () => {
      if (instance.isShown()) {
        hideViaRegistry();
        return;
      }
      openInstance();
    };

    const handleRootElementMouseenter = () => {
      if (instance.isShown()) {
        return;
      }
      openInstance();
    };

    const handleRootElementMouseleave = () => {
      instance?.hide(props.hideDelay);
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
      openInstance(target);
    };

    const hide = (delay?: number) => {
      if (delay) {
        instance.hide(delay);
        return;
      }
      hideViaRegistry();
    };

    const setProps = (prop: TippyProps) => {
      instance.setProps(prop);
    };

    const update = (force = false) => {
      return instance.repositionTippyInstance(force);
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

      overlayRegistry.dispose(resolvedOverlayId);
      instance.uninstallInstance();
    });

    expose({ show, hide, setProps, update, overlayId: resolvedOverlayId });
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
            class={['bklog-overlay-root', props.contentClass].filter(Boolean).join(' ')}
            data-overlay-id={resolvedOverlayId}
          >
            {slots.content?.() ?? renderSlot()}
          </div>
        </div>
      </div>
    );
  },
});
