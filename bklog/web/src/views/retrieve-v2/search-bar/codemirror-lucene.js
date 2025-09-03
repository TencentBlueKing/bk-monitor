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
import { sql } from '@codemirror/lang-sql';
import { EditorState, EditorSelection } from '@codemirror/state';
import { keymap, EditorView, Decoration } from '@codemirror/view';
import { minimalSetup } from 'codemirror';
import { debounce } from 'lodash-es';

const notKeywordDecorator = Decoration.mark({
  class: 'cm-not-keyword', // 这将添加一个cm-not-keyword类名
});

function highlightNotKeywords() {
  return EditorView.decorations.of(view => {
    const decorations = [];
    const text = view.state.doc.toString();
    const regex = /\bNOT\b/g;

    let match;
    while ((match = regex.exec(text)) !== null) {
      decorations.push(notKeywordDecorator.range(match.index, match.index + match[0].length));
    }

    return Decoration.set(decorations);
  });
}

export default ({ target, onChange, onFocusChange, onFocusPosChange, onKeyEnter, value, stopDefaultKeyboard }) => {
  // 键盘操作事件处理函数
  // 这里通过回调函数处理，如果 stopDefaultKeyboard 返回true，则会阻止编辑器默认的监盘行为
  const stopKeyboardList = ['ArrowUp', 'ArrowDown'].map(keymap => ({
    key: keymap,
    run: () => {
      return stopDefaultKeyboard?.() ?? false;
    },
  }));

  const debouncedTrack = debounce(update => {
    onChange?.(update.state.doc);
    onFocusPosChange?.(update.state);
  });

  const state = EditorState.create({
    doc: value,
    extensions: [
      keymap.of([
        {
          key: 'Enter',
          mac: 'Enter',
          run: view => {
            return onKeyEnter?.(view) ?? false;
          },
        },
        ...stopKeyboardList,
      ]),
      minimalSetup,
      sql(),
      highlightNotKeywords(),
      EditorView.lineWrapping,

      EditorView.focusChangeEffect.of((state, focusing) => {
        onFocusChange?.(state, focusing);
      }),
      EditorView.updateListener.of(update => {
        if (update.selectionSet) {
          onFocusPosChange?.(update.state);
        }
        if (update.docChanged) {
          debouncedTrack(update);
        }
      }),
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

  const setValue = (value, from = 0, to = undefined) => {
    const currentValue = view.state.doc.toString();
    if (currentValue === value) {
      return;
    }

    // 处理替换全部内容的情况
    if (to === Infinity) {
      const docLength = view.state.doc.length;
      view.dispatch({
        changes: { from: 0, to: docLength, insert: value },
        selection: EditorSelection.cursor(value.length),
      });
      return;
    }

    // 处理插入新内容的情况
    if (to === undefined) {
      // 确保 from 不超过文档长度
      const safeFrom = Math.min(from, view.state.doc.length);
      view.dispatch({
        changes: { from: safeFrom, insert: value },
        selection: EditorSelection.cursor(safeFrom + value.length),
        userEvent: 'input',
      });
      return;
    }

    // 处理替换指定范围内容的情况
    if (typeof to === 'number') {
      // 确保 from 和 to 在有效范围内
      const docLength = view.state.doc.length;
      const safeFrom = Math.min(from, docLength);
      const safeTo = Math.min(to, docLength);

      // 如果 from 大于等于 to，当作插入处理
      if (safeFrom >= safeTo) {
        view.dispatch({
          changes: { from: safeFrom, insert: value },
          selection: EditorSelection.cursor(safeFrom + value.length),
          userEvent: 'input',
        });
        return;
      }

      view.dispatch({
        changes: { from: safeFrom, to: safeTo, insert: value },
        selection: EditorSelection.cursor(safeFrom + value.length),
        userEvent: 'input',
      });
    }
  };

  const setFocus = focusPosition => {
    if (!view) return;

    view.focus();
    // 确保光标位置在有效范围内
    const docLength = view.state.doc.length;
    const pos = typeof focusPosition === 'number' ? Math.min(Math.max(0, focusPosition), docLength) : 0;

    view.dispatch({
      selection: EditorSelection.cursor(pos),
      userEvent: 'focus',
    });
  };

  const getValue = () => {
    return view.state.doc.toString() ?? '*';
  };

  return {
    state,
    view,
    appendText,
    setValue,
    setFocus,
    getValue,
  };
};
