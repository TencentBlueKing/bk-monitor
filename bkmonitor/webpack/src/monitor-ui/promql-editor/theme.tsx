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
import { HighlightStyle, tags } from '@codemirror/highlight';
import { EditorView } from '@codemirror/view';

export const theme = EditorView.theme({
  '&': {
    '&.cm-focused': {
      outline: 'none !important',
      outline_fallback: 'none'
    }
  },
  '.cm-scroller': {
    overflow: 'hidden',
    fontFamily: '"DejaVu Sans Mono", monospace'
  },
  '.cm-placeholder': {
    fontFamily:
      // eslint-disable-next-line max-len
      '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans","Liberation Sans",sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji"'
  },

  '.cm-matchingBracket': {
    color: '#000',
    backgroundColor: '#dedede',
    fontWeight: 'bold',
    outline: '1px dashed transparent'
  },
  '.cm-nonmatchingBracket': { borderColor: 'red' },

  '.cm-tooltip': {
    backgroundColor: '#f8f8f8',
    borderColor: 'rgba(52, 79, 113, 0.2)'
  },

  '.cm-tooltip.cm-tooltip-autocomplete': {
    '& > ul': {
      maxHeight: '350px',
      fontFamily: '"DejaVu Sans Mono", monospace',
      maxWidth: 'unset'
    },
    '& > ul > li': {
      padding: '2px 1em 2px 3px'
    },
    '& li:hover': {
      backgroundColor: '#ddd'
    },
    '& > ul > li[aria-selected]': {
      backgroundColor: '#d6ebff',
      color: 'unset'
    },
    minWidth: '30%'
  },

  '.cm-completionDetail': {
    float: 'right',
    color: '#999'
  },

  '.cm-tooltip.cm-completionInfo': {
    marginTop: '-11px',
    padding: '10px',
    fontFamily: "'Open Sans', 'Lucida Sans Unicode', 'Lucida Grande', sans-serif;",
    border: 'none',
    backgroundColor: '#d6ebff',
    minWidth: '250px',
    maxWidth: 'min-content'
  },

  '.cm-completionInfo.cm-completionInfo-right': {
    '&:before': {
      content: "' '",
      height: '0',
      position: 'absolute',
      width: '0',
      left: '-20px',
      border: '10px solid transparent',
      borderRightColor: '#d6ebff'
    },
    marginLeft: '12px'
  },
  '.cm-completionInfo.cm-completionInfo-left': {
    '&:before': {
      content: "' '",
      height: '0',
      position: 'absolute',
      width: '0',
      right: '-20px',
      border: '10px solid transparent',
      borderLeftColor: '#d6ebff'
    },
    marginRight: '12px'
  },

  '.cm-completionMatchedText': {
    textDecoration: 'none',
    fontWeight: 'bold',
    color: '#0066bf'
  },

  '.cm-line': {
    '&::selection': {
      backgroundColor: '#add6ff'
    },
    '& > span::selection': {
      backgroundColor: '#add6ff'
    }
  },

  '.cm-selectionMatch': {
    backgroundColor: '#e6f3ff'
  },

  '.cm-diagnostic': {
    '&.cm-diagnostic-error': {
      borderLeft: '3px solid #e65013'
    }
  },

  '.cm-completionIcon': {
    boxSizing: 'content-box',
    fontSize: '16px',
    lineHeight: '1',
    marginRight: '10px',
    verticalAlign: 'top',
    '&:after': { content: "''" },
    fontFamily: 'codicon',
    paddingRight: '0',
    opacity: '1',
    color: '#007acc'
  },

  '.cm-completionIcon-function, .cm-completionIcon-method': {
    '&:after': { content: "'f'" },
    color: '#652d90'
  },
  '.cm-completionIcon-class': {
    '&:after': { content: "'○'" }
  },
  '.cm-completionIcon-interface': {
    '&:after': { content: "'◌'" }
  },
  '.cm-completionIcon-variable': {
    '&:after': { content: "'𝑥'" }
  },
  '.cm-completionIcon-constant': {
    '&:after': { content: "'c'" },
    color: '#007acc'
  },
  '.cm-completionIcon-type': {
    '&:after': { content: "'𝑡'" }
  },
  '.cm-completionIcon-enum': {
    '&:after': { content: "'∪'" }
  },
  '.cm-completionIcon-property': {
    '&:after': { content: "'□'" }
  },
  '.cm-completionIcon-keyword': {
    '&:after': { content: "'k'" },
    color: '#616161'
  },
  '.cm-completionIcon-namespace': {
    '&:after': { content: "'▢'" }
  },
  '.cm-completionIcon-text': {
    '&:after': { content: "'t'" },
    color: '#ee9d28'
  }
});

export const promqlHighlighter = HighlightStyle.define([
  { tag: tags.name, color: '#000' },
  { tag: tags.number, color: '#09885a' },
  { tag: tags.string, color: '#a31515' },
  { tag: tags.keyword, color: '#008080' },
  { tag: tags.function(tags.variableName), color: '#008080' },
  { tag: tags.labelName, color: '#800000' },
  { tag: tags.operator },
  { tag: tags.modifier, color: '#008080' },
  { tag: tags.paren },
  { tag: tags.squareBracket },
  { tag: tags.brace },
  { tag: tags.invalid, color: 'red' },
  { tag: tags.comment, color: '#888', fontStyle: 'italic' }
]);
