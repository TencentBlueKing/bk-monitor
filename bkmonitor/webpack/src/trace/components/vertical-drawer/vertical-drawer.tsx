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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, computed, defineComponent, shallowRef, Transition, useTemplateRef } from 'vue';

import { useVerticalResize } from '../../hooks/use-vertical-resize';

import type { VerticalResizeDirection } from '../../hooks/use-vertical-resize';

import './vertical-drawer.scss';

/** 显隐机制：v-if 挂载 / 卸载，v-show 保留 DOM 仅切换 display */
type VerticalDrawerDisplayMode = 'v-if' | 'v-show';
/** 弹出方向：贴容器底部或顶部 */
type VerticalDrawerPlacement = 'bottom' | 'top';

/** 进出场过渡名，与 scss 中的 vertical-drawer-slide-* 类名对应 */
const TRANSITION_NAME = 'vertical-drawer-slide';

/**
 * 垂直方向弹出抽屉：贴最近的定位父容器底边/顶边弹出，可拖拽调高。
 * 显隐由 isShow 驱动，父级可用 v-model:isShow 或监听 close 自行处理。
 */
export default defineComponent({
  name: 'VerticalDrawer',
  props: {
    /** 是否展示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 显隐机制：v-if 每次挂载重置内部状态，v-show 保留 DOM 与内部状态 */
    displayMode: {
      type: String as PropType<VerticalDrawerDisplayMode>,
      default: 'v-if',
    },
    /** 弹出方向 */
    placement: {
      type: String as PropType<VerticalDrawerPlacement>,
      default: 'bottom',
    },
    /** 标题 */
    title: {
      type: String,
      default: '',
    },
    /** 标题后的副标题，为空时不渲染分隔线与副标题 */
    subtitle: {
      type: String,
      default: '',
    },
    /** 初始高度 */
    defaultHeight: {
      type: Number,
      default: 440,
    },
    /** 拖拽调高的下限 */
    minHeight: {
      type: Number,
      default: 200,
    },
    /** 拖拽调高的上限，缺省时按父容器高度扣除 reserveHeight 推算 */
    maxHeight: {
      type: Number,
    },
    /** 未配置 maxHeight 时，为上方（placement 为 top 时为下方）内容预留的高度 */
    reserveHeight: {
      type: Number,
      default: 120,
    },
    /** 是否展示顶部拖拽条并允许调高 */
    hasResize: {
      type: Boolean,
      default: true,
    },
    /** 是否展示右上角关闭按钮 */
    showClose: {
      type: Boolean,
      default: true,
    },
    /** 层级 */
    zIndex: {
      type: Number,
      default: 200,
    },
  },
  emits: {
    /** 关闭按钮点击，配合 v-model:isShow 使用 */
    'update:isShow': (value: boolean) => typeof value === 'boolean',
    /** 关闭按钮点击 */
    close: () => true,
  },
  setup(props, { emit }) {
    /** 抽屉根节点，拖拽调高时按父容器高度推算上限 */
    const rootRef = useTemplateRef<HTMLElement>('rootRef');
    /** 当前高度 */
    const height = shallowRef(props.defaultHeight);

    const rootClass = computed(() => ({
      'is-bottom': props.placement === 'bottom',
      'is-top': props.placement === 'top',
      'vertical-drawer': true,
    }));

    const rootStyle = computed(() => ({
      height: `${height.value}px`,
      zIndex: props.zIndex,
    }));

    /** 关闭按钮：同时抛出 v-model 更新与独立的 close 事件 */
    function handleClose() {
      emit('update:isShow', false);
      emit('close');
    }

    const { isResizing, startResize } = useVerticalResize({
      getHeight: () => height.value,
      getMaxHeight: () =>
        Math.max(
          props.minHeight,
          props.maxHeight ?? (rootRef.value?.parentElement?.clientHeight ?? 0) - props.reserveHeight
        ),
      getMinHeight: () => props.minHeight,
      onResize: value => (height.value = value),
    });

    /**
     * @description 拖拽调高：上限取 maxHeight 或父容器高度减去预留高度；
     *              顶部弹出时下拉变高，底部弹出时上拉变高
     * @param {MouseEvent} e 鼠标按下事件
     */
    function handleResizeStart(e: MouseEvent) {
      const direction: VerticalResizeDirection = props.placement === 'top' ? 'down' : 'up';
      startResize(e, direction);
    }

    return { handleClose, handleResizeStart, isResizing, rootClass, rootStyle };
  },
  render() {
    const isVShow = this.displayMode === 'v-show';
    return (
      <Transition
        appear={!isVShow && this.isShow}
        name={TRANSITION_NAME}
      >
        {!isVShow && !this.isShow ? null : (
          <div
            ref='rootRef'
            style={this.rootStyle}
            class={this.rootClass}
            v-show={isVShow ? this.isShow : true}
          >
            {this.hasResize ? (
              <div
                class={['drawer-resize-handle', { 'is-resizing': this.isResizing }]}
                onMousedown={this.handleResizeStart}
              />
            ) : null}
            <div class='drawer-header'>
              <div class='header-title-block'>
                <span class='drawer-title'>{this.title}</span>
                {this.subtitle ? <span class='title-divider' /> : null}
                {this.subtitle ? (
                  <span
                    class='drawer-subtitle'
                    v-overflow-tips={{ placement: 'top', theme: 'dark text-wrap' }}
                  >
                    {this.subtitle}
                  </span>
                ) : null}
              </div>
              <div class='header-actions'>
                {this.$slots['header-actions']?.()}
                {this.showClose ? (
                  <i
                    class='icon-monitor icon-mc-close-copy drawer-close'
                    onClick={this.handleClose}
                  />
                ) : null}
              </div>
            </div>
            <div class='drawer-body'>{this.$slots.default?.()}</div>
          </div>
        )}
      </Transition>
    );
  },
});
