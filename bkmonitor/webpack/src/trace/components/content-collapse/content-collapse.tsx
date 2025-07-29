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
import { type VNode, defineComponent, nextTick, onBeforeMount, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { debounce } from 'lodash';

import './content-collapse.scss';

export default defineComponent({
  name: 'ContentCollapse',
  props: {
    /** 展开状态 */
    expand: { default: false, type: Boolean },
    /** 收起的默认高度 */
    defaultHeight: { default: 0, type: Number },
    /** 展开的最大高度 */
    maxHeight: { type: Number, required: true },
    /** 未展开是否渲染content */
    renderContent: { default: true, type: Boolean },
    /** 是否需要关闭按钮 */
    needCloseButton: { default: true, type: Boolean },
    /** 渲染就开启动画 */
    renderAnimation: { default: true, type: Boolean },
  },
  emits: ['overflow', 'expandChange'],
  setup(props, { emit, slots }) {
    const instanceRef = ref();
    /** 内容区域 */
    const collapseContentRef = ref();
    /** 高度 */
    const height = ref<number>(0);
    /** 最大高度 */
    const localMaxHeight = ref(0);
    /** 是否渲染content */
    const showContent = ref(false);
    /** 是否允许溢出滚动 */
    const isOverflow = ref(false);
    const openAnimation = ref(false);

    onBeforeMount(() => {
      props.defaultHeight && (localMaxHeight.value = props.defaultHeight);
      if (props.renderAnimation) {
        openAnimation.value = true;
      } else {
        setTimeout(() => {
          openAnimation.value = true;
        }, 50);
      }
    });

    onMounted(() => {
      addListener(instanceRef.value, handleTransitionend);
      addListener(instanceRef.value, handleResize);
      if (props.expand) {
        nextTick(() => updateHeight(props.expand));
      }
      checkOverflow();
    });

    onBeforeUnmount(() => {
      if (instanceRef.value) {
        removeListener(instanceRef.value, handleTransitionend);
        removeListener(instanceRef.value, handleResize);
      }
    });
    watch(
      () => props.expand,
      val => {
        isOverflow.value = false;
        if (props.renderContent || (!props.renderContent && val)) showContent.value = val;
        props.renderContent ? updateHeight(val) : nextTick(() => updateHeight(val));
        !val && instanceRef.value?.scrollTo?.(0, 0);
      },
      { immediate: true }
    );

    /**
     * @description: 监听动画结束
     * @param {TransitionEvent} evt
     */
    function handleTransitionend(evt: TransitionEvent) {
      if (evt.propertyName === 'height' && evt.target === instanceRef.value) {
        if (!props.expand) {
          showContent.value = props.expand;
        }
        isOverflow.value = props.expand;
      }
    }

    /**
     * @description: 更新高度
     * @param {boolean} val 展开状态
     */
    function updateHeight(val: boolean) {
      localMaxHeight.value = props.maxHeight;
      const contentHeight = collapseContentRef.value?.scrollHeight;
      height.value = val ? contentHeight : contentHeight < props.defaultHeight ? contentHeight : props.defaultHeight;
      !!localMaxHeight.value && val && height.value > localMaxHeight.value && (height.value = localMaxHeight.value);
    }

    /** 对外暴露更新内容区域高度的方法 */
    function handleContentResize() {
      props.expand && updateHeight(true);
    }

    /**
     * @description: 渲染内容区域
     * @return {VNode[]}
     */
    function handleRenderContent(): VNode[] {
      if (props.renderContent) {
        return slots.default?.();
      }
      return showContent.value ? slots.default?.() : undefined;
    }

    function handleRenderCloseBtn() {
      if (!props.needCloseButton) return undefined;
      const tpl = (
        <i
          class={['monitor-collapse-close icon-monitor icon-mc-triangle-down', { 'is-expand': showContent.value }]}
          onClick={handleClickClose}
        />
      );
      if (props.renderContent) {
        return tpl;
      }
      return showContent.value ? tpl : undefined;
    }

    function handleClickClose() {
      emit('expandChange', !showContent.value);
    }

    const handleResize = debounce(() => {
      nextTick(() => updateHeight(props.expand));
      checkOverflow();
    }, 300);

    function checkOverflow() {
      isOverflow.value = collapseContentRef.value?.scrollHeight > props.defaultHeight;
      emit('overflow', isOverflow.value);
    }

    return {
      instanceRef,
      height,
      collapseContentRef,
      handleResize,
      isOverflow,
      openAnimation,
      handleRenderContent,
      handleRenderCloseBtn,
      handleContentResize,
    };
  },
  render() {
    return (
      <div
        ref='instanceRef'
        style={{ height: `${this.height}px` }}
        class={['monitor-collapse-wrap', { 'is-overflow': this.isOverflow, animation: this.openAnimation }]}
      >
        <div
          ref='collapseContentRef'
          class='monitor-collapse-content'
        >
          {this.handleRenderContent()}
        </div>
        {this.handleRenderCloseBtn()}
      </div>
    );
  },
});
