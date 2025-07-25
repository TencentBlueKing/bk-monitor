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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type Viewer, Editor } from '@toast-ui/editor';
import codeSyntaxHighlight from '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight-all';

import fixUrlPlugin from './fixUrlPlugin';

import type { EditorPlugin } from '@toast-ui/editor/types/editor';

import './viewer.scss';
import '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css';
import '@toast-ui/editor/dist/toastui-editor.css';
import 'prismjs/themes/prism.css';

interface IMarkdowViewerProps {
  flowchartStyle?: boolean;
  height?: number | string;
  value: string;
}
@Component
export default class MarkdowViewer extends tsc<IMarkdowViewerProps> {
  @Prop() height: string;
  @Prop() value: string;
  @Prop() flowchartStyle: boolean;

  editor: Viewer = null;
  editorEvents: string[] = ['load', 'change', 'focus', 'blur'];

  @Watch('value')
  onValueChange(val: string, preVal: string) {
    if (val !== preVal) {
      this.editor.destroy();
      this.createEditor();
    }
  }

  mounted() {
    this.createEditor();
  }
  createEditor() {
    const eventOption = {};
    this.editorEvents.forEach(event => {
      eventOption[event] = (...args: any) => {
        this.$emit(event, ...args);
      };
    });
    this.editor = Editor.factory({
      el: this.$refs.viewer as HTMLElement,
      events: eventOption,
      initialValue: this.value,
      height: this.height,
      viewer: true,
      plugins: [fixUrlPlugin as EditorPlugin, codeSyntaxHighlight],
    });
  }
  destroyed() {
    this.editorEvents.forEach(event => this.editor.off(event));
    this.editor.destroy();
  }

  invoke(methodName: string, ...args: any) {
    let result = null;
    if (this.editor[methodName]) {
      result = this.editor[methodName](...args);
    }
    return result;
  }
  render() {
    return (
      <div
        ref='viewer'
        class={['markdown-viewer', { 'md-veiwer-flowchart-wrap': this.flowchartStyle }]}
      />
    );
  }
}
