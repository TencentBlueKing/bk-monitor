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
import { defineComponent, ref, onMounted, onUnmounted, watch, PropType } from 'vue';

import { autocompletion, completionKeymap, closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete';
import { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
import { bracketMatching, indentOnInput } from '@codemirror/language';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { EditorState } from '@codemirror/state';
import { placeholder } from '@codemirror/view';
import {
  keymap,
  highlightSpecialChars,
  drawSelection,
  dropCursor,
  rectangularSelection,
  crosshairCursor,
} from '@codemirror/view';
import { EditorView } from 'codemirror';

import { grepSyntaxHighlighting } from './grep-highlighter';

import './grep-cli-editor.scss';

export default defineComponent({
  name: 'GrepCliEditor',
  props: {
    value: {
      type: String as PropType<string>,
      default: '',
    },
    placeholder: {
      type: String as PropType<string>,
      default: '-- INSERT --',
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    height: {
      type: String,
      default: '34px',
    },
    autoHeight: {
      type: Boolean,
      default: false,
    },
    minHeight: {
      type: String,
      default: '34px',
    },
    maxHeight: {
      type: String,
      default: '200px',
    },
    enableSyntaxHighlight: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['change', 'enter'],
  setup(props, { emit }) {
    const editorRef = ref<HTMLDivElement>();
    const currentHeight = ref(props.height);
    let editorView: EditorView | null = null;

    // 创建编辑器状态
    const createState = (doc: string) => {
      const initialHeight = props.autoHeight ? currentHeight.value : props.height;

      // 计算8行的最大高度
      // 字体大小14px，行高1.4，8行 = 14 * 1.4 * 8 = 156.8px
      // 加上上下padding各6px = 168.8px，约170px
      const maxLines = 8;
      const fontSize = 14;
      const lineHeight = 1.4;
      const verticalPadding = 12; // 上下各6px
      const maxHeightForLines = `${Math.ceil(fontSize * lineHeight * maxLines + verticalPadding)}px`;

      // 手动配置扩展，不包含行号
      const extensions = [
        keymap.of([
          {
            key: 'Enter',
            mac: 'Enter',
            run: view => {
              emit('enter', view.state.doc.toString());
              return true;
            },
          },
        ]),
        // 基础编辑功能
        history(),
        drawSelection(),
        dropCursor(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        rectangularSelection(),
        crosshairCursor(),
        highlightSelectionMatches(),
        highlightSpecialChars(),

        // 添加 placeholder 扩展
        placeholder(props.placeholder),

        // 使用默认键盘映射，不做特殊处理
        keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...completionKeymap]),

        // 更新监听器
        EditorView.updateListener.of(update => {
          if (update.docChanged) {
            const newValue = update.state.doc.toString();
            emit('change', newValue);
          }
        }),

        // 主题样式
        EditorView.theme({
          '&': {
            fontSize: '12px',
            height: initialHeight,
            maxHeight: maxHeightForLines,
          },
          '.cm-content': {
            padding: '6px 8px',
            minHeight: initialHeight,
            lineHeight: '1.4',
            fontFamily: 'Monaco, Menlo, Ubuntu Mono, Consolas, source-code-pro, monospace',
          },
          '.cm-focused': {
            outline: 'none',
          },
          '.cm-editor': {
            borderRadius: '2px',
            border: 'none',
            backgroundColor: 'transparent',
            height: 'auto',
            maxHeight: maxHeightForLines,
          },
          '.cm-scroller': {
            overflow: 'auto',
            maxHeight: maxHeightForLines,
          },
          // 确保没有行号相关样式
          '.cm-gutters': {
            display: 'none',
          },
          // 自定义 placeholder 样式
          '.cm-placeholder': {
            color: '#999',
            fontStyle: 'italic',
            fontFamily: 'Monaco, Menlo, Ubuntu Mono, Consolas, source-code-pro, monospace',
            fontSize: '12px',
          },
          // 自定义滚动条样式
          '.cm-scroller::-webkit-scrollbar': {
            width: '6px',
            height: '6px',
          },
          '.cm-scroller::-webkit-scrollbar-track': {
            backgroundColor: '#f1f1f1',
            borderRadius: '3px',
          },
          '.cm-scroller::-webkit-scrollbar-thumb': {
            backgroundColor: '#c1c1c1',
            borderRadius: '3px',
          },
          '.cm-scroller::-webkit-scrollbar-thumb:hover': {
            backgroundColor: '#a8a8a8',
          },
        }),
      ];

      // 根据 enableSyntaxHighlight 属性决定是否启用语法高亮
      if (props.enableSyntaxHighlight) {
        extensions.push(grepSyntaxHighlighting());
      }

      return EditorState.create({
        doc,
        extensions,
      });
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
      newValue => {
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

    // 监听自适应高度属性变化
    watch(
      () => [props.autoHeight, props.minHeight, props.maxHeight],
      () => {
        if (editorRef.value) {
          editorRef.value.style.height = props.height;
          currentHeight.value = props.height;
        }
      },
    );

    // 监听 placeholder 变化
    watch(
      () => props.placeholder,
      () => {
        if (editorView) {
          // 重新创建编辑器以应用新的 placeholder
          const currentValue = editorView.state.doc.toString();
          const cursorPos = editorView.state.selection.main.head;

          destroyEditor();

          const state = createState(currentValue);
          editorView = new EditorView({
            state,
            parent: editorRef.value!,
          });

          // 恢复光标位置
          editorView.dispatch({
            selection: { anchor: cursorPos, head: cursorPos },
          });
        }
      },
    );

    // 获取编辑器实例（供外部调用）
    const getEditor = () => editorView;

    // 聚焦编辑器
    const focus = () => {
      if (editorView) {
        editorView.focus();
      }
    };

    // 设置选中内容
    const setSelection = (from: number, to?: number) => {
      if (editorView) {
        editorView.dispatch({
          selection: { anchor: from, head: to ?? from },
        });
      }
    };

    // 获取当前高度
    const getCurrentHeight = () => currentHeight.value;

    onMounted(() => {
      initEditor();
    });

    onUnmounted(() => {
      destroyEditor();
    });

    return {
      editorRef,
      currentHeight,
      getEditor,
      focus,
      setSelection,
      getCurrentHeight,
    };
  },
  render() {
    return (
      <div
        ref='editorRef'
        style={{ height: this.autoHeight ? this.currentHeight : this.height }}
        class={['grep-cli-codemirror-editor', { 'auto-height': this.autoHeight }]}
      ></div>
    );
  },
});
