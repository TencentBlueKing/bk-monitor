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

import { type EditorOptions, type PreviewStyle, Editor } from '@toast-ui/editor';

import './viewer.scss';
// import codeSyntaxHighlight from '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight-all';
// import '@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css';
import '@toast-ui/editor/dist/toastui-editor.css';

interface IMarkdownEditorProps {
  flowchartStyle?: boolean;
  height: string;
  html: string;
  options: EditorOptions;
  previewStyle: PreviewStyle;
  value: string;
  visible: boolean;
}
@Component
export default class MarkdownEditor extends tsc<IMarkdownEditorProps> {
  editor: Editor = null;
  editorEvents: string[] = ['load', 'change', 'stateChange', 'focus', 'blur'];
  valueUpdateMethod: string[] = ['insertText', 'setValue', 'setMarkdown', 'setHtml', 'reset'];
  @Prop({ default: 'vertical' }) previewStyle: PreviewStyle;
  @Prop({ default: '500px' }) height: string;
  @Prop() value: string;
  @Prop() options: EditorOptions;
  @Prop() html: string;
  @Prop({ default: true }) visible: boolean;
  @Prop({ default: true }) flowchartStyle: boolean;

  @Watch('previewStyle')
  onPreviewStyleChange(v: PreviewStyle) {
    this.editor.changePreviewStyle(v);
  }
  @Watch('value')
  onValueChange(v: string, old: string) {
    if (v !== old && v !== this.editor.getMarkdown()) {
      this.editor.setMarkdown(v);
    }
  }
  @Watch('height')
  onHeightChange(v: string) {
    this.editor.setHeight(v);
  }

  @Watch('html')
  onHtmlChange(v: string) {
    this.editor.setHTML(v);
    this.$emit('input', this.editor.getMarkdown());
  }
  @Watch('visible')
  onVisibleChange(newValue) {
    newValue ? this.editor.show() : this.editor.hide();
  }
  mounted() {
    this.editor = new Editor({
      el: this.$el as HTMLDivElement,
      language: 'zh-cn',
      initialValue: this.value,
      initialEditType: 'markdown',
      height: this.height,
      previewStyle: this.previewStyle,
      hideModeSwitch: true,
      events: this.editorEvents.reduce((pre, key) => (pre[key] = (...args: any) => this.$emit(key, ...args)), {}),
      viewer: false,
    });
    if (this.$listeners.input) {
      this.editor.on('change', () => {
        this.$emit('input', this.editor.getMarkdown());
      });
    }
  }
  destroyed() {
    this.editorEvents.forEach(event => this.editor.off(event));
    this.editor.destroy();
  }
  invoke(methodName: string, ...args: any) {
    let result = null;
    if (this.editor[methodName]) {
      result = this.editor[methodName](...args);
      if (this.valueUpdateMethod.indexOf(methodName) > -1) {
        this.$emit('input', this.editor.getMarkdown());
      }
    }
    return result;
  }
  render() {
    return (
      <div
        ref='editor'
        class={['markdown-viewer', { 'md-veiwer-flowchart-wrap': this.flowchartStyle }]}
      />
    );
  }
}
