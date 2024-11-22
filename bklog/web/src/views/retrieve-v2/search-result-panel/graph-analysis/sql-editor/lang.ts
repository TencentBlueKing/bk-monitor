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
import { Range } from 'monaco-editor';

type DorisField = {
  name: string;
  type: string;
  description: string;
};

// 假设这些是Doris的关键字和函数示例
const dorisKeywords = [
  'SELECT',
  'FROM',
  'WHERE',
  'INSERT',
  'UPDATE',
  'DELETE',
  'CREATE',
  'DROP',
  'ALTER',
  'TABLE',
  'DATABASE',
  'VIEW',
  'INDEX',
  'JOIN',
  'ON',
  'GROUP BY',
  'ORDER BY',
  'LIMIT',
  'OFFSET',
  'UNION',
  'ALL',
  'DISTINCT',
];

const dorisFunctions = [
  'SUM',
  'AVG',
  'COUNT',
  'MIN',
  'MAX',
  'CONCAT',
  'LENGTH',
  'SUBSTRING',
  'NOW',
  'CURDATE',
  'DATEDIFF',
  'IF',
  'COALESCE',
  'CAST',
  'CONVERT',
];

monaco.languages.register({ id: 'dorisSQL' });

monaco.languages.setMonarchTokensProvider('dorisSQL', {
  keywords: dorisKeywords,
  functions: dorisFunctions,

  tokenizer: {
    root: [
      [
        /[a-zA-Z_]\w*/,
        {
          cases: {
            '@keywords': 'keyword',
            '@functions': 'type',
            '@default': 'identifier',
          },
        },
      ],
      { include: '@whitespace' },
      [/[()]/, '@brackets'],
      [/[;,.]/, 'delimiter'],
      [/\d+/, 'number'],
      [/".*?"/, 'string'],
      [/'[^']*'/, 'string'],
    ],
    whitespace: [
      [/\s+/, 'white'],
      [/--.*$/, 'comment'],
      [/\/\*.*\*\//, 'comment'],
    ],
  },
});

let fetchDorisFieldsFn: () => DorisField[] | undefined = undefined;

const fetchDorisFieldsPromise = position => {
  return (fetchDorisFieldsFn?.() ?? []).map((field, index) => ({
    label: field.name,
    kind: monaco.languages.CompletionItemKind.Field,
    insertText: field.name,
    detail: field.type, // 显示字段类型
    documentation: field.description, // 显示字段描述
    range: new Range(position.lineNumber, position.column, position.lineNumber, position.column),
    sortText: `1_${index}_${field.name}`,
  }));
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

    const fieldSuggestions = fetchDorisFieldsPromise(position);
    const keywordAndFunctionSuggestions = [
      ...dorisKeywords.map((keyword, index) => ({
        label: keyword,
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: keyword + ' ',
        range: range,
        sortText: `2_${index}_${keyword}`,
      })),
      ...dorisFunctions.map((func, index) => ({
        label: func,
        kind: monaco.languages.CompletionItemKind.Function,
        insertText: `${func}($0)`,
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        range: range,
        sortText: `3_${index}_${func}`,
        command: {
          id: 'editor.action.triggerParameterHints',
          title: 'Trigger Parameter Hints',
        },
      })),
    ];
    return { suggestions: [...fieldSuggestions, ...keywordAndFunctionSuggestions] };
  },
});

export const setDorisFields = (fn: () => DorisField[] | undefined) => {
  fetchDorisFieldsFn = fn;
};
