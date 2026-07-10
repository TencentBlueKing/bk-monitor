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
import RetrieveHelper from '@/views/retrieve-helper';
import { highlightPlainTextIntoFragment } from '@/views/retrieve-core/page-highlight';

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  getClickTargetElement,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import UseSegmentPropInstance from './use-segment-pop';

import type { Ref } from 'vue';

export type FormatterConfig = {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
  field: any;
  onSegmentClick: (_args: any) => void;
  onSegmentRenderUpdate?: () => void;
  options?: Record<string, any>;
  precomputedSegments?: PrecomputedSegments;
};

export type SegmentAppendText = {
  text: string;
  onClick?: (..._args) => void;
  onMouseDown?: (..._args) => void;
  onMouseUp?: (..._args) => void;
  attributes?: Record<string, string>;
};
export type PrecomputedSegments = Record<string, Array<{
  text: string;
  isMark?: boolean;
  isCursorText?: boolean;
  isBlobWord?: boolean;
  isNotParticiple?: boolean;
}>>;
export default class UseJsonFormatter {
  editor?: JsonView;
  config: FormatterConfig;
  setValuePromise: Promise<any>;
  localDepth: number;
  getSegmentContent: (_keyRef: object, _fn: (..._args) => void) => Ref<HTMLElement>;
  keyRef: any;
  segmentTaskId: number;

  constructor(cfg: FormatterConfig) {
    this.config = cfg;
    this.setValuePromise = Promise.resolve(true);
    this.localDepth = 1;
    this.keyRef = {};
    this.segmentTaskId = 0;
    this.getSegmentContent = UseSegmentPropInstance.getSegmentContent.bind(UseSegmentPropInstance);
  }

  update(cfg) {
    this.config = cfg;
  }

  getField(fieldName: string) {
    return this.config.fields.find(item => item.field_name === fieldName);
  }

  getFieldNameValue() {
    const tippyInstance = segmentPopInstance.getInstance();
    const target = tippyInstance.reference;
    let name = target.getAttribute('data-field-name');
    let value = target.getAttribute('data-field-value');
    let depth = target.getAttribute('data-field-dpth');

    if (value === undefined) {
      value = target.textContent;
    }

    if (name === undefined) {
      const valueElement = tippyInstance.reference.closest('.field-value') as HTMLElement;
      name = valueElement?.getAttribute('data-field-name');
    }

    if (depth === undefined) {
      depth = target.closest('[data-depth]')?.getAttribute('data-depth');
    }

    return { value, name, depth };
  }

  onSegmentEnumClick(val, isLink) {
    const { name, value, depth } = this.getFieldNameValue();
    const activeField = this.getField(name);
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.config.jsonValue?.[activeField?.field_name]
      : value;

    const option = {
      fieldName: activeField?.field_name,
      fieldType: activeField?.field_type,
      operation: val === 'not' ? 'is not' : val,
      value: target ?? value,
      depth,
    };

    this.config.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
  }

  isValidTraceId(traceId) {
    const traceIdPattern = /^[a-f0-9]{32}$/;
    return traceIdPattern.test(traceId);
  }

  handleSegmentClick(e: MouseEvent, value) {
    // 如果是点击划选文本，则不进行处理
    if (RetrieveHelper.isClickOnSelection(e, 2) || window?.getSelection()?.toString()?.length > 1) {
      return;
    }
    if (!value.toString() || value === '--') {
      return;
    }

    const valueElement = (e.target as HTMLElement).closest('.field-value') as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
    const fieldType = valueElement?.getAttribute('data-field-type');

    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('[data-item-id="trace-view"]') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');

    // 根据字段信息隐藏虚拟字段相关的选项
    const isVirtualField = fieldType === '__virtual__';
    const virtualFieldHiddenItems = ['is', 'not', 'new-search-page-is']; // 需要隐藏的选项

    virtualFieldHiddenItems.forEach((itemId) => {
      const element = content.value.querySelector(`[data-item-id="${itemId}"]`) as HTMLElement;
      element?.style.setProperty('display', isVirtualField ? 'none' : 'inline-flex');
    });

    // 这里的动态样式用于只显示"添加到本次检索"、"从本次检索中排除"
    const hasSegmentLightStyle = document.getElementById('dynamic-segment-light-style') !== null;

    // 若是应用了动态样式(实时日志/上下文)，且是虚拟字段，则不显示弹窗(弹窗无内容)
    if (hasSegmentLightStyle && isVirtualField) {
      return;
    }

    const { offsetX, offsetY } = getClickTargetElement(e);
    const target = setPointerCellClickTargetHandler(e, { offsetX, offsetY });

    const depth = valueElement.closest('[data-depth]')?.getAttribute('data-depth');

    target.setAttribute('data-field-value', value);
    target.setAttribute('data-field-name', fieldName);
    target.setAttribute('data-field-dpth', depth);

    segmentPopInstance.show(target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
  }

  isTextField(field: any) {
    return field?.field_type === 'text';
  }

  isAnalyzed(field: any) {
    return field?.is_analyzed ?? false;
  }

  escapeString(val: string) {
    const map = {
      '&amp;': '&',
      '&lt;': '<',
      '&gt;': '>',
      '&quot;': '"',
      '&#x27;': "'",
    };

    return typeof val !== 'string'
      ? val
      : val.replace(new RegExp(`(${Object.keys(map).join('|')})`, 'g'), match => map[match]);
  }

  splitTextIntoChunks(value: string, chunkSize = 2000) {
    if (!value) {
      return [];
    }

    const chunks: string[] = [];
    for (let index = 0; index < value.length; index += chunkSize) {
      chunks.push(value.slice(index, index + chunkSize));
    }

    return chunks.map(text => ({
      text,
      isCursorText: true,
    }));
  }

  getSplitList(field: any, content: any, options: { usePrecomputedSegments?: boolean } = {}) {
    const fieldName = typeof field === 'string' ? field : field?.field_name;
    const usePrecomputedSegments = options.usePrecomputedSegments ?? true;
    const precomputedSegments = fieldName ? this.config.precomputedSegments?.[fieldName] : undefined;
    if (usePrecomputedSegments && Array.isArray(precomputedSegments)) {
      return precomputedSegments;
    }

    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = this.escapeString(String(content));

    return this.splitTextIntoChunks(value).map(item => ({
      ...item,
      isNotParticiple: this.isTextField(field),
      isMark: new RegExp(markRegStr).test(item.text),
    }));
  }

  getChildItem(item) {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    const text = item.text?.length ? item.text : '""';
    const textNode = document.createElement('span');

    if (item.isMark) {
      textNode.classList.add('valid-text');
      textNode.appendChild(highlightPlainTextIntoFragment({
        text: text.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
        resultHighlighted: true,
      }));
      return textNode;
    }

    if (!(item.isNotParticiple || item.isBlobWord)) {
      if (item.isCursorText) {
        textNode.classList.add('valid-text');
      }
      textNode.appendChild(highlightPlainTextIntoFragment({ text }));
      return textNode;
    }

    textNode.classList.add('others-text');
    textNode.appendChild(highlightPlainTextIntoFragment({ text }));
    return textNode;
  }

  creatSegmentNodes = () => {
    const segmentNode = document.createElement('span');
    segmentNode.classList.add('segment-content');
    segmentNode.classList.add('bklog-scroll-cell');

    return segmentNode;
  };

  initStringAsValue(text?: string, appendText?: SegmentAppendText) {
    let root = this.getTargetRoot() as HTMLElement;
    if (root) {
      if (root.classList.contains('field-value')) {
        root = root.parentElement;
      }

      const fieldName = (root.querySelector('.field-name .black-mark') as HTMLElement)?.getAttribute('data-field-name');
      this.setNodeValueWordSplit(root, fieldName, '.field-value', text, appendText);
    }
  }

  addWordSegmentClick(root: HTMLElement) {
    if (!root.hasAttribute('data-word-segment-click')) {
      root.setAttribute('data-word-segment-click', '1');
      root.addEventListener('click', (e) => {
        const validTextElement = (e.target as HTMLElement).closest?.('.valid-text') as HTMLElement | null;
        if (validTextElement) {
          this.handleSegmentClick(e, validTextElement.textContent);
        }
      });
    }
  }

  setNodeValueWordSplit(
    target: HTMLElement,
    fieldName,
    valueSelector = '.bklog-json-field-value',
    textValue?: string,
    appendText?: SegmentAppendText,
  ) {
    this.addWordSegmentClick(target);
    for (const element of target.querySelectorAll(valueSelector)) {
      if (!element.getAttribute('data-has-word-split')) {
        const text = textValue ?? element.textContent;
        const field = this.getField(fieldName);
        const vlaues = this.getSplitList(field, text);
        const targetElement = element as HTMLElement;

        targetElement.setAttribute('data-has-word-split', '1');
        targetElement.setAttribute('data-field-name', fieldName);
        targetElement.setAttribute('data-field-type', field?.field_type);

        if (targetElement.hasAttribute('data-with-intersection')) {
          targetElement.style.setProperty('min-height', [targetElement.offsetHeight, 'px'].join(''));
        }

        targetElement.innerHTML = '';

        const segmentContent = this.creatSegmentNodes();

        const { setListItem, removeScrollEvent } = setScrollLoadCell(
          vlaues,
          targetElement,
          segmentContent,
          this.getChildItem,
          { pageSize: 1, maxAutoRenderItems: 1 },
        );
        removeScrollEvent();

        targetElement.append(segmentContent);
        setListItem(1, () => {
          this.config.onSegmentRenderUpdate?.();
        });

        if (appendText !== undefined) {
          const appendElement = document.createElement('span');
          appendElement.textContent = appendText.text;
          if (appendText.onClick) {
            appendElement.addEventListener('click', appendText.onClick);
          }
          if (appendText.onMouseDown) {
            appendElement.addEventListener('mousedown', appendText.onMouseDown);
          }
          if (appendText.onMouseUp) {
            appendElement.addEventListener('mouseup', appendText.onMouseUp);
          }

          for (const key of Object.keys(appendText.attributes ?? {})) {
            appendElement.setAttribute(key, appendText.attributes[key]);
          }

          element.firstChild.appendChild(appendElement);
        }

        requestAnimationFrame(() => {
          element.style.removeProperty('min-height');
        });
      }
    }
  }

  handleExpandNode(args) {
    if (args.isExpand) {
      // const target = args.targetElement as HTMLElement;
      // const rootElement = args.rootElement as HTMLElement;
      // const fieldName = (rootElement.parentNode.querySelector('.field-name .black-mark') as HTMLElement)?.innerText;
      // this.setNodeValueWordSplit(target, fieldName, '.bklog-json-field-value');
    }
  }

  get computedOptions() {
    return {
      mode: 'view',
      navigationBar: false,
      statusBar: false,
      mainMenuBar: false,
      onExpand: this.handleExpandNode.bind(this),
      ...(this.config.options ?? {}),
    };
  }

  getTargetRoot() {
    if (Array.isArray(this.config.target.value)) {
      return this.config.target.value[0];
    }

    return this.config.target.value;
  }

  initEditor(depth) {
    const targetRoot = this.getTargetRoot();
    if (!targetRoot) {
      this.editor = undefined;
      return false;
    }

    this.localDepth = depth;
    this.editor = new JsonView(targetRoot, {
      onNodeExpand: this.handleExpandNode.bind(this),
      depth,
      field: this.config.field,
      segmentRender: (value: string, rootNode: HTMLElement) => {
        const taskId = this.segmentTaskId;
        const vlaues = this.getSplitList(this.config.field, value, { usePrecomputedSegments: false });
        if (taskId !== this.segmentTaskId || !rootNode.isConnected) return;

        const segmentContent = this.creatSegmentNodes();
        rootNode.append(segmentContent);

        if (!rootNode.classList.contains('bklog-scroll-box')) {
          rootNode.classList.add('bklog-scroll-box');
        }

        const { setListItem, removeScrollEvent } = setScrollLoadCell(
          vlaues,
          rootNode,
          segmentContent,
          this.getChildItem,
          { pageSize: 1, maxAutoRenderItems: 1 },
        );
        removeScrollEvent();
        setListItem(1, this.config.onSegmentRenderUpdate);
      },
    });

    this.editor.initClickEvent((e) => {
      const validTextElement = (e.target as HTMLElement).closest?.('.valid-text') as HTMLElement | null;
      if (validTextElement) {
        this.handleSegmentClick(e, validTextElement.textContent);
      }
    });

    return true;
  }

  setNodeExpand([currentDepth]) {
    this.editor?.expand(currentDepth);
  }

  setValue(depth) {
    this.setValuePromise = new Promise((resolve, reject) => {
      try {
        this.segmentTaskId += 1;
        if (!this.editor && !this.initEditor(depth)) {
          resolve(false);
          return;
        }

        this.editor?.setValue(this.config.jsonValue);
        this.setNodeExpand([depth]);
        this.localDepth = depth;
        resolve(true);
      } catch (e) {
        reject(e);
      }
    });

    return this.setValuePromise;
  }

  setExpand(depth) {
    this.setValuePromise?.then(() => {
      if (!this.editor && !this.initEditor(depth)) return;

      this.setNodeExpand([depth]);
      this.localDepth = depth;
    }).catch(() => undefined);
  }

  destroy() {
    this.segmentTaskId += 1;
    this.editor?.destroy();
    this.editor = undefined;
    const root = this.getTargetRoot() as HTMLElement;
    if (root) {
      let target = root;
      if (!root.classList.contains('field-value')) {
        target = root.querySelector('.field-value');
      }

      if (target?.hasAttribute('data-has-word-split')) {
        target.removeAttribute('data-has-word-split');
      }

      if (target && typeof this.config.jsonValue === 'string') {
        target.textContent = this.config.jsonValue;
      }
    }
  }

  getEditor() {
    return {
      setValue: this.setValue.bind(this),
      setExpand: this.setExpand.bind(this),
      initEditor: this.initEditor.bind(this),
      destroy: this.destroy.bind(this),
    };
  }
}
