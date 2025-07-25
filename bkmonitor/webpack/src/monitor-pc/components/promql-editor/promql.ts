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

import { languages } from 'monaco-editor';
// noinspection JSUnusedGlobalSymbols
export const languageConfiguration = {
  // the default separators except `@$`
  wordPattern: /(-?\d*\.\d\w*)|([^`~!#%^&*()\-=+[{\]}\\|;:'",.<>/?\s]+)/g,
  // Not possible to make comments in PromQL syntax
  comments: {
    lineComment: '#',
  },
  brackets: [
    // ['{', '}'],
    // ['[', ']'],
    // ['(', ')']
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
    { open: '<', close: '>' },
  ],
  folding: {},
};
// PromQL Aggregation Operators
// (https://prometheus.io/docs/prometheus/latest/querying/operators/#aggregation-operators)
const aggregations = [
  'sum',
  'min',
  'max',
  'avg',
  'group',
  'stddev',
  'stdvar',
  'count',
  'count_values',
  'bottomk',
  'topk',
  'quantile',
];
const duration = ['1m', '5m', '10m', '30m', '1h', '1d'];
// PromQL functions
const functions = [
  'abs',
  'absent',
  'absent_over_time',
  'acos',
  'acosh',
  'asin',
  'asinh',
  'atan',
  'atanh',
  'avg_over_time',
  'ceil',
  'changes',
  'clamp',
  'clamp_max',
  'clamp_min',
  'cos',
  'cosh',
  'count_over_time',
  'days_in_month',
  'day_of_month',
  'day_of_week',
  'deg',
  'delta',
  'deriv',
  'exp',
  'floor',
  'histogram_quantile',
  'holt_winters',
  'hour',
  'idelta',
  'increase',
  'irate',
  'label_replace',
  'label_join',
  'last_over_time',
  'ln',
  'log10',
  'log2',
  'max_over_time',
  'min_over_time',
  'minute',
  'month',
  'pi',
  'predict_linear',
  'present_over_time',
  'quantile_over_time',
  'rad',
  'rate',
  'resets',
  'round',
  'scalar',
  'sgn',
  'sin',
  'sinh',
  'sort',
  'sort_desc',
  'sqrt',
  'stddev_over_time',
  'stdvar_over_time',
  'sum_over_time',
  'tan',
  'tanh',
  'time',
  'timestamp',
  'vector',
  'year',
];
// PromQL specific functions: Aggregations over time
// (https://prometheus.io/docs/prometheus/latest/querying/functions/#aggregation_over_time)
const aggregationsOverTime = [];
for (let _i = 0, aggregations_1 = aggregations; _i < aggregations_1.length; _i++) {
  const agg = aggregations_1[_i];
  aggregationsOverTime.push(`${agg}_over_time`);
}
// PromQL vector matching + the by and without clauses
// (https://prometheus.io/docs/prometheus/latest/querying/operators/#vector-matching)
const vectorMatching = ['on', 'ignoring', 'group_right', 'group_left', 'by', 'without'];
// Produce a regex matching elements : (elt1|elt2|...)
const vectorMatchingRegex = `(${vectorMatching.reduce(function (prev, curr) {
  return `${prev}|${curr}`;
})})`;
// PromQL Operators
// (https://prometheus.io/docs/prometheus/latest/querying/operators/)
const operators = ['+', '-', '*', '/', '%', '^', '==', '!=', '>', '<', '>=', '<=', 'and', 'or', 'unless'];
// PromQL offset modifier
// (https://prometheus.io/docs/prometheus/latest/querying/basics/#offset-modifier)
const offsetModifier = ['offset'];
// Merging all the keywords in one list
const keywords = [
  ...aggregations.map(str => ({ keyword: str, type: 'aggregations' })),
  ...functions.map(str => ({ keyword: str, type: 'functions' })),
  ...aggregationsOverTime.map(str => ({ keyword: str, type: 'aggregationsOverTime' })),
  ...vectorMatching.map(str => ({ keyword: str, type: 'vectorMatching' })),
  ...offsetModifier.map(str => ({ keyword: str, type: 'offsetModifier' })),
  ...duration.map(str => ({ keyword: str, type: 'duration' })),
];
// const keywords = aggregations
//   .concat(functions)
//   .concat(aggregationsOverTime)
//   .concat(vectorMatching)
//   .concat(offsetModifier);
// noinspection JSUnusedGlobalSymbols
export const language = {
  ignoreCase: false,
  defaultToken: '',
  tokenPostfix: '.promql',
  keywords: keywords.map(item => item.keyword),
  operators,
  vectorMatching: vectorMatchingRegex,
  // we include these common regular expressions
  symbols: /[=><!~?:&|+\-*/^%]+/,
  escapes: /\\(?:[abfnrtv\\"']|x[0-9A-Fa-f]{1,4}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})/,
  digits: /\d+(_+\d+)*/,
  octaldigits: /[0-7]+(_+[0-7]+)*/,
  binarydigits: /[0-1]+(_+[0-1]+)*/,
  hexdigits: /[[0-9a-fA-F]+(_+[0-9a-fA-F]+)*/,
  integersuffix: /(ll|LL|u|U|l|L)?(ll|LL|u|U|l|L)?/,
  floatsuffix: /[fFlL]?/,
  // The main tokenizer for our languages
  tokenizer: {
    root: [
      // 'by', 'without' and vector matching
      [/@vectorMatching\s*(?=\()/, 'type', '@clauses'],
      // labels
      [/[a-z_]\w*(?=\s*(=|!=|=~|!~))/, 'tag'],
      // comments
      [/(^#.*$)/, 'comment'],
      // all keywords have the same color
      [
        /[a-zA-Z_]\w*/,
        {
          cases: {
            '@keywords': 'type',
            '@default': 'identifier',
          },
        },
      ],
      // strings
      [/"([^"\\]|\\.)*$/, 'string.invalid'],
      [/'([^'\\]|\\.)*$/, 'string.invalid'],
      [/"/, 'string', '@string_double'],
      [/'/, 'string', '@string_single'],
      [/`/, 'string', '@string_backtick'],
      // whitespace
      { include: '@whitespace' },
      // delimiters and operators
      [/[{}()[\]]/, '@brackets'],
      [/[<>](?!@symbols)/, '@brackets'],
      [
        /@symbols/,
        {
          cases: {
            '@operators': 'delimiter',
            '@default': '',
          },
        },
      ],
      // numbers
      [/\d+[smhdwy]/, 'number'],
      [/\d*\d+[eE]([-+]?\d+)?(@floatsuffix)/, 'number.float'],
      [/\d*\.\d+([eE][-+]?\d+)?(@floatsuffix)/, 'number.float'],
      [/0[xX][0-9a-fA-F']*[0-9a-fA-F](@integersuffix)/, 'number.hex'],
      [/0[0-7']*[0-7](@integersuffix)/, 'number.octal'],
      [/0[bB][0-1']*[0-1](@integersuffix)/, 'number.binary'],
      [/\d[\d']*\d(@integersuffix)/, 'number'],
      [/\d(@integersuffix)/, 'number'],
    ],
    string_double: [
      [/[^\\"]+/, 'string'],
      [/@escapes/, 'string.escape'],
      [/\\./, 'string.escape.invalid'],
      [/"/, 'string', '@pop'],
    ],
    string_single: [
      [/[^\\']+/, 'string'],
      [/@escapes/, 'string.escape'],
      [/\\./, 'string.escape.invalid'],
      [/'/, 'string', '@pop'],
    ],
    string_backtick: [
      [/[^\\`$]+/, 'string'],
      [/@escapes/, 'string.escape'],
      [/\\./, 'string.escape.invalid'],
      [/`/, 'string', '@pop'],
    ],
    clauses: [
      [/[^(,)]/, 'tag'],
      [/\)/, 'identifier', '@pop'],
    ],
    whitespace: [[/[ \t\r\n]+/, 'white']],
  },
};

function kindFn(type: string) {
  if (type === 'functions' || type === 'aggregations' || type === 'aggregationsOverTime') {
    return languages.CompletionItemKind.Variable;
  }
  if (type === 'duration') {
    return languages.CompletionItemKind.Unit;
  }
  return languages.CompletionItemKind.Keyword;
}
// noinspection JSUnusedGlobalSymbols
export const completionItemProvider = {
  provideCompletionItems(_model, _position, context) {
    // To simplify, we made the choice to never create automatically the parenthesis behind keywords
    // It is because in PromQL, some keywords need parenthesis behind, some don't, some can have but it's optional.
    let list = [];
    if (context.triggerCharacter === '[') {
      list = keywords.filter(item => item.type === 'duration');
    } else {
      list = keywords;
    }
    const maxIndexDigits = list.length.toString().length;
    const suggestions = list.map((item, index) => {
      return {
        label: item.keyword,
        kind: kindFn(item.type),
        insertText: item.keyword,
        insertTextRules: languages.CompletionItemInsertTextRule.InsertAsSnippet,
        sortText: index.toString().padStart(maxIndexDigits, '0'),
      };
    });
    return { suggestions };
  },
  triggerCharacters: ['{', ',', '[', '(', '=', '~', ' ', '"'],
};
