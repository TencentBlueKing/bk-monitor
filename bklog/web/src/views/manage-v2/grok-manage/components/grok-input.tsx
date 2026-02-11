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
import { defineComponent, ref, onMounted, onUnmounted, watch, type PropType, nextTick } from 'vue';

import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete';
import { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
import { bracketMatching, indentOnInput } from '@codemirror/language';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { EditorState } from '@codemirror/state';
import {
  placeholder as cmPlaceholder,
  keymap,
  highlightSpecialChars,
  drawSelection,
  dropCursor,
  rectangularSelection,
  crosshairCursor,
} from '@codemirror/view';

import { EditorView } from 'codemirror';

import BkLogPopover from '@/components/bklog-popover';

import GrokPopoverList from './grok-popover-list';
import { grokSyntaxHighlighting } from './grok-highlighter';
import type { GrokPopoverListExpose, IGrokItem } from '../types';

import './grok-input.scss';

export default defineComponent({
  name: 'GrokInput',
  props: {
    value: {
      type: String,
      default: '',
    },
    // 是否启用 Grok 模式（%{} 匹配、语法高亮、自动补全等功能）
    grokMode: {
      type: Boolean,
      default: false,
    },
    type: {
      type: String as PropType<'text' | 'textarea'>,
      default: 'text',
    },
    placeholder: {
      type: String,
      default: '',
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    // type 为 textarea 时是否显示滚动条
    showScrollbar: {
      type: Boolean,
      default: true,
    },
    // 弹窗定位模式：'editor' 相对于编辑器容器定位，'cursor' 相对于光标位置定位
    popoverPosition: {
      type: String as PropType<'editor' | 'cursor'>,
      default: 'editor',
    },
  },
  emits: ['input', 'change', 'enter', 'focus', 'blur'],
  setup(props, { emit, expose }) {
    const editorRef = ref<HTMLDivElement>();
    const popoverRef = ref<any>();
    const grokListRef = ref<GrokPopoverListExpose>();
    let editorView: EditorView | null = null;

    // 弹窗状态（仅 grokMode 启用时使用）
    const popoverVisible = ref(false);
    // 当前 %{} 中的关键字（仅 grokMode 启用时使用）
    const currentKeyword = ref('');
    // 当前光标在 %{} 中的位置信息（仅 grokMode 启用时使用）
    const currentGrokRange = ref<{ start: number; end: number } | null>(null);

    // 解析光标位置所在的 %{} 范围和关键字
    const parseGrokAtCursor = (text: string, cursorPos: number) => {
      // 查找光标前最近的 %{
      let startPos = -1;
      for (let i = cursorPos - 1; i >= 0; i--) {
        if (text[i] === '{' && i > 0 && text[i - 1] === '%') {
          startPos = i - 1;
          break;
        }
        // 如果遇到 } 说明不在 %{} 内
        if (text[i] === '}') {
          break;
        }
      }

      if (startPos === -1) return null;

      // 查找配对的 }
      let endPos = -1;
      for (let i = startPos + 2; i < text.length; i++) {
        if (text[i] === '}') {
          endPos = i;
          break;
        }
        // 遇到换行或新的 %{ 说明当前 %{ 未闭合
        if (text[i] === '\n' || (text[i] === '%' && i + 1 < text.length && text[i + 1] === '{')) {
          // 未闭合，endPos 为当前光标位置
          endPos = cursorPos;
          break;
        }
      }

      // 如果没找到闭合的 }，设置为当前文本末尾
      if (endPos === -1) {
        endPos = text.length;
      }

      // 提取 {} 内的关键字
      const keyword = text.substring(startPos + 2, endPos);

      return {
        start: startPos,
        end: endPos + 1, // 包含 }
        keyword,
        cursorInRange: cursorPos >= startPos + 2 && cursorPos <= endPos,
      };
    };

    // 创建编辑器状态
    const createState = (doc: string) => {
      const isTextarea = props.type === 'textarea';

      const extensions = [
        // 基础编辑功能
        history(),
        drawSelection(),
        dropCursor(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        rectangularSelection(),
        crosshairCursor(),
        highlightSelectionMatches(),
        highlightSpecialChars(),
        EditorView.lineWrapping,

        // Grok 模式下启用括号匹配高亮、自动补全（括号自动闭合等）
        ...(props.grokMode ? [bracketMatching(), closeBrackets(), autocompletion()] : []),

        // placeholder
        cmPlaceholder(props.placeholder),

        // 键盘映射
        keymap.of([
          // Grok 弹窗导航支持（仅 grokMode 启用时生效）
          {
            key: 'ArrowDown',
            run: () => {
              if (props.grokMode && popoverVisible.value && grokListRef.value) {
                grokListRef.value.handleKeydown(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
                return true;
              }
              return false;
            },
          },
          {
            key: 'ArrowUp',
            run: () => {
              if (props.grokMode && popoverVisible.value && grokListRef.value) {
                grokListRef.value.handleKeydown(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
                return true;
              }
              return false;
            },
          },
          {
            key: 'Enter',
            run: () => {
              if (props.grokMode && popoverVisible.value && grokListRef.value) {
                grokListRef.value.handleKeydown(new KeyboardEvent('keydown', { key: 'Enter' }));
                return true;
              }
              return false;
            },
          },
          // Grok 模式下启用括号闭合和自动补全的键盘映射
          ...(props.grokMode ? closeBracketsKeymap : []),
          ...defaultKeymap,
          ...searchKeymap,
          ...historyKeymap,
          ...(props.grokMode ? completionKeymap : []),
        ]),

        // 单行模式下 Enter 键行为
        ...(isTextarea
          ? []
          : [
            keymap.of([
              {
                key: 'Enter',
                run: (view) => {
                  emit('enter', view.state.doc.toString());
                  return true;
                },
              },
            ]),
          ]),

        // 更新监听器
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const newValue = update.state.doc.toString();
            emit('input', newValue);
            emit('change', newValue);

            // 检查是否输入了 % 并自动补全 {}
            handleAutoComplete(update);
          }

          // 监听选区变化，更新弹窗状态
          if (update.selectionSet || update.docChanged) {
            // 传入 docChanged 参数，用于区分是光标移动还是内容变化
            handleSelectionChange(update.state, update.docChanged);
          }
        }),

        // 主题样式
        EditorView.theme({
          '&': {
            fontSize: '12px',
          },
          '.cm-content': {
            color: '#63656e',
            padding: isTextarea ? '5px 10px' : '0 10px 0 8px',
            lineHeight: isTextarea ? '1.5' : '30px',
            fontFamily: 'inherit',
          },
          '.cm-focused': {
            outline: 'none',
          },
          '.cm-editor': {
            borderRadius: '2px',
            border: 'none',
            backgroundColor: 'transparent',
            height: '100%',
          },
          '.cm-scroller': {
            overflow: isTextarea ? (props.showScrollbar ? 'auto' : 'hidden') : 'hidden',
          },
          '.cm-gutters': {
            display: 'none',
          },
          '.cm-placeholder': {
            color: '#c4c6cc',
            fontFamily: 'inherit',
            fontSize: '12px',
          },
          '.cm-line': {
            padding: '0',
          },
        }),
      ];

      // Grok 模式下启用语法高亮
      if (props.grokMode) {
        extensions.push(grokSyntaxHighlighting());
      }

      // 只读模式
      if (props.readonly || props.disabled) {
        extensions.push(EditorState.readOnly.of(true));
      }

      return EditorState.create({
        doc,
        extensions,
      });
    };

    // 处理自动补全 - 输入 % 后自动补全 {}
    const handleAutoComplete = (update: any) => {
      if (!props.grokMode) return;

      const changes = update.changes;
      let inserted = '';
      changes.iterChanges((fromA: number, toA: number, fromB: number, toB: number, text: any) => {
        inserted = text.toString();
      });

      // 如果只插入了 %，自动补全 {}
      if (inserted === '%') {
        const cursorPos = update.state.selection.main.head;
        const text = update.state.doc.toString();

        // 检查 % 后面是否已经有 {
        if (text[cursorPos] !== '{') {
          // 插入 {} 并将光标移动到 {} 之间
          nextTick(() => {
            if (editorView) {
              editorView.dispatch({
                changes: { from: cursorPos, to: cursorPos, insert: '{}' },
                selection: { anchor: cursorPos + 1 },
              });

              // 显示弹窗
              showPopover();
            }
          });
        }
      }
    };

    // 处理选区变化
    const handleSelectionChange = (state: EditorState, docChanged: boolean) => {
      if (!props.grokMode) return;

      const cursorPos = state.selection.main.head;
      const text = state.doc.toString();

      const grokInfo = parseGrokAtCursor(text, cursorPos);

      if (grokInfo && grokInfo.cursorInRange) {
        const wasInGrokRange = currentGrokRange.value !== null;

        currentGrokRange.value = { start: grokInfo.start, end: grokInfo.end };

        // 只有以下情况才更新关键字（触发搜索）:
        // 1. 文档内容发生变化（输入/删除）
        // 2. 光标首次进入 %{} 范围
        if (docChanged || !wasInGrokRange) {
          currentKeyword.value = grokInfo.keyword;
        }

        // 显示弹窗
        showPopover();
      } else {
        hidePopover();
      }
    };

    // 显示弹窗
    const showPopover = () => {
      popoverVisible.value = true;
      popoverRef.value?.show?.();
    };

    // 隐藏弹窗
    const hidePopover = () => {
      if (popoverVisible.value) {
        popoverVisible.value = false;
        popoverRef.value?.hide?.();
        currentGrokRange.value = null;
        currentKeyword.value = '';
      }
    };

    // 处理选择 Grok 项
    const handleGrokSelect = (item: IGrokItem) => {
      if (!editorView || !currentGrokRange.value) return;

      const { start } = currentGrokRange.value;
      const text = editorView.state.doc.toString();

      // 查找当前 %{} 的结束位置
      let endPos = start + 2;
      for (let i = start + 2; i < text.length; i++) {
        if (text[i] === '}') {
          endPos = i + 1;
          break;
        }
      }

      // 替换整个 %{xxx} 为 %{选中的name}
      const newContent = `%{${item.name}}`;
      editorView.dispatch({
        changes: { from: start, to: endPos, insert: newContent },
        selection: { anchor: start + newContent.length },
      });

      hidePopover();
      editorView.focus();
    };

    // 初始化编辑器
    const initEditor = () => {
      if (!editorRef.value) return;

      const state = createState(props.value);
      editorView = new EditorView({
        state,
        parent: editorRef.value,
      });
    };

    // 销毁编辑器
    const destroyEditor = () => {
      if (editorView) {
        editorView.destroy();
        editorView = null;
      }
    };

    // 监听 value 变化
    watch(
      () => props.value,
      (newValue) => {
        if (editorView && editorView.state.doc.toString() !== newValue) {
          const transaction = editorView.state.update({
            changes: {
              from: 0,
              to: editorView.state.doc.length,
              insert: newValue,
            },
          });
          editorView.dispatch(transaction);
        }
      },
    );

    // 监听 grokMode 变化，重建编辑器以应用/移除 Grok 相关功能
    watch(
      () => props.grokMode,
      (newVal, oldVal) => {
        if (newVal === oldVal) return;

        // grokMode 变化时重建编辑器
        const currentValue = editorView?.state.doc.toString() || props.value;
        destroyEditor();
        nextTick(() => {
          initEditor();
          // 恢复之前的内容
          if (editorView && currentValue) {
            editorView.dispatch({
              changes: {
                from: 0,
                to: editorView.state.doc.length,
                insert: currentValue,
              },
            });
          }
        });
      },
    );

    // 聚焦编辑器
    const focus = () => {
      if (editorView) {
        editorView.focus();
      }
    };

    // 获取编辑器实例
    const getEditor = () => editorView;

    onMounted(() => {
      // 使用 nextTick 确保 DOM 已经渲染完成
      nextTick(() => {
        initEditor();
      });
    });

    onUnmounted(() => {
      destroyEditor();
    });

    expose({
      focus,
      getEditor,
    });

    // 渲染 CodeMirror 编辑器
    const renderEditor = () => {
      // Grok 模式：需要 Popover 包裹以显示 Grok 列表
      if (props.grokMode) {
        const renderPopoverContent = () => (
          <GrokPopoverList
            ref={grokListRef}
            keyword={currentKeyword.value}
            visible={popoverVisible.value}
            on-select={handleGrokSelect}
          />
        );

        return (
          <BkLogPopover
            ref={popoverRef}
            contentClass='grok-input-popover-content'
            trigger='manual'
            options={{
              placement: 'bottom-start',
              hideOnClick: true,
              appendTo: document.body,
              theme: 'bklog-basic-light',
              arrow: false,
              ...(props.popoverPosition === 'cursor' ? {
                popperOptions: {
                  modifiers: [
                    {
                      name: 'offset',
                      options: {
                        offset: ({ reference }: { reference: { x: number; y: number; height: number } }) => {
                          // 光标定位模式：计算光标位置相对于编辑器容器的偏移
                          if (!editorView) return [0, 0];
                          const cursorPos = editorView.state.selection.main.head;
                          const cursorCoords = editorView.coordsAtPos(cursorPos);
                          if (!cursorCoords) return [0, 0];
                          // 计算光标位置与参考元素的偏移量
                          const offsetX = cursorCoords.left - reference.x;
                          const offsetY = cursorCoords.bottom - reference.y - reference.height + 4;
                          return [offsetX, offsetY];
                        },
                      },
                    },
                  ],
                },
              } : {}),
            } as any}
            {...{
              scopedSlots: { content: renderPopoverContent },
            }}
          >
            {/* 编辑器容器 - 作为弹窗定位的目标元素 */}
            <div
              ref={editorRef}
              class={[
                'grok-input-editor',
                `grok-input-editor--${props.type}`,
                'bklog-v3-popover-tag',
                {
                  'is-disabled': props.disabled,
                  'is-readonly': props.readonly,
                  'hide-scrollbar': props.type === 'textarea' && !props.showScrollbar,
                },
              ]}
            ></div>
          </BkLogPopover>
        );
      }

      // 非 Grok 模式：直接渲染编辑器
      return (
        <div
          ref={editorRef}
          class={[
            'grok-input-editor',
            `grok-input-editor--${props.type}`,
            {
              'is-disabled': props.disabled,
              'is-readonly': props.readonly,
              'hide-scrollbar': props.type === 'textarea' && !props.showScrollbar,
            },
          ]}
        ></div>
      );
    };

    return () => (
      <div
        class={[
          'grok-input-wrapper',
          {
            'hide-scrollbar': props.type === 'textarea' && !props.showScrollbar,
          },
        ]}
      >
        {renderEditor()}
      </div>
    );
  },
});
