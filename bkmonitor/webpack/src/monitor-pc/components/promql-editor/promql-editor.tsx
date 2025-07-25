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

import { parser } from '@prometheus-io/lezer-promql';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import { throttle } from 'throttle-debounce';

import { promLanguageDefinition } from './monaco-promql';
import { completionItemProvider, language, languageConfiguration } from './promql';
import { validateQuery } from './validation';

import './promql-editor.scss';

/**
 * @description placeholder
 */
class PlaceholderWidget {
  editor = null;
  domNode = null;
  constructor(editor) {
    this.editor = editor;
    this.domNode = document.createElement('div');
    this.domNode.className = 'placeholder-widget';
    this.domNode.innerHTML = window.i18n.tc('请输入 PromQL 查询语句，Shift + Enter换行，Enter查询');
    this.editor.addOverlayWidget(this);
    this.update();
  }
  getId() {
    return 'my.placeholder.widget';
  }
  getDomNode() {
    return this.domNode;
  }
  getPosition() {
    return {
      preference: monaco.editor.OverlayWidgetPositionPreference.TOP_CENTER,
    };
  }
  update() {
    const model = this.editor.getModel();
    const isEmpty = model.getValueLength() === 0;
    this.domNode.style.display = isEmpty ? 'block' : 'none';
  }
}
function editorWillMount(monaco) {
  const languageId = promLanguageDefinition.id;
  const { aliases, extensions, mimetypes } = promLanguageDefinition;
  monaco.languages.register({ id: languageId, aliases, extensions, mimetypes });
  monaco.languages.onLanguage(languageId, () => {
    monaco.languages.setMonarchTokensProvider(languageId, language);
    monaco.languages.setLanguageConfiguration(languageId, languageConfiguration);
    monaco.languages.registerCompletionItemProvider(languageId, completionItemProvider);
  });
  return {};
}

const defalutOptions = {
  lineNumbers: 'off',
  lineDecorationsWidth: 10,
  lineNumbersMinChars: 0,
  glyphMargin: false,
  folding: false,
  minimap: {
    enabled: false,
  },
  fontSize: 14,
  fontFamily: 'Menlo, Monaco, "Courier New", monospace',
  codeLens: false,
  contextmenu: false,
  fixedOverflowWidgets: true,
  renderLineHighlightOnlyWhenFocus: true,
  overviewRulerBorder: false,
  overviewRulerLanes: 0,
  wordWrap: 'on',
  scrollBeyondLastLine: false,
  renderLineHighlight: 'none',
  scrollbar: {
    vertical: 'hidden',
    verticalScrollbarSize: 0,
    horizontal: 'hidden',
    horizontalScrollbarSize: 0,
    alwaysConsumeMouseWheel: false,
  },
  padding: {
    top: 4,
    bottom: 8,
    right: 0,
    left: 0,
  },
  suggest: () => ({
    showWords: false,
  }),
  lineHeight: 19,
  suggestFontSize: 12,
  suggestLineHeight: 19,
  cursorStyle: 'line-thin',
};
export interface IPromqlMonacoEditorProps {
  className?: null | string;
  defaultValue?: string;
  height?: string;
  isError?: boolean;
  language?: string;
  minHeight?: number;
  options?: object;
  overrideServices?: object;
  readonly?: boolean;
  theme?: null | string;
  value?: null | string;
  width?: string;
  executeQuery?: (v: boolean) => void;
  onBlur?: (value: string, hasErr: boolean) => void;
  onChange?: (v: string) => void;
  onFocus?: () => void;
  uri?: (v: any) => void;
}
@Component
export default class PromqlMonacoEditor extends tsc<IPromqlMonacoEditorProps> {
  @Ref('containerElement') readonly containerElement?: HTMLDivElement;
  @Prop({ default: 68 }) readonly minHeight: number;
  @Prop({ default: false }) readonly isError: boolean;
  @Prop({ default: null }) readonly value: null | string;
  @Prop({ default: '' }) readonly defaultValue?: string;
  @Prop({ default: 'promql' }) readonly language?: string;
  @Prop({ default: 'vs' }) readonly theme?: null | string;
  @Prop({ default: () => defalutOptions }) readonly options: object;
  @Prop({ default: () => ({}) }) readonly overrideServices?: object;
  @Prop({ default: null }) readonly className?: null | string;
  @Prop({ default: () => null }) readonly executeQuery: (v: boolean) => void;
  @Prop() readonly uri?: (v: any) => monaco.Uri;
  @Prop({ default: false }) readonly: boolean;

  editor: monaco.editor.IStandaloneCodeEditor | null = null;
  preventTriggerChangeEvent = false;

  wrapHeight = 0;
  wrapWidth = 0;

  roInstance = null;

  throttleUpdateLayout = () => {};

  created() {
    this.throttleUpdateLayout = throttle(300, this.updateLayout);
  }

  mounted() {
    this.initMonaco();
  }

  beforeDestroy() {
    this.destroyMonaco();
  }
  deactivated() {
    this.destroyMonaco();
  }

  onChange(value: string) {
    this.$emit('change', value);
  }

  /**
   * @description 编辑器事件
   */
  handleEditorDidMount() {
    this.roInstance = new ResizeObserver(entries => {
      for (const entry of entries) {
        const newW = entry.contentRect.width;
        if (this.wrapWidth !== newW) {
          this.throttleUpdateLayout();
          this.wrapWidth = newW;
        }
      }
    });
    this.roInstance.observe(this.$el);
    this.editor.onDidContentSizeChange(_event => {
      this.updateLayout();
    });
    const placeholderWidget = new PlaceholderWidget(this.editor);
    this.editor.onDidChangeModelContent(_event => {
      if (!this.preventTriggerChangeEvent) {
        this.onChange(this.editor.getValue());
      }
      placeholderWidget.update();
      const model = this.editor.getModel();
      if (!model) {
        return;
      }
      const query = model.getValue();
      const errors = validateQuery(query, query, model.getLinesContent(), parser) || [];
      const markers = errors.map(({ error, ...boundary }) => ({
        message: `${
          error ? `Error parsing "${error}"` : 'Parse error'
        }. The query appears to be incorrect and could fail to be executed.`,
        severity: monaco.MarkerSeverity.Error,
        ...boundary,
      }));
      monaco.editor.setModelMarkers(model, this.language, markers);
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
      run: (editor: monaco.editor.ICodeEditor): Promise<void> | void => {
        const suggestController = editor.getContribution('editor.contrib.suggestController') as any;
        const suggestCount = suggestController.widget.value._state || 0;
        if (suggestCount <= 0) {
          this.executeQuery(this.getLinterStatus());
        } else {
          editor.trigger('keyboard', 'acceptSelectedSuggestion', {});
        }
      },
    });
    setTimeout(() => {
      this.updateLayout();
    }, 0);
  }

  updateLayout() {
    const pixelHeight = this.editor.getContentHeight();
    const height = pixelHeight > this.minHeight ? pixelHeight : this.minHeight;
    this.editor.layout({ width: this.$el.clientWidth, height });
    this.wrapHeight = height;
  }

  /**
   * @description 初始化
   */
  initMonaco() {
    const finalValue = this.value !== null ? this.value : this.defaultValue;
    if (this.containerElement) {
      const finalOptions = { ...this.options, ...editorWillMount(monaco) };
      const modelUri = this.uri?.(monaco);
      let model = null;
      if (modelUri) {
        model = monaco.editor.getModel(modelUri);
      }
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
          ...(this.theme ? { theme: this.theme } : {}),
          readOnly: this.readonly,
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
            text: this.value,
          },
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
        ...optionsWithoutModel,
      });
    }
  }
  @Watch('options')
  onOptionsChanged() {
    if (this.editor) {
      const { model, ...optionsWithoutModel } = this.options as any;
      this.editor.updateOptions({
        ...(this.className ? { extraEditorClassName: this.className } : {}),
        ...optionsWithoutModel,
      });
    }
  }

  @Watch('theme')
  onThemeChanged() {
    if (this.editor) {
      monaco.editor.setTheme(this.theme);
    }
  }
  destroyMonaco() {
    this.editor?.dispose?.();
    monaco.editor.getModels().forEach(model => model.dispose());
    this.roInstance?.disconnect?.();
  }

  initResize(e: Event) {
    e.preventDefault();
    window.addEventListener('mousemove', this.resizeElement);
    window.addEventListener('mouseup', this.stopResize);
  }
  resizeElement(e: MouseEvent) {
    const start = this.$el.getBoundingClientRect().top;
    const mouseY = e.clientY;
    const newHeight = mouseY - start + 5;
    if (newHeight < this.minHeight) {
      this.wrapHeight = this.minHeight;
    } else {
      this.wrapHeight = newHeight;
    }
    this.editor.layout({ width: this.$el.clientWidth, height: this.wrapHeight - 2 });
  }
  stopResize() {
    window.removeEventListener('mousemove', this.resizeElement);
  }

  render() {
    return (
      <div
        style={{
          minHeight: `${this.minHeight}px`,
          height: `${this.wrapHeight <= 0 ? this.minHeight : this.wrapHeight}px`,
        }}
        class={['promql-editor-component', { 'is-error': this.isError }]}
      >
        <div
          ref='containerElement'
          class='promql-editor'
        />
        <div
          class='resize-vertical-drop'
          onMousedown={this.initResize}
        >
          <div class='lines'>
            <div class='line-1' />
            <div class='line-2' />
          </div>
        </div>
      </div>
    );
  }
}
