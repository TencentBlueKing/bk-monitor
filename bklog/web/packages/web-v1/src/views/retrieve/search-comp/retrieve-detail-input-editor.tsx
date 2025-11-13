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

import { Component, PropSync, Emit, Mixins } from 'vue-property-decorator';

import * as monaco from 'monaco-editor';

import MonacoEditor from '../../../components/collection-access/components/step-add/monaco-editor.vue';
import classDragMixin from '../../../mixins/class-drag-mixin';

import './retrieve-detail-input-editor.scss';

@Component
export default class UiQuery extends Mixins(classDragMixin) {
  @PropSync('value', { type: String, default: '*' }) propsValue: string;
  /** monaco-editor实例 */
  editor = null;
  /** 输入框最小高度 */
  collectMinHeight = 90;
  /** 当前收藏容器的高度 */
  collectHeight = 100;
  /** monaco输入框配置 */
  monacoConfig = {
    cursorBlinking: 'blink',
    acceptSuggestionOnEnter: 'off',
    acceptSuggestionOnCommitCharacter: false, // 是否提示输入
    overviewRulerBorder: false, // 是否应围绕概览标尺绘制边框
    selectOnLineNumbers: false, //
    renderLineHighlight: 'none', // 当前行高亮方式
    lineNumbers: 'off', // 左侧是否展示行
    minimap: {
      enabled: false, // 是否启用预览图
    },
    find: {
      cursorMoveOnType: false,
      seedSearchStringFromSelection: 'never',
      addExtraSpaceOnTop: false,
    },
    // 折叠
    folding: false,
    // 自动换行
    wordWrap: true,
    wrappingStrategy: 'advanced',
    fixedOverflowWidgets: false,
    scrollbar: {
      // 滚动条设置
      verticalScrollbarSize: 6, // 竖滚动条
      useShadows: true, // 失焦阴影动画
    },
    // 隐藏右上角光标的小黑点
    hideCursorInOverviewRuler: true,
    // 隐藏小尺子
    overviewRulerLanes: 0,
    renderLineHighlightOnlyWhenFocus: false,
    autoClosingBrackets: 'never',
    autoClosingDelete: 'never',
    autoClosingOvertype: 'never',
    autoClosingQuotes: 'never',
    autoSurround: 'never',
    autoIndent: 'None',
    copyWithSyntaxHighlighting: false,
    selectionHighlight: false,
    occurrencesHighlight: false,
    foldingHighlight: false,
    highlightActiveBracketPair: false,
    highlightActiveIndentation: false,
    quickSuggestions: true,
    suggestions: false,
    wordBasedSuggestions: false,
    wordBasedSuggestionsOnlySameLanguage: false,
    unicodeHighlight: {
      ambiguousCharacters: false,
    },
    autoDetectHighContrast: false,
    roundedSelection: false,
    renderWhitespace: 'none',
    renderIndentGuides: false,
    trimAutoWhitespace: false,
    renderControlCharacters: true,
    insertSpaces: false,
  };
  /** 提示样式 */
  placeholderStyle = {
    top: '1px',
    left: '10px',
    fontSize: '12px',
  };

  @Emit('focus')
  emitFocus() {}

  @Emit('input')
  emitInput(value) {
    return value;
  }

  @Emit('blur')
  emitBlur(value) {
    // 清空选中的文本高亮背景
    this.editor.setSelection({
      startLineNumber: 0,
      startColumn: 0,
      endLineNumber: 0,
      endColumn: 0,
    });
    return value;
  }

  @Emit('keydown')
  emitKeyDown(event) {
    return event;
  }

  focus() {
    this.resetCursorPosition();
    this.editor.focus();
  }

  blur() {
    (document.activeElement as any).blur();
  }

  /** 语法初始化 */
  initMonacoBeforeFun(monacoInst) {
    monacoInst.editor.defineTheme('myTheme', {
      base: 'vs',
      inherit: true,
      rules: [
        { token: 'AND-OR-color', foreground: 'FF9C01' },
        { token: 'NOT-color', foreground: 'CB2427' },
      ],
      colors: {
        'editor.foreground': '63656E', // 用户输入的基础颜色
      },
    });
    monacoInst.languages.register({ id: 'mySpecialLanguage' });
    monacoInst.languages.setMonarchTokensProvider('mySpecialLanguage', {
      // 设置语法规则
      tokenizer: {
        root: [
          [/\s+(AND|and|OR|or)\s+/g, 'AND-OR-color'],
          [/\s+(NOT)\s+/g, 'NOT-color'],
        ],
      },
    });
    return monacoInst;
  }

  /** 重置光标位置到文本末尾 */
  resetCursorPosition() {
    const model = this.editor.getModel();
    const lastLineNumber = model.getLineCount();
    const lastColumn = model.getLineMaxColumn(lastLineNumber);
    this.editor.setPosition({ lineNumber: lastLineNumber, column: lastColumn });
    this.editor.revealLine(lastLineNumber);
  }

  /** 获取monaco-editor实例 */
  getEditorInstance(editor) {
    this.editor = editor;
    // 方向键的键绑定
    const arrowKeys = [monaco.KeyCode.UpArrow, monaco.KeyCode.DownArrow];
    // 禁止方向键的默认行为
    for (const keyCode of arrowKeys) {
      this.editor.addCommand(keyCode, () => {
        // 当方向键被按下时，此函数会被调用。
        // 在这里不做任何操作，从而忽略键盘事件。
      });
    }
    this.editor.addCommand(monaco.KeyCode.Enter, () => {
      this.resetCursorPosition();
    });
  }

  render() {
    return (
      <div class='retrieve-input-editor'>
        <MonacoEditor
          placeholder-style={this.placeholderStyle}
          height={this.collectHeight}
          v-model={this.propsValue}
          font-size={12}
          init-monaco-before-fun={this.initMonacoBeforeFun}
          is-show-problem-drag={false}
          is-show-top-label={false}
          language='mySpecialLanguage'
          monaco-config={this.monacoConfig}
          placeholder={this.$t('请输入') as string}
          theme='myTheme'
          onBlur={this.emitBlur}
          onChange={this.emitInput}
          onEditorDidMount={editor => this.getEditorInstance(editor)}
          onFocus={this.emitFocus}
          onKeydown={this.emitKeyDown}
        />
        <div
          class={['drag-bottom', { 'drag-ing': this.isChanging }]}
          onMousedown={e => this.dragBegin(e, 'dragY')}
        />
      </div>
    );
  }
}
