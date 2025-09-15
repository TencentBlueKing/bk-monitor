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
import { RangeSetBuilder } from '@codemirror/state';
import { Decoration, type DecorationSet, EditorView, ViewPlugin, type ViewUpdate } from '@codemirror/view';

import type { Extension } from '@codemirror/state';

// 语法高亮样式类
const grepStyles = {
  command: 'grep-command',
  argument: 'grep-argument',
  string: 'grep-string',
  pattern: 'grep-pattern',
  pipe: 'grep-pipe',
  escape: 'grep-escape',
};

// 创建装饰器
const commandDecoration = Decoration.mark({ class: grepStyles.command });
const argumentDecoration = Decoration.mark({ class: grepStyles.argument });
const stringDecoration = Decoration.mark({ class: grepStyles.string });
const patternDecoration = Decoration.mark({ class: grepStyles.pattern });
const pipeDecoration = Decoration.mark({ class: grepStyles.pipe });
const escapeDecoration = Decoration.mark({ class: grepStyles.escape });

// 语法高亮插件
const grepHighlighter = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = this.buildDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged) {
        this.decorations = this.buildDecorations(update.view);
      }
    }

    buildDecorations(view: EditorView): DecorationSet {
      const builder = new RangeSetBuilder<Decoration>();
      const text = view.state.doc.toString();

      // 分析整个文本
      this.analyzeText(text, builder);

      return builder.finish();
    }

    private analyzeText(text: string, builder: RangeSetBuilder<Decoration>) {
      let pos = 0;
      const len = text.length;

      while (pos < len) {
        // 跳过空白字符
        if (/\s/.test(text[pos])) {
          pos++;
          continue;
        }

        // 匹配管道符
        if (text[pos] === '|') {
          builder.add(pos, pos + 1, pipeDecoration);
          pos++;
          continue;
        }

        // 匹配 grep/egrep 命令
        const grepMatch = text.substr(pos).match(/^(grep|egrep)(?=\s|$)/);
        if (grepMatch) {
          const matchLen = grepMatch[0].length;
          builder.add(pos, pos + matchLen, commandDecoration);
          pos += matchLen;
          continue;
        }

        // 匹配参数 (-i, -v, -E 等)
        const argMatch = text.substr(pos).match(/^-[a-zA-Z0-9]+/);
        if (argMatch) {
          const matchLen = argMatch[0].length;
          builder.add(pos, pos + matchLen, argumentDecoration);
          pos += matchLen;
          continue;
        }

        // 匹配双引号字符串
        if (text[pos] === '"') {
          const result = this.parseQuotedString(text, pos, '"');
          if (result) {
            builder.add(pos, result.end, stringDecoration);
            // 高亮转义字符
            this.highlightEscapes(text, pos + 1, result.end - 1, builder);
            pos = result.end;
            continue;
          }
        }

        // 匹配单引号字符串
        if (text[pos] === "'") {
          const result = this.parseQuotedString(text, pos, "'");
          if (result) {
            builder.add(pos, result.end, stringDecoration);
            // 高亮转义字符
            this.highlightEscapes(text, pos + 1, result.end - 1, builder);
            pos = result.end;
            continue;
          }
        }

        // 匹配未加引号的模式
        const patternMatch = text.substr(pos).match(/^[^\s|"']+/);
        if (patternMatch) {
          const matchLen = patternMatch[0].length;
          builder.add(pos, pos + matchLen, patternDecoration);
          // 高亮转义字符
          this.highlightEscapes(text, pos, pos + matchLen, builder);
          pos += matchLen;
          continue;
        }

        pos++;
      }
    }

    private parseQuotedString(text: string, start: number, quote: string): { end: number } | null {
      let pos = start + 1;
      while (pos < text.length) {
        if (text[pos] === quote) {
          return { end: pos + 1 };
        }
        if (text[pos] === '\\' && pos + 1 < text.length) {
          pos += 2; // 跳过转义字符
        } else {
          pos++;
        }
      }
      return { end: text.length }; // 未闭合的字符串
    }

    private highlightEscapes(text: string, start: number, end: number, builder: RangeSetBuilder<Decoration>) {
      for (let i = start; i < end - 1; i++) {
        if (text[i] === '\\') {
          // 匹配常见转义序列
          const escapeMatch = text.substr(i).match(/^\\["'\\tnr]/);
          if (escapeMatch) {
            builder.add(i, i + escapeMatch[0].length, escapeDecoration);
            i += escapeMatch[0].length - 1;
          } else {
            // 匹配十六进制转义
            const hexMatch = text.substr(i).match(/^\\x[0-9a-fA-F]{2}/);
            if (hexMatch) {
              builder.add(i, i + hexMatch[0].length, escapeDecoration);
              i += hexMatch[0].length - 1;
            }
          }
        }
      }
    }
  },
  {
    decorations: v => v.decorations,
  },
);

// CSS 样式
export const grepHighlightTheme = EditorView.theme({
  '.grep-command': {
    color: '#0066cc',
    fontWeight: 'bold',
  },
  '.grep-argument': {
    color: '#cc6600',
    fontWeight: 'bold',
  },
  '.grep-string': {
    color: '#009900',
  },
  '.grep-pattern': {
    color: '#cc0066',
  },
  '.grep-pipe': {
    color: '#666666',
    fontWeight: 'bold',
  },
  '.grep-escape': {
    color: '#ff6600',
    fontWeight: 'bold',
  },
});

// 导出 grep 语法高亮扩展
export function grepSyntaxHighlighting(): Extension {
  return [grepHighlighter, grepHighlightTheme];
}
