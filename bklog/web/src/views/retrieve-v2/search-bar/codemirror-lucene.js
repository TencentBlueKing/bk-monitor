import { EditorState } from '@codemirror/state';
import { basicSetup, EditorView } from 'codemirror';
// import { syntaxHighlighting, HighlightStyle } from '@codemirror/language';
// import { tags as t } from '@lezer/highlight';
import { sql } from '@codemirror/lang-sql';
import { lineNumbers } from "@codemirror/gutter";

// // 定义 Lucene 语法高亮
// const luceneHighlightStyle = HighlightStyle.define([
//   { tag: tags.keyword, color: "#cc7832" },
//   { tag: tags.operator, color: "#a9b7c6" },
//   { tag: tags.string, color: "#6a8759" },
//   { tag: tags.variableName, color: "#9876aa" },
//   { tag: tags.number, color: "#6897bb" },
//   { tag: tags.comment, color: "#808080" },
//   { tag: tags.bracket, color: "#a9b7c6" },
//   { tag: tags.wildcard, color: "#ff0000" }
// ]);

// 自定义 SQL 扩展以支持 Lucene
function lucene() {
  const luceneKeywords = ['AND', 'OR', 'NOT'];
  const luceneOperators = ['+', '-', '*', '?'];
  return sql({
    dialect: {
      keywords: luceneKeywords,
      builtin: [],
      types: [],
      operators: luceneOperators,
      builtinFunctions: [],
      builtinVariables: [],
      builtinTables: [],
    },
    languageData: {
      commentTokens: { line: '//' },
    },
  });
}

export default ({ target, onChange, onFocusChange, value }) => {
  const state = EditorState.create({
    doc: value,
    extensions: [
      basicSetup.filter(ext => ext != lineNumbers),
      // lucene()
      // syntaxHighlighting(luceneHighlightStyle),
      // EditorView.lineWrapping,
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
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value },
    });
  };

  return { state, view, appendText, setValue };
};
