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

import { defineComponent, ref, onMounted, onUnmounted, watch, type PropType } from 'vue';

import { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
import { EditorState } from '@codemirror/state';
import { placeholder, keymap, highlightSpecialChars, drawSelection } from '@codemirror/view';
import { EditorView } from 'codemirror';

import { jumpLinkSyntaxHighlighting } from './jump-link-highlighter';

import './jump-link-editor.scss';

export default defineComponent({
  name: 'JumpLinkEditor',
  props: {
    value: {
      type: String as PropType<string>,
      default: '',
    },
    placeholder: {
      type: String as PropType<string>,
      default: '',
    },
  },
  emits: ['change', 'blur'],
  setup(props, { emit }) {
    const editorRef = ref<HTMLDivElement>();
    let editorView: EditorView | null = null;

    // 创建编辑器状态
    const createState = (doc: string) => {
      const extensions = [
        // 基础编辑功能
        history(),
        drawSelection(),
        highlightSpecialChars(),

        // placeholder
        placeholder(props.placeholder),

        // 键盘映射
        keymap.of([...defaultKeymap, ...historyKeymap]),

        // 更新监听器
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const newValue = update.state.doc.toString();
            emit('change', newValue);
          }
          if (update.focusChanged && !update.view.hasFocus) {
            // 编辑器失去焦点时，触发 blur 事件
            emit('blur');
          }
        }),

        // 变量语法高亮
        jumpLinkSyntaxHighlighting(),

        // 主题样式
        EditorView.theme({
          '&': {
            fontSize: '12px',
            height: '32px',
            border: '1px solid transparent',
            borderRadius: '2px',
            backgroundColor: '#fff',
            background: 'transparent',
          },
          '&.cm-focused': {
            outline: 'none',
            borderColor: '#3A84FF',
          },
          '.cm-content': {
            padding: '6px 10px 6px 8px',
            minHeight: '32px',
            lineHeight: '20px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          },
          '.cm-scroller': {
            overflow: 'hidden',
          },
          '.cm-gutters': {
            display: 'none',
          },
          '.cm-placeholder': {
            color: '#C4C6CC',
            fontStyle: 'normal',
            fontSize: '12px',
          },
        }),
      ];

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

    onMounted(() => {
      initEditor();
    });

    onUnmounted(() => {
      destroyEditor();
    });

    return {
      editorRef,
    };
  },
  render() {
    return (
      <div
        ref='editorRef'
        class='jump-link-codemirror-editor'
      ></div>
    );
  },
});
