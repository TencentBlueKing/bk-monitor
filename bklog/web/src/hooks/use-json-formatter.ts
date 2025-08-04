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
import { Ref } from 'vue';

import JsonView from '../global/json-view';
// import jsonEditorTask, { EditorTask } from '../global/utils/json-editor-task';
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  getClickTargetElement,
  optimizedSplit,
  setPointerCellClickTargetHandler,
  setScrollLoadCell,
} from './hooks-helper';
import LuceneSegment from './lucene.segment';
import UseSegmentPropInstance from './use-segment-pop';

export type FormatterConfig = {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
  field: any;
  onSegmentClick: (args: any) => void;
  options?: Record<string, any>;
};

export type SegmentAppendText = { text: string; onClick?: (...args) => void; attributes?: Record<string, string> };
export default class UseJsonFormatter {
  editor: JsonView;
  config: FormatterConfig;
  setValuePromise: Promise<any>;
  localDepth: number;
  getSegmentContent: (keyRef: object, fn: (...args) => void) => Ref<HTMLElement>;
  keyRef: any;

  constructor(cfg: FormatterConfig) {
    this.config = cfg;
    this.setValuePromise = Promise.resolve(true);
    this.localDepth = 1;
    this.keyRef = {};
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
    if (!value.toString() || value === '--') return;
    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('.bklog-trace-view')?.closest('.segment-event-box') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');

    const { offsetX, offsetY } = getClickTargetElement(e);
    const target = setPointerCellClickTargetHandler(e, { offsetX, offsetY });

    const valueElement = (e.target as HTMLElement).closest('.field-value') as HTMLElement;
    const fieldName = valueElement?.getAttribute('data-field-name');
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
      : val.replace(RegExp(`(${Object.keys(map).join('|')})`, 'g'), match => map[match]);
  }

  getSplitList(field: any, content: any) {
    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = this.escapeString(`${content}`);
    if (this.isAnalyzed(field)) {
      if (field.tokenize_on_chars) {
        // 这里进来的都是开了分词的情况
        return optimizedSplit(value, field.tokenize_on_chars);
      }

      return LuceneSegment.split(value, 1000);
    }

    return [
      {
        text: value.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
        isNotParticiple: this.isTextField(field),
        isMark: new RegExp(markRegStr).test(value),
        isCursorText: true,
      },
    ];
  }

  getChildItem(item) {
    if (item.text === '\n') {
      const brNode = document.createElement('br');
      return brNode;
    }

    if (item.isMark) {
      const mrkNode = document.createElement('mark');
      mrkNode.textContent = item.text.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
      mrkNode.classList.add('valid-text');
      return mrkNode;
    }

    if (!item.isNotParticiple && !item.isBlobWord) {
      const validTextNode = document.createElement('span');
      if (item.isCursorText) {
        validTextNode.classList.add('valid-text');
      }
      validTextNode.textContent = item.text?.length ? item.text : '""';
      return validTextNode;
    }

    const textNode = document.createElement('span');
    textNode.classList.add('others-text');
    textNode.textContent = item.text?.length ? item.text : '""';
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
      root.addEventListener('click', e => {
        if ((e.target as HTMLElement).classList.contains('valid-text')) {
          this.handleSegmentClick(e, (e.target as HTMLElement).textContent);
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
    target.querySelectorAll(valueSelector).forEach((element: HTMLElement) => {
      if (!element.getAttribute('data-has-word-split')) {
        const text = textValue ?? element.textContent;
        const field = this.getField(fieldName);
        const vlaues = this.getSplitList(field, text);
        element?.setAttribute('data-has-word-split', '1');
        element?.setAttribute('data-field-name', fieldName);

        if (element.hasAttribute('data-with-intersection')) {
          element.style.setProperty('min-height', `${element.offsetHeight}px`);
        }

        element.innerHTML = '';

        const segmentContent = this.creatSegmentNodes();

        const { setListItem, removeScrollEvent } = setScrollLoadCell(
          vlaues,
          element,
          segmentContent,
          this.getChildItem,
        );
        removeScrollEvent();

        element.append(segmentContent);
        setListItem(1000);

        if (appendText) {
          const appendElement = document.createElement('span');
          appendElement.textContent = appendText.text;
          if (appendText.onClick) {
            appendElement.addEventListener('click', appendText.onClick);
          }

          Object.keys(appendText.attributes ?? {}).forEach(key => {
            appendElement.setAttribute(key, appendText.attributes[key]);
          });

          element.firstChild.appendChild(appendElement);
        }

        requestAnimationFrame(() => {
          element.style.removeProperty('min-height');
        });
      }
    });
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
    if (this.getTargetRoot()) {
      this.localDepth = depth;
      this.editor = new JsonView(this.getTargetRoot(), {
        onNodeExpand: this.handleExpandNode.bind(this),
        depth,
        field: this.config.field,
        segmentRender: (value: string, rootNode: HTMLElement) => {
          const vlaues = this.getSplitList(this.config.field, value);
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
          );
          removeScrollEvent();
          setListItem(600);
        },
      });

      this.editor.initClickEvent(e => {
        if ((e.target as HTMLElement).classList.contains('valid-text')) {
          this.handleSegmentClick(e, (e.target as HTMLElement).textContent);
        }
      });
    }
  }

  setNodeExpand([currentDepth]) {
    this.editor.expand(currentDepth);
  }

  setValue(depth) {
    this.setValuePromise = new Promise((resolve, reject) => {
      try {
        this.editor.setValue(this.config.jsonValue);
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
      this.setNodeExpand([depth]);
      this.localDepth = depth;
    });
  }

  destroy() {
    this.editor?.destroy();
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
