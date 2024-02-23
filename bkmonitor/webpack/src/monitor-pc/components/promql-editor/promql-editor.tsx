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

const defalutOptions = {
  lineNumbers: 'off',
  minimap: {
    enabled: false
  },
  fontSize: 12,
  renderLineHighlightOnlyWhenFocus: true,
  overviewRulerBorder: false,
  extraEditorClassName: 'promql-monaco-editor-component',
  automaticLayout: true
};
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
  executeQuery?: Function;
  className?: string | null;
  uri?: Function;
  onBlur?: (value: string, hasErr: boolean) => void;
  onFocus?: () => void;
}
@Component
export default class PromqlMonacoEditor extends tsc<IPromqlMonacoEditorProps> {
  @Ref('containerElement') readonly containerElement?: HTMLDivElement;
  @Prop({ default: '100%' }) readonly width: string;
  @Prop({ default: '100%' }) readonly height: string;
  @Prop({ default: null }) readonly value: string | null;
  @Prop({ default: '' }) readonly defaultValue?: string;
  @Prop({ default: 'promql' }) readonly language?: string;
  @Prop({ default: null }) readonly theme?: string | null;
  @Prop({ default: () => defalutOptions }) readonly options: object;
  @Prop({ default: () => ({}) }) readonly overrideServices?: object;
  @Prop({ default: noop }) readonly editorDidMount: Function;
  @Prop({ default: noop }) readonly editorWillUnmount?: Function;
  @Prop({ default: null }) readonly className?: string | null;
  @Prop({ default: () => null }) readonly executeQuery: Function;
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

  mounted() {
    this.initMonaco();
  }

  beforeDestroy() {
    this.destroyMonaco();
  }

  onChange(value: string) {
    this.$emit('change', value);
  }

  /**
   * @description 编辑器事件
   */
  handleEditorDidMount() {
    this.editorDidMount?.(this.editor, monaco);
    this.subscription = this.editor.onDidChangeModelContent(_event => {
      if (!this.preventTriggerChangeEvent) {
        this.onChange(this.editor.getValue());
      }
    });
    this.editor.onDidBlurEditorText(() => {
      this.$emit('blur', this.editor.getValue(), this.getLinterStatus());
    });
    this.editor.onDidFocusEditorText(() => {
      this.$emit('focus');
    });
    this.editor.addAction({
      keybindings: [monaco.KeyCode.Enter],
      id: 'enter',
      label: 'enter',
      run: (editor: monaco.editor.ICodeEditor): void | Promise<void> => {
        const suggestController = editor.getContribution('editor.contrib.suggestController') as any;
        const suggestCount = suggestController.widget.value._state || 0;
        if (suggestCount <= 0) {
          const position = editor.getPosition();
          editor.executeEdits('', [
            {
              range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
              text: ''
            }
          ]);
          this.executeQuery(this.getLinterStatus());
        } else {
          editor.trigger('keyboard', 'acceptSelectedSuggestion', {});
        }
      }
    });
    // monaco.languages.registerCodeActionProvider(this.language, {
    //   provideCodeActions(model) {
    //     const markers = monaco.editor.getModelMarkers({ resource: model.uri });
    //     const actions = [];

    //     markers.forEach(marker => {
    //       actions.push({
    //         title: `Syntax Error: ${marker.message}`,
    //         diagnostics: [marker],
    //         kind: 'quickfix'
    //       });
    //     });

    //     return {
    //       actions,
    //       dispose: () => {}
    //     };
    //   }
    // });
  }
  handleEditorWillUnmount() {
    this.editorWillUnmount(this.editor, monaco);
  }

  /**
   * @description 初始化
   */
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

  /**
   * @description 判断是否语法错误
   */
  getLinterStatus() {
    let hasError = false;
    if (this.editor) {
      const model = this.editor.getModel();
      const markers = monaco.editor.getModelMarkers({ resource: model.uri });
      hasError = !!markers.length;
    }
    return hasError;
  }

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
