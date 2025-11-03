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
import * as monaco from 'monaco-editor';

import builtinFunctions from './builtinFunctions.json' with { type: 'json' };
import builtinVariables from './builtinVariables.json' with { type: 'json' };
import keywords from './keywords.json' with { type: 'json' };
import operators from './operators.json' with { type: 'json' };

type DorisField = {
  name: string;
  type: string;
  description: string;
};

monaco.languages.register({ id: 'dorisSQL' });

monaco.languages.setMonarchTokensProvider('dorisSQL', {
  /** defaultToken */
  defaultToken: '',

  /** tokenPostfix */
  tokenPostfix: '.sql',

  /** ignoreCase */
  ignoreCase: true,

  /** brackets */
  brackets: [
    { open: '[', close: ']', token: 'delimiter.square' },
    { open: '(', close: ')', token: 'delimiter.parenthesis' },
  ],

  /** keywords */
  keywords,

  /** operators */
  operators,

  /** builtinFunctions */
  builtinFunctions,

  builtinVariables,

  /** pseudoColumns */
  pseudoColumns: ['$ACTION', '$IDENTITY', '$ROWGUID', '$PARTITION'],

  /** tokenizer */
  tokenizer: {
    root: [
      { include: '@comments' },
      { include: '@whitespace' },
      { include: '@pseudoColumns' },
      { include: '@numbers' },
      { include: '@strings' },
      { include: '@complexIdentifiers' },
      { include: '@scopes' },
      [/[;,.]/, 'delimiter'],
      [/[()]/, '@brackets'],
      [
        /[\w@#$]+/,
        {
          cases: {
            '@keywords': 'keyword',
            '@operators': 'operator',
            '@builtinVariables': 'predefined',
            '@builtinFunctions': 'predefined',
            '@default': 'identifier',
          },
        },
      ],
      [/[<>=!%&+\-*/|~^]/, 'operator'],
    ],
    whitespace: [[/\s+/, 'white']],
    comments: [
      [/--+.*/, 'comment'],
      [/\/\*/, { token: 'comment.quote', next: '@comment' }],
    ],
    comment: [
      [/[^*/]+/, 'comment'],
      // Not supporting nested comments, as nested comments seem to not be standard?
      /* i.e. http://stackoverflow.com/questions/728172/are-there
            -multiline-comment-delimiters-in-sql-that-are-vendor-agnostic */
      // [/\/\*/, { token: 'comment.quote', next: '@push' }],    // nested comment not allowed :-(
      [/\*\//, { token: 'comment.quote', next: '@pop' }],
      [/./, 'comment'],
    ],
    pseudoColumns: [
      [
        /[$][A-Za-z_][\w@#$]*/,
        {
          cases: {
            '@pseudoColumns': 'predefined',
            '@default': 'identifier',
          },
        },
      ],
    ],
    numbers: [
      [/0[xX][0-9a-fA-F]*/, 'number'],
      [/[$][+-]*\d*(\.\d*)?/, 'number'],
      [/((\d+(\.\d*)?)|(\.\d+))([eE][-+]?\d+)?/, 'number'],
    ],
    strings: [
      [/N'/, { token: 'string', next: '@string' }],
      [/'/, { token: 'string', next: '@string' }],
    ],
    string: [
      [/[^']+/, 'string'],
      [/''/, 'string'],
      [/'/, { token: 'string', next: '@pop' }],
    ],
    complexIdentifiers: [
      [/\[/, { token: 'identifier.quote', next: '@bracketedIdentifier' }],
      [/"/, { token: 'identifier.quote', next: '@quotedIdentifier' }],
    ],
    bracketedIdentifier: [
      [/[^\]]+/, 'identifier'],
      [/]]/, 'identifier'],
      [/]/, { token: 'identifier.quote', next: '@pop' }],
    ],
    quotedIdentifier: [
      [/[^"]+/, 'identifier'],
      [/""/, 'identifier'],
      [/"/, { token: 'identifier.quote', next: '@pop' }],
    ],
    scopes: [
      [/BEGIN\s+(DISTRIBUTED\s+)?TRAN(SACTION)?\b/i, 'keyword'],
      [/BEGIN\s+TRY\b/i, { token: 'keyword.try' }],
      [/END\s+TRY\b/i, { token: 'keyword.try' }],
      [/BEGIN\s+CATCH\b/i, { token: 'keyword.catch' }],
      [/END\s+CATCH\b/i, { token: 'keyword.catch' }],
      [/(BEGIN|CASE)\b/i, { token: 'keyword.block' }],
      [/END\b/i, { token: 'keyword.block' }],
      [/WHEN\b/i, { token: 'keyword.choice' }],
      [/THEN\b/i, { token: 'keyword.choice' }],
    ],
  },
});

let fetchDorisFieldsFn: () => DorisField[] | undefined;

const castFieldMapFn = (item, index) => {
  if (index === 0) {
    return item;
  }

  return `['${item}']`;
};

const fetchDorisFieldsPromise = range => {
  return (fetchDorisFieldsFn?.() ?? []).map((field, _index) => {
    let insertText = field.name;
    if (field.name.indexOf('.') > 0) {
      const splitList = field.name.split('.');
      if (splitList.length > 1) {
        insertText = `CAST(${splitList.map(castFieldMapFn).join('')} AS TEXT)`;
      }
    }

    return {
      label: field.name,
      kind: monaco.languages.CompletionItemKind.Field,
      insertText,
      filterText: field.name,
      detail: field.type, // 显示字段类型
      documentation: field.description, // 显示字段描述
      range,
      sortText: 'a',
    };
  });
};

// 注册自动补全提供者
monaco.languages.registerCompletionItemProvider('dorisSQL', {
  provideCompletionItems: (model, position) => {
    const word = model.getWordUntilPosition(position);
    const range = {
      startLineNumber: position.lineNumber,
      endLineNumber: position.lineNumber,
      startColumn: word.startColumn,
      endColumn: word.endColumn,
    };

    const fieldSuggestions = fetchDorisFieldsPromise(range);
    const keywordAndFunctionSuggestions = [
      ...keywords.map((keyword, _index) => ({
        label: keyword,
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: `${keyword} `,
        filterText: keyword,
        range,
        sortText: 'b',
      })),
      ...builtinFunctions.map((func, _index) => ({
        label: func,
        filterText: func,
        kind: monaco.languages.CompletionItemKind.Function,
        insertText: `${func}($0)`,
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        range,
        sortText: 'c',
        command: {
          id: 'editor.action.triggerParameterHints',
          title: 'Trigger Parameter Hints',
        },
      })),
    ];

    const suggestions = [...fieldSuggestions, ...keywordAndFunctionSuggestions];
    return { suggestions };
  },
});

export const setDorisFields = (fn: () => DorisField[] | undefined) => {
  fetchDorisFieldsFn = fn;
};
