import * as monaco from 'monaco-editor';
import { Range, Position } from 'monaco-editor';

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
  'DESC'
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
// 多词短语高亮
const specialKeywords = [
  'ORDER BY',
  'GROUP BY',
];
monaco.languages.register({ id: 'dorisSQL' });

monaco.languages.setMonarchTokensProvider('dorisSQL', {
  keywords: dorisKeywords,
  functions: dorisFunctions,

  tokenizer: {
    root: [
      ...specialKeywords.map(keyword => ({
        regex: new RegExp(`\\b${keyword.replace(/\s+/g, '\\s+')}\\b`),
        action: { token: 'keyword' }
      })),
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
