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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import { promLanguageDefinition } from 'monaco-promql';

import { noop, processSize } from './utils';

function editorWillMount(monaco) {
  const languageId = promLanguageDefinition.id;
  monaco.languages.register(promLanguageDefinition);
  monaco.languages.onLanguage(languageId, () => {
    promLanguageDefinition.loader().then(mod => {
      monaco.languages.setMonarchTokensProvider(languageId, mod.language);
      monaco.languages.setLanguageConfiguration(languageId, mod.languageConfiguration);
      monaco.languages.registerCompletionItemProvider(languageId, mod.completionItemProvider);
    });
  });
  return {};
}
export interface IPromqlMonacoEditorProps {
  width?: string;
  height?: string;
  value?: string | null;
  defaultValue?: string;
  language?: string;
  theme?: string | null;
  options?: object;
  overrideServices?: object;
  // editorWillMount?: Function;
  editorDidMount?: Function;
  editorWillUnmount?: Function;
  onChange?: Function;
  className?: string | null;
  uri?: Function;
}
@Component
export default class PromqlMonacoEditor extends tsc<IPromqlMonacoEditorProps> {
  @Ref('containerElement') readonly containerElement?: HTMLDivElement;
  @Prop({ default: '100%' }) readonly width: string;
  @Prop({ default: '100%' }) readonly height: string;
  @Prop({ default: null }) readonly value: string | null;
  @Prop({ default: '' }) readonly defaultValue?: string;
  @Prop({ default: 'javascript' }) readonly language?: string;
  @Prop({ default: null }) readonly theme?: string | null;
  @Prop({ default: () => ({}) }) readonly options: object;
  @Prop({ default: () => ({}) }) readonly overrideServices?: object;
  // @Prop({ default: noop }) readonly editorWillMount: Function;
  @Prop({ default: noop }) readonly editorDidMount: Function;
  @Prop({ default: noop }) readonly editorWillUnmount?: Function;
  @Prop({ default: noop }) readonly onChange?: Function;
  @Prop({ default: null }) readonly className?: string | null;
  @Prop() readonly uri?: Function;

  editor: monaco.editor.IStandaloneCodeEditor | null = null;
  subscription: monaco.IDisposable | null = null;
  preventTriggerChangeEvent = false;

  get style() {
    return {
      width: processSize(this.width),
      height: processSize(this.height)
    };
  }
  handleEditorDidMount() {
    this.editorDidMount?.(this.editor, monaco);

    this.subscription = this.editor.onDidChangeModelContent(event => {
      if (!this.preventTriggerChangeEvent) {
        this.onChange(this.editor.getValue(), event);
      }
    });
  }
  handleEditorWillUnmount() {
    this.editorWillUnmount(this.editor, monaco);
  }

  initMonaco() {
    const finalValue = this.value !== null ? this.value : this.defaultValue;

    if (this.containerElement) {
      const finalOptions = { ...this.options, ...editorWillMount(monaco) };
      const modelUri = this.uri?.(monaco);
      let model = modelUri && monaco.editor.getModel(modelUri);
      if (model) {
        model.setValue(finalValue);
        monaco.editor.setModelLanguage(model, this.language);
      } else {
        model = monaco.editor.createModel(finalValue, this.language, modelUri);
      }
      this.editor = monaco.editor.create(
        this.containerElement,
        {
          model,
          ...(this.className ? { extraEditorClassName: this.className } : {}),
          ...finalOptions,
          ...(this.theme ? { theme: this.theme } : {})
        },
        this.overrideServices
      );
      this.handleEditorDidMount();
    }
  }
  mounted() {
    this.initMonaco();
    //   if (this.editor) {
    //     this.handleEditorWillUnmount();
    //     this.editor.dispose();
    //   }
    //   this.subscription.dispose();
  }

  // Use the beforeDestroy lifecycle hook instead of useEffect
  // beforeDestroy() {
  //   this.destroyMonaco();
  // }

  @Watch('value')
  onValueChanged() {
    if (this.editor) {
      if (this.value === this.editor.getValue()) {
        return;
      }

      const model = this.editor.getModel();
      this.preventTriggerChangeEvent = true;
      this.editor.pushUndoStop();
      // pushEditOperations says it expects a cursorComputer, but doesn't seem to need one.
      model.pushEditOperations(
        [],
        [
          {
            range: model.getFullModelRange(),
            text: this.value
          }
        ],
        undefined
      );
      this.editor.pushUndoStop();
      this.preventTriggerChangeEvent = false;
    }
  }

  @Watch('language')
  onLanguageChanged() {
    if (this.editor) {
      const model = this.editor.getModel();
      monaco.editor.setModelLanguage(model, this.language);
    }
  }
  @Watch('className')
  onClassChanged() {
    if (this.editor) {
      const { model, ...optionsWithoutModel } = this.options as any;
      this.editor.updateOptions({
        ...(this.className ? { extraEditorClassName: this.className } : {}),
        ...optionsWithoutModel
      });
    }
  }
  @Watch('options')
  onOptionsChanged() {
    if (this.editor) {
      const { model, ...optionsWithoutModel } = this.options as any;
      this.editor.updateOptions({
        ...(this.className ? { extraEditorClassName: this.className } : {}),
        ...optionsWithoutModel
      });
    }
  }

  @Watch('width')
  onWidthChanged() {
    this.editor?.layout();
  }
  @Watch('height')
  onHeightChanged() {
    this.editor?.layout();
  }
  @Watch('theme')
  onThemeChanged() {
    if (this.editor) {
      monaco.editor.setTheme(this.theme);
    }
  }
  destroyMonaco() {
    this.editor?.dispose?.();
    this.subscription?.dispose?.();
  }

  render() {
    return (
      <div
        ref='containerElement'
        style={this.style}
        class='react-monaco-editor-container'
      />
    );
  }
}
