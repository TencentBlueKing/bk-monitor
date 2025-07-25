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
import { ref as deepRef, defineComponent, onBeforeUnmount, onMounted, watch } from 'vue';

import { type Viewer, Editor } from '@toast-ui/editor';
import codeSyntaxHighlight from '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight-all';

import fixUrlPlugin from './fixUrlPlugin';

import type { EditorPlugin } from '@toast-ui/editor/types/editor';

import './viewer.scss';
import '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css';
import '@toast-ui/editor/dist/toastui-editor.css';
import 'prismjs/themes/prism.css';

interface MarkdownViewerProps {
  flowchartStyle?: boolean;
  height?: number | string;
  value: string;
}

export default defineComponent<MarkdownViewerProps>({
  name: 'MarkdownViewer',
  props: {
    height: [String, Number],
    value: { type: String, required: true },
    flowchartStyle: Boolean,
  },
  emits: ['load', 'change', 'focus', 'blur'],
  setup(props, { emit, attrs }) {
    const viewerRef = deepRef<HTMLElement | null>(null);
    const editor = deepRef<null | Viewer>(null);
    const editorEvents = ['load', 'change', 'focus', 'blur'];

    const createEditor = () => {
      const eventOption: Record<string, (...args: any[]) => void> = {};
      editorEvents.map(event => {
        eventOption[event] = (...args: any[]) => {
          emit(event, ...args);
        };
      });
      editor.value = Editor.factory({
        el: viewerRef.value as HTMLElement,
        events: eventOption,
        initialValue: props.value,
        height: props.height,
        viewer: true,
        plugins: [fixUrlPlugin as EditorPlugin, codeSyntaxHighlight],
      });
    };

    watch(
      () => props.value,
      (val, preVal) => {
        if (val !== preVal && editor.value) {
          editor.value.destroy();
          createEditor();
        }
      }
    );

    onMounted(() => {
      createEditor();
    });

    onBeforeUnmount(() => {
      if (editor.value) {
        editorEvents.forEach(event => editor.value!.off(event));
        editor.value.destroy();
      }
    });

    // 提供外部调用
    const invoke = (methodName: string, ...args: any[]) => {
      if (editor.value && typeof (editor.value as any)[methodName] === 'function') {
        return (editor.value as any)[methodName](...args);
      }
      return null;
    };

    return () => (
      <div
        ref={viewerRef}
        class={['markdown-viewer', { 'md-veiwer-flowchart-wrap': props.flowchartStyle }]}
        {...attrs}
      />
    );
  },
});
