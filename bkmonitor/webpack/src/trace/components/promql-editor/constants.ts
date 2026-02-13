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
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';

export const defaultOptions = {
  lineNumbers: 'off' as const,
  lineDecorationsWidth: 10,
  lineNumbersMinChars: 0,
  glyphMargin: false,
  folding: false,
  minimap: {
    enabled: false,
  },
  fontSize: 14,
  fontFamily: 'Menlo, Monaco, "Courier New", monospace',
  codeLens: false,
  contextmenu: false,
  fixedOverflowWidgets: true,
  renderLineHighlightOnlyWhenFocus: true,
  overviewRulerBorder: false,
  overviewRulerLanes: 0,
  wordWrap: 'on' as const,
  scrollBeyondLastLine: false,
  renderLineHighlight: 'none' as const,
  scrollbar: {
    vertical: 'hidden' as const,
    verticalScrollbarSize: 0,
    horizontal: 'hidden' as const,
    horizontalScrollbarSize: 0,
    alwaysConsumeMouseWheel: false,
  },
  padding: {
    top: 4,
    bottom: 8,
    right: 0,
    left: 0,
  },
  suggest: () => ({
    showWords: false,
  }),
  lineHeight: 19,
  suggestFontSize: 12,
  suggestLineHeight: 19,
  cursorStyle: 'line-thin' as const,
};

/**
 * @description placeholder
 */
export class PlaceholderWidget {
  domNode = null;
  editor = null;
  constructor(editor) {
    this.editor = editor;
    this.domNode = document.createElement('div');
    this.domNode.className = 'placeholder-widget';
    this.domNode.innerHTML = window.i18n.t('请输入 PromQL 查询语句，Shift + Enter换行，Enter查询');
    this.editor.addOverlayWidget(this);
    this.update();
  }
  getDomNode() {
    return this.domNode;
  }
  getId() {
    return 'my.placeholder.widget';
  }
  getPosition() {
    return {
      preference: monaco.editor.OverlayWidgetPositionPreference.TOP_CENTER,
    };
  }
  update() {
    const model = this.editor.getModel();
    const isEmpty = model.getValueLength() === 0;
    this.domNode.style.display = isEmpty ? 'block' : 'none';
  }
}
