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
import { lineNumbers } from '@codemirror/gutter';
import { sql } from '@codemirror/lang-sql';
import { EditorState } from '@codemirror/state';
import { keymap } from '@codemirror/view';
import { basicSetup, EditorView } from 'codemirror';

export default ({ target, onChange, onFocusChange, onKeyEnter, value }) => {
  const state = EditorState.create({
    doc: value,
    extensions: [
      keymap.of([
        {
          key: 'Enter',
          run: view => {
            onKeyEnter?.(view);
            return true;
          },
        },
      ]),
      basicSetup.filter(ext => ext != lineNumbers),
      sql(),
      EditorView.lineWrapping,
      EditorView.focusChangeEffect.of((_, focusing) => {
        onFocusChange?.(focusing);
      }),
      EditorView.updateListener.of(update => {
        if (update.docChanged) {
          onChange?.(update.state.doc);
        }
      }),
      // luceneLanguage
    ],
  });

  const view = new EditorView({
    state,
    parent: target,
  });

  const appendText = value => {
    view.dispatch({
      changes: { from: view.state.doc.length, insert: value },
    });
  };

  const setValue = value => {
    if (view.state.doc.toString() === value) {
      return;
    }

    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value },
    });

    setTimeout(() => {
      view.dispatch({
        selection: {
          anchor: view.state.doc.length,
          head: view.state.doc.length,
        },
      });
    }, 300);
  };

  return { state, view, appendText, setValue };
};
