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

/* Highlight.js PromQL 语法高亮插件 */
export function PromQlLanguage(hljs) {
  // 聚合操作符
  const AGGREGATION_OPERATORS = [
    'sum',
    'min',
    'max',
    'avg',
    'stddev',
    'stdvar',
    'count',
    'count_values',
    'bottomk',
    'topk',
    'quantile',
  ];

  // 函数列表
  const FUNCTIONS = [
    'abs',
    'absent',
    'ceil',
    'changes',
    'clamp_max',
    'clamp_min',
    'count_scalar',
    'day_of_month',
    'day_of_week',
    'days_in_month',
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
    'label_join',
    'label_replace',
    'ln',
    'log2',
    'log10',
    'minute',
    'month',
    'predict_linear',
    'rate',
    'resets',
    'round',
    'scalar',
    'sort',
    'sort_desc',
    'sqrt',
    'time',
    'timestamp',
    'vector',
    'year',
    'avg_over_time',
    'min_over_time',
    'max_over_time',
    'sum_over_time',
    'count_over_time',
    'quantile_over_time',
    'stddev_over_time',
    'stdvar_over_time',
  ];

  // 关键字
  const KEYWORDS = [
    'by',
    'without',
    'group_left',
    'group_right',
    'ignoring',
    'on',
    'offset',
    'bool',
    'and',
    'or',
    'unless',
    'ALERT',
    'IF',
    'FOR',
    'LABELS',
    'ANNOTATIONS',
  ];

  // 运算符
  const OPERATORS = [
    '+',
    '-',
    '*',
    '/',
    '%',
    '^',
    '==',
    '!=',
    '>',
    '<',
    '>=',
    '<=',
    '=',
    '~',
    '!~',
    'and',
    'or',
    'unless',
  ];

  return {
    name: 'PromQL',
    case_insensitive: false,
    keywords: {
      keyword: KEYWORDS,
      built_in: FUNCTIONS,
    },
    contains: [
      // 注释
      hljs.HASH_COMMENT_MODE,

      // 字符串
      hljs.QUOTE_STRING_MODE,
      hljs.APOS_STRING_MODE,

      // 数字
      {
        className: 'number',
        variants: [
          { begin: '\\b(0b[01]+)\\b' },
          { begin: '\\b(0x[0-9a-fA-F]+)\\b' },
          { begin: '(-?)\\b(\\d+(\\.\\d*)?|\\.\\d+)([eE][-+]?\\d+)?\\b' },
        ],
      },

      // 时间单位
      {
        className: 'duration',
        begin: '\\b\\d+[smhdwy]\\b',
        relevance: 10,
      },

      // 运算符
      {
        className: 'operator',
        begin: OPERATORS.map(op => (op.length > 1 ? `\\b${op}\\b` : `\\${op}`)).join('|'),
        relevance: 0,
      },

      // 聚合操作符带by/without子句（最高优先级）
      {
        className: 'aggregation',
        begin: `\\b(${AGGREGATION_OPERATORS.join('|')})\\s+\\b(by|without)\\b\\s*\\(`,
        end: '\\)',
        returnBegin: true,
        contains: [
          {
            // 匹配聚合操作符本身
            className: 'function',
            begin: `\\b(${AGGREGATION_OPERATORS.join('|')})\\b`,
            relevance: 10,
          },
          {
            // 匹配by/without关键字
            className: 'keyword',
            begin: '\\b(by|without)\\b',
            relevance: 5,
          },
          {
            // 匹配标签列表
            begin: '\\(',
            end: '\\)',
            endsParent: true,
            relevance: 0,
            contains: [
              {
                className: 'label',
                begin: '\\b[a-zA-Z_][a-zA-Z0-9_]*\\b',
                relevance: 0,
              },
            ],
          },
        ],
      },

      // 聚合操作符不带子句
      {
        className: 'function',
        begin: `\\b(${AGGREGATION_OPERATORS.join('|')})\\b\\s*(?=\\()`,
        relevance: 10,
      },

      // 普通函数调用
      {
        className: 'function',
        begin: `\\b(${FUNCTIONS.join('|')})\\b\\s*(?=\\()`,
        relevance: 5,
      },

      // 独立的关键字（by, without等）
      {
        className: 'keyword',
        begin: `\\b(${KEYWORDS.join('|')})\\b`,
        relevance: 3,
      },

      // 标签名称（在匹配器中使用）
      {
        className: 'label',
        begin: '\\b[a-zA-Z_][a-zA-Z0-9_]*\\b(?=\\s*[=~!])',
        relevance: 0,
      },

      // 指标名称（最后匹配，避免与关键字冲突）
      {
        className: 'metric',
        begin: '\\b[a-zA-Z_:][a-zA-Z0-9_:]*\\b',
        relevance: 0,
      },
    ],
  };
}
