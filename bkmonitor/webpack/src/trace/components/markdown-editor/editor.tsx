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

import { type PropType, defineComponent, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue';

import { type EditorOptions, type PreviewStyle, Editor } from '@toast-ui/editor';

import './viewer.scss';
// import codeSyntaxHighlight from '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight-all';
// import '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css';
import '@toast-ui/editor/dist/toastui-editor.css';

export default defineComponent({
  name: 'MarkdownEditor',
  props: {
    previewStyle: {
      type: String as PropType<PreviewStyle>,
      default: 'vertical',
    },
    height: {
      type: String,
      default: '500px',
    },
    value: {
      type: String,
      default: '',
    },
    options: {
      type: Object as PropType<EditorOptions>,
      default: () => ({}),
    },
    html: {
      type: String,
      default: '',
    },
    visible: {
      type: Boolean,
      default: true,
    },
    flowchartStyle: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['input', 'load', 'change', 'focus', 'blur'],
  setup(props, { emit }) {
    const editorRef = useTemplateRef<HTMLElement>('editorRef');
    const editor = shallowRef<Editor>(null);
    const editorEvents: string[] = ['load', 'change', 'focus', 'blur'];
    const valueUpdateMethod: string[] = ['insertText', 'setValue', 'setMarkdown', 'setHtml', 'reset'];

    watch(
      () => props.previewStyle,
      v => {
        editor.value.changePreviewStyle(v);
      }
    );

    watch(
      () => props.value,
      (v, old) => {
        if (v !== old && v !== editor.value.getMarkdown()) {
          editor.value.setMarkdown(v);
        }
      }
    );

    watch(
      () => props.height,
      v => {
        editor.value.setHeight(v);
      }
    );

    watch(
      () => props.html,
      v => {
        editor.value.setHTML(v);
        emit('input', editor.value.getMarkdown());
      }
    );

    watch(
      () => props.visible,
      v => {
        v ? editor.value.show() : editor.value.hide();
      }
    );

    const invoke = (methodName: string, ...args: any) => {
      let result = null;
      if (editor.value[methodName]) {
        result = editor.value[methodName](...args);
        if (valueUpdateMethod.indexOf(methodName) > -1) {
          emit('input', editor.value.getMarkdown());
        }
      }
      return result;
    };

    onMounted(() => {
      editor.value = new Editor({
        el: editorRef.value,
        language: 'zh-cn',
        initialValue: props.value,
        initialEditType: 'markdown',
        height: props.height,
        previewStyle: props.previewStyle,
        hideModeSwitch: true,
        events: editorEvents.reduce((pre, key) => {
          pre[key] = (...args: any) => emit(key, ...args);
          return pre;
        }, {}),
        viewer: false,
      });
      editor.value.on('change', () => {
        emit('input', editor.value.getMarkdown());
      });
    });

    onBeforeUnmount(() => {
      for (const event of editorEvents) {
        editor.value.off(event);
      }
      editor.value.destroy();
    });

    return {
      invoke,
    };
  },
  render() {
    return (
      <div
        ref='editorRef'
        class={['markdown-viewer', { 'md-veiwer-flowchart-wrap': this.flowchartStyle }]}
      />
    );
  },
});
