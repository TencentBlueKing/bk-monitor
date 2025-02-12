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
import { getCurrentInstance, nextTick } from 'vue';
import { defineComponent, onMounted, onUnmounted, ref, watch } from 'vue';

import './monitor-drag.scss';

export default defineComponent({
  name: 'MonitorDragComp',
  props: {
    minWidth: { type: Number, default: 200 },
    maxWidth: { type: Number, default: 500 },
    toggleSet: { type: Boolean, default: false },
    resetPosKey: { type: String, default: '' },
    startPlacement: { type: String, default: 'right' },
    theme: { type: String, default: 'normal' },
    lineText: { type: String, default: window.i18n.tc('详情') },
    isShow: { type: Boolean, default: false },
    isInPanelView: { type: Boolean, default: false },
    top: { type: Number, default: 0 },
  },
  emits: ['trigger', 'move'],
  setup(props, { emit }) {
    const left = ref(0);
    const defaultLeft = ref(0);
    const show = ref(true);
    const isMoving = ref(false);
    const instance = getCurrentInstance();

    watch(
      () => [props.toggleSet, props.resetPosKey],
      () => {
        show.value = false;
        setTimeout(handleSetDefault, 320);
      }
    );

    onMounted(() => {
      handleSetDefault();
      window.addEventListener('resize', handleClientResize);
    });

    onUnmounted(() => {
      window.removeEventListener('resize', handleClientResize);
    });

    function handleClientResize() {
      handleSetDefault();
    }
    /**
     * @description: 初始化设置位置
     * @param {*}
     * @return {*}
     */
    function handleSetDefault() {
      setTimeout(() => {
        const rect = instance?.proxy.$el.parentElement.getBoundingClientRect();
        left.value = props.startPlacement === 'left' ? rect.left - 3 : rect.width + rect.left - 3;
        instance.proxy.$el.parentElement.style.position = 'relative';
        defaultLeft.value = left.value;
        show.value = true;
      }, 30);
    }
    /**
     * @description: mousdown触发
     * @param {object} e 事件参数
     * @return {*}
     */
    function handleMouseDown(mouseDownEvent: MouseEvent) {
      const target = instance?.proxy.$el.parentElement;
      let mouseX = mouseDownEvent.clientX;
      if (props.isInPanelView && left.value) {
      }
      document.onselectstart = () => false;
      document.ondragstart = () => false;
      function handleMouseMove(event) {
        isMoving.value = true;
        const swipeRight = event.clientX - mouseX >= 0;
        mouseX = event.clientX;
        document.body.style.cursor = 'col-resize';
        const rect = target.getBoundingClientRect();
        const isMax =
          props.startPlacement === 'left'
            ? rect.width - event.clientX + rect.left < props.minWidth
            : event.clientX - rect.left < props.minWidth;
        if (isMax) {
          emit('move', 0, swipeRight, handleMouseUp);
          handleMouseUp();
          left.value = props.startPlacement === 'left' ? rect.left - 3 : rect.left + rect.width - 3;
          nextTick(() => {
            left.value = defaultLeft.value;
          });
        } else {
          const newLeft = Math.min(
            Math.max(
              props.minWidth,
              props.startPlacement === 'left' ? rect.width - event.clientX + rect.left : event.clientX - rect.left
            ),
            props.maxWidth
          );
          emit('move', newLeft, swipeRight, handleMouseUp);
          if (newLeft >= props.maxWidth) {
            handleMouseUp();
          }
          left.value = props.startPlacement === 'left' ? rect.left + rect.width - newLeft - 3 : newLeft + rect.left - 3;
        }
      }
      function handleMouseUp() {
        isMoving.value = false;
        document.body.style.cursor = '';
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.onselectstart = null;
        document.ondragstart = null;
      }
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    function handleTrigger(e: Event) {
      e.stopPropagation();
      emit('trigger', !props.isShow);
    }

    return {
      left,
      show,
      isMoving,
      handleMouseDown,
      handleTrigger,
    };
  },
  render() {
    return (
      <div
        style={{ left: this.theme !== 'normal' ? '' : `${this.left}px`, display: this.show ? 'flex' : 'none' }}
        class={['monitor-drag', this.theme, this.startPlacement]}
        onMousedown={this.handleMouseDown}
      >
        <div>
          {['line', 'line-round'].includes(this.theme) && (
            <div class={['theme-line', this.startPlacement, { 'is-show': this.isShow }]}>
              <span class='line-wrap'>
                <span
                  style={{ top: `${this.top}px` }}
                  class={['line', { 'is-moving': this.isMoving }]}
                >
                  {this.theme === 'line-round' && (
                    <div class='line-round-wrap'>
                      {[1, 2, 3, 4, 5].map(i => (
                        <span
                          key={i}
                          class={`line-round ${i === 3 ? `line-square line-round-${i}` : `line-round-${i}`}`}
                        />
                      ))}
                    </div>
                  )}
                </span>
              </span>
              {this.lineText && (
                <span
                  class='line-trigger'
                  onClick={this.handleTrigger}
                  onMousedown={e => e.stopPropagation()}
                >
                  {!this.isShow && <span class='trigger-text'>{this.lineText}</span>}
                  <i class='icon-monitor icon-arrow-left' />
                </span>
              )}
            </div>
          )}
        </div>
        {this.$slots?.default}
      </div>
    );
  },
});
