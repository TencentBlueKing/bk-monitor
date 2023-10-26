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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { autocompletion, CompletionContext, completionKeymap, CompletionResult } from '@codemirror/autocomplete';
import { closeBrackets, closeBracketsKeymap } from '@codemirror/closebrackets';
import { defaultKeymap, insertNewlineAndIndent } from '@codemirror/commands';
import { commentKeymap } from '@codemirror/comment';
import { history, historyKeymap } from '@codemirror/history';
import { indentOnInput, syntaxTree } from '@codemirror/language';
import { Diagnostic, lintKeymap } from '@codemirror/lint';
import { bracketMatching } from '@codemirror/matchbrackets';
import { highlightSelectionMatches, searchKeymap } from '@codemirror/search';
import { Compartment, EditorState, Prec } from '@codemirror/state';
import { EditorView, highlightSpecialChars, keymap, placeholder, ViewUpdate } from '@codemirror/view';
import { PromQLExtension } from 'codemirror-promql';
import { CompleteStrategy, newCompleteStrategy } from 'codemirror-promql/dist/esm/complete';

import { promqlHighlighter, theme } from './theme';

import './promql-editor.scss';

const promqlExtension = new PromQLExtension();
const dynamicConfigCompartment = new Compartment();
interface IPromqlEditorProps {
  value?: string;
  readonly?: boolean;
  executeQuery?: (hasError?: boolean) => void;
}
interface IProqlEditorEvent {
  onChange: string;
  onBlur: (v: string, hasError?: boolean) => void;
  onFocus: void;
}
export class HistoryCompleteStrategy implements CompleteStrategy {
  private complete: CompleteStrategy;
  private queryHistory: string[];
  constructor(complete: CompleteStrategy, queryHistory: string[]) {
    this.complete = complete;
    this.queryHistory = queryHistory;
  }

  promQL(context: CompletionContext): Promise<CompletionResult | null> | CompletionResult | null {
    return Promise.resolve(this.complete.promQL(context)).then(res => {
      const { state, pos } = context;
      const tree = syntaxTree(state).resolve(pos, -1);
      const start = res !== null ? res.from : tree.from;

      if (start !== 0) {
        return res;
      }

      const historyItems: CompletionResult = {
        from: start,
        to: pos,
        options: this.queryHistory.map(q => ({
          label: q.length < 80 ? q : q.slice(0, 76).concat('...'),
          detail: 'past query',
          apply: q,
          info: q.length < 80 ? undefined : q
        })),
        span: /^[a-zA-Z0-9_:]+$/
      };

      if (res !== null) {
        historyItems.options = historyItems.options.concat(res.options);
      }
      return historyItems;
    });
  }
}
@Component
export default class PromqlEditor extends tsc<IPromqlEditorProps, IProqlEditorEvent> {
  @Ref('editorInstance') editorInstanceRef?: HTMLDivElement;
  @Prop({ type: String, default: '' }) value?: string;
  @Prop({ type: Function }) executeQuery?: (hasError?: boolean) => void;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  instance: EditorView | null = null;
  mounted() {
    promqlExtension.activateCompletion(true);
    promqlExtension.activateLinter(true);
    promqlExtension.setComplete({
      completeStrategy: new HistoryCompleteStrategy(
        // newCompleteStrategy({
        //   remote: { url: 'http://demo.robustperception.io:9090' }
        // }),
        newCompleteStrategy({}),
        []
      )
    });
    const dynamicConfig = [promqlHighlighter, promqlExtension.asExtension()];
    if (this.instance) {
      this.instance.dispatch(
        this.instance.state.update({
          effects: dynamicConfigCompartment.reconfigure(dynamicConfig)
        })
      );
      return;
    }
    const startState = EditorState.create({
      doc: this.value,
      extensions: [
        theme,
        highlightSpecialChars(),
        history(),
        EditorState.allowMultipleSelections.of(true),
        indentOnInput(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        highlightSelectionMatches(),
        EditorView.lineWrapping,
        keymap.of([
          ...closeBracketsKeymap,
          ...defaultKeymap,
          ...searchKeymap,
          ...historyKeymap,
          ...commentKeymap,
          ...completionKeymap,
          ...lintKeymap
        ]),
        placeholder(window.i18n.tc('Shift + Enter换行，Enter查询')),
        dynamicConfigCompartment.of(dynamicConfig),
        // This keymap is added without precedence so that closing the autocomplete dropdown
        // via Escape works without blurring the editor.
        keymap.of([
          {
            key: 'Escape',
            run: (v: EditorView): boolean => {
              v.contentDOM.blur();
              return false;
            }
          }
        ]),
        Prec.override(
          keymap.of([
            {
              key: 'Enter',
              run: (): boolean => {
                this.executeQuery?.(this.getLinterStatus());
                return true;
              }
            },
            {
              key: 'Shift-Enter',
              run: insertNewlineAndIndent
            }
          ])
        ),
        EditorView.updateListener.of((update: ViewUpdate): void => {
          const newVal = update.state.doc.toString();
          if (this.value !== newVal) this.$emit('change', newVal);
        })
      ]
    });
    const view = new EditorView({
      state: startState,
      parent: this.editorInstanceRef
    });
    view.contentDOM.addEventListener('blur', this.handleBlur);
    view.contentDOM.addEventListener('focus', this.handleFocus);
    this.instance = view;
    if (this.readonly) {
      view.contentDOM.removeAttribute('contenteditable');
    }
  }
  beforeDestroy() {
    this.instance?.contentDOM.removeEventListener('blur', this.handleBlur);
    this.instance?.contentDOM.removeEventListener('focus', this.handleFocus);
    this.instance?.destroy?.();
  }
  /**
   * @description: 获取是否语法错误
   * @param {*}
   * @return {*}
   */
  getLinterStatus() {
    let hasError = false;
    if (this.instance) {
      const lintFunc = promqlExtension.getLinter().promQL()(this.instance) as Diagnostic[];
      hasError = lintFunc?.length > 0;
    }
    return hasError;
  }
  /**
   * @description: 失焦后触发
   * @param {*}
   * @return {*}
   */
  handleBlur() {
    return this.$emit('blur', this.value, this.getLinterStatus());
  }

  /**
   * @description: 聚焦
   * @param {*}
   * @return {*}
   */
  handleFocus() {
    this.$emit('focus');
  }
  render() {
    return (
      <div class='promql-editor'>
        <div
          class='promql-editor-instance'
          ref='editorInstance'
        ></div>
      </div>
    );
  }
}
