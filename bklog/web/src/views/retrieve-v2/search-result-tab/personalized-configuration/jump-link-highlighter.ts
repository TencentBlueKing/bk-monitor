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

// 创建变量装饰器 - 匹配 {xxx} 格式
const variableDecoration = Decoration.mark({ class: 'jump-link-variable' });

// 变量高亮插件
const jumpLinkHighlighter = ViewPlugin.fromClass(
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

      // 匹配 {xxx} 格式的变量
      const variableRegex = /\{[^{}]+\}/g;
      let match;

      while ((match = variableRegex.exec(text)) !== null) {
        builder.add(match.index, match.index + match[0].length, variableDecoration);
      }

      return builder.finish();
    }
  },
  {
    decorations: v => v.decorations,
  },
);

// CSS 样式主题
export const jumpLinkHighlightTheme = EditorView.theme({
  '.jump-link-variable': {
    color: '#3A84FF',
    backgroundColor: '#E1ECFF',
    borderRadius: '2px',
    padding: '0 2px',
    fontWeight: '500',
  },
});

// 导出跳转链接语法高亮扩展
export function jumpLinkSyntaxHighlighting(): Extension {
  return [jumpLinkHighlighter, jumpLinkHighlightTheme];
}
