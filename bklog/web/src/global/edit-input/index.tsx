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

import { defineComponent, ref, nextTick, onMounted, onBeforeUnmount } from 'vue';

import './index.scss';

export default defineComponent({
  name: 'EditInput',
  emits: ['change', 'delete'],
  props: {
    value: {
      type: String,
      required: true,
    },
    showDelete: {
      type: Boolean,
      default: true,
    },
    maxWidth: {
      type: Number,
      default: 200,
    },
    maxHeight: {
      type: Number,
      default: 200,
    },
    resize: {
      type: String,
      default: 'none',
      validator: (value: string) => {
        return ['none', 'vertical', 'horizontal', 'both', 'inherit'].includes(value);
      },
    },
  },
  setup(props, { emit }) {
    const isEditMode = ref(false);
    const editValue = ref('');
    const containerRef = ref<HTMLDivElement | null>(null);
    const textareaRef = ref<HTMLTextAreaElement | null>(null);
    const editContainerRef = ref<HTMLDivElement | null>(null);
    const isFinishingEdit = ref(false); // 防止重复调用 finishEdit
    const isEnterKeyPressed = ref(false); // 标记是否通过 Enter 键完成编辑
    // 标记是否正在输入法组合过程中
    const isComposing = ref(false);

    /**
     * 进入编辑模式
     */
    const enterEditMode = () => {
      if (isEditMode.value) return;

      isEditMode.value = true;
      editValue.value = props.value;
      isEnterKeyPressed.value = false; // 重置标志
      isFinishingEdit.value = false; // 重置标志

      nextTick(() => {
        if (containerRef.value && textareaRef.value && editContainerRef.value) {
          const rect = containerRef.value.getBoundingClientRect();
          // 使用固定定位，保持原位置，但增加一些内边距
          const padding = 8; // 上下各 4px padding
          const minWidth = Math.max(rect.width, 120);

          editContainerRef.value.style.width = `${minWidth}px`;
          editContainerRef.value.style.left = `${rect.left + window.scrollX}px`;
          editContainerRef.value.style.top = `${rect.top + window.scrollY}px`;

          // 调整 textarea 高度以适应内容
          textareaRef.value.style.height = 'auto';
          const scrollHeight = textareaRef.value.scrollHeight;
          const minHeight = Math.max(rect.height, 22);
          const calculatedHeight = Math.max(scrollHeight + padding, minHeight);
          // 应用 maxHeight 限制
          const finalHeight = Math.min(calculatedHeight, props.maxHeight);
          textareaRef.value.style.height = `${Math.min(scrollHeight, props.maxHeight - padding)}px`;
          editContainerRef.value.style.height = `${finalHeight}px`;

          textareaRef.value.focus();
          textareaRef.value.select();
        }
      });
    };

    /**
     * 完成编辑
     */
    const finishEdit = () => {
      if (!isEditMode.value) {
        return;
      }

      if (isFinishingEdit.value) {
        return;
      }

      isFinishingEdit.value = true;
      const newValue = editValue.value.trim();
      const oldValue = props.value;

      if (newValue !== oldValue) {
        emit('change', newValue);
      }

      isEditMode.value = false;
      isFinishingEdit.value = false;
      isEnterKeyPressed.value = false;
    };

    /**
     * 取消编辑
     */
    const cancelEdit = () => {
      isEditMode.value = false;
      editValue.value = props.value;
    };

    /**
     * 处理键盘事件
     */
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        // 如果正在输入法组合过程中，不处理Enter事件
        if (e.isComposing || isComposing.value) {
          return;
        }
        e.preventDefault();
        e.stopPropagation();

        // 确保 editValue 是最新的（从 textarea 读取）
        if (textareaRef.value) {
          editValue.value = textareaRef.value.value;
        }

        isEnterKeyPressed.value = true;
        // 使用 nextTick 确保在 blur 事件之前完成
        nextTick(() => {
          finishEdit();
        });
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        cancelEdit();
      }
    };

    // 输入法组合开始
    const handleCompositionStart = () => {
      isComposing.value = true;
    };

    // 输入法组合结束
    const handleCompositionEnd = () => {
      isComposing.value = false;
    };

    /**
     * 处理删除
     */
    const handleDelete = (e: MouseEvent) => {
      e.stopPropagation();
      emit('delete');
    };

    /**
     * 处理点击外部区域
     */
    const handleClickOutside = (e: MouseEvent) => {
      if (isEditMode.value && editContainerRef.value && !editContainerRef.value.contains(e.target as Node)) {
        finishEdit();
      }
    };

    onMounted(() => {
      document.addEventListener('click', handleClickOutside);
    });

    onBeforeUnmount(() => {
      document.removeEventListener('click', handleClickOutside);
    });

    return () => (
      <div class="bklog-edit-input-wrapper">
        <div
          ref={containerRef}
          class={['edit-input-item', { 'is-edit-mode': isEditMode.value }]}
          style={{ maxWidth: `${props.maxWidth}px` }}
          onDblclick={enterEditMode}
        >
          <span class="edit-input-text">{props.value}</span>
          {props.showDelete && (
            <i
              class="bklog-icon bklog-close"
              onClick={handleDelete}
            ></i>
          )}
        </div>

        {isEditMode.value && (
          <div
            ref={editContainerRef}
            class="edit-input-edit-container"
            onClick={(e) => e.stopPropagation()}
          >
            <textarea
              ref={textareaRef}
              class='edit-input-textarea'
              data-resize={props.resize}
              style={{ "--resize": props.resize }}
              value={editValue.value}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                editValue.value = target.value;
                // 自动调整高度
                if (editContainerRef.value) {
                  target.style.height = 'auto';
                  const scrollHeight = target.scrollHeight;
                  const padding = 8; // 上下各 4px padding
                  const minHeight = 22;
                  const calculatedHeight = Math.max(scrollHeight + padding, minHeight);
                  // 应用 maxHeight 限制
                  const finalHeight = Math.min(calculatedHeight, props.maxHeight);
                  target.style.height = `${Math.min(scrollHeight, props.maxHeight - padding)}px`;
                  editContainerRef.value.style.height = `${finalHeight}px`;
                }
              }}
              onKeydown={handleKeyDown}
              onCompositionstart={handleCompositionStart}
              onCompositionend={handleCompositionEnd}
              onBlur={() => {
                // 确保 editValue 是最新的（从 textarea 读取）
                if (textareaRef.value) {
                  editValue.value = textareaRef.value.value;
                }

                // 如果已经通过 Enter 键完成编辑，则不再处理 blur 事件
                // 使用 setTimeout 确保在 Enter 键处理之后检查
                setTimeout(() => {
                  if (!isEnterKeyPressed.value && isEditMode.value) {
                    finishEdit();
                  }
                }, 10); // 增加延迟，确保 Enter 键处理完成
              }}
            />
          </div>
        )}
      </div>
    );
  },
});

