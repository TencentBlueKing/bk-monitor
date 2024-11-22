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
import UseSegmentPropInstance from './use-segment-pop';

export type FormatterConfig = {
  target: Ref<HTMLElement | null>;
  fields: any[];
  jsonValue: any;
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

  onSegmentEnumClick(val, isLink) {
    const tippyInstance = segmentPopInstance.getInstance();
    const currentValue = tippyInstance.reference.innerText;
    const valueElement = tippyInstance.reference.closest('.field-value') as HTMLElement;
    const depth = tippyInstance.reference.closest('[data-depth]')?.getAttribute('data-depth');

    const fieldName = valueElement?.getAttribute('data-field-name');
    const activeField = this.getField(fieldName);
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.config.jsonValue?.[activeField?.field_name]
      : currentValue;

    const option = {
      fieldName: activeField?.field_name,
      operation: val === 'not' ? 'is not' : val,
      value: (target ?? currentValue).replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      depth,
    };

    this.config.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
  }

  isValidTraceId(traceId) {
    const traceIdPattern = /^[a-f0-9]{32}$/;
    return traceIdPattern.test(traceId);
  }

  handleSegmentClick(e, value) {
    if (!value.toString() || value === '--') return;
    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('.bklog-trace-view')?.closest('.segment-event-box') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');
    segmentPopInstance.show(e.target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
  }

  getCurrentFieldRegStr(field: any) {
    /** 默认分词字符串 */
    const segmentRegStr = ',&*+:;?^=!$<>\'"{}()|[]\\/\\s\\r\\n\\t-';
    if (field.tokenize_on_chars) {
      return field.tokenize_on_chars;
    }

    return segmentRegStr;
  }

  isTextField(field: any) {
    return field?.field_type === 'text';
  }

  isAnalyzed(field: any) {
    return field?.is_analyzed ?? false;
  }

  splitParticipleWithStr(str: string, delimiterPattern: string) {
    if (!str) return [];
    // 转义特殊字符，并构建用于分割的正则表达式
    const regexPattern = delimiterPattern
      .split('')
      .map(delimiter => `\\${delimiter}`)
      .join('|');

    // 构建正则表达式以找到分隔符或分隔符周围的文本
    const regex = new RegExp(`(${regexPattern})`);

    // 先根据高亮标签分割
    const markSplitRes = str.match(/(<mark>.*?<\/mark>|.+?(?=<mark|$))/gs);

    // 在高亮分割数组基础上再以分隔符分割数组
    const parts = markSplitRes.reduce((list, item) => {
      if (/^<mark>.*?<\/mark>$/.test(item)) {
        list.push(item);
      } else {
        const arr = item.split(regex);
        arr.forEach(i => i && list.push(i));
      }
      return list;
    }, []);

    // 转换结果为对象数组，包含分隔符标记
    const result = parts
      .filter(part => part?.length)
      .map(part => {
        return {
          text: part,
          isNotParticiple: regex.test(part),
          isMark: /^<mark>.*?<\/mark>$/.test(part),
        };
      });

    return result;
  }

  getSplitList(field: any, content: any) {
    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = `${content}`;
    if (this.isAnalyzed(field)) {
      // 这里进来的都是开了分词的情况
      return this.splitParticipleWithStr(value, this.getCurrentFieldRegStr(field));
    }

    return [
      {
        text: value.replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
        isNotParticiple: this.isTextField(field),
        isMark: new RegExp(markRegStr).test(value),
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
      mrkNode.innerHTML = item.text.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
      return mrkNode;
    }

    if (!item.isNotParticiple) {
      const validTextNode = document.createElement('span');
      validTextNode.classList.add('valid-text');
      validTextNode.innerHTML = item.text;
      return validTextNode;
    }

    const textNode = document.createElement('span');
    textNode.classList.add('others-text');
    textNode.innerText = item.text;
    return textNode;
  }

  creatSegmentNodes = (vlaues: any[]) => {
    const segmentNode = document.createElement('span');
    segmentNode.classList.add('segment-content');

    vlaues.forEach(item => {
      segmentNode.append(this.getChildItem(item));
    });

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

  setNodeValueWordSplit(
    target: HTMLElement,
    fieldName,
    valueSelector = '.bklog-json-field-value',
    textValue?: string,
    appendText?: SegmentAppendText,
  ) {
    // const fieldName = name.replace(/(^\s*)|(\s*$)/g, '');
    target.querySelectorAll(valueSelector).forEach(element => {
      if (!element.getAttribute('data-has-word-split')) {
        const text = textValue ?? (element as HTMLDivElement).innerText;
        const field = this.getField(fieldName);
        const vlaues = this.getSplitList(field, text);
        element?.setAttribute('data-has-word-split', '1');
        element?.setAttribute('data-field-name', fieldName);
        element.innerHTML = '';
        element.append(this.creatSegmentNodes(vlaues));
        element.addEventListener('click', e => {
          if ((e.target as HTMLElement).classList.contains('valid-text')) {
            this.handleSegmentClick(e, (e.target as HTMLElement).innerText);
          }
        });

        if (appendText) {
          const appendElement = document.createElement('span');
          appendElement.innerText = appendText.text;
          if (appendText.onClick) {
            appendElement.addEventListener('click', appendText.onClick);
          }

          Object.keys(appendText.attributes ?? {}).forEach(key => {
            appendElement.setAttribute(key, appendText.attributes[key]);
          });

          element.firstChild.appendChild(appendElement);
        }
      }
    });
  }

  handleExpandNode(args) {
    if (args.isExpand) {
      const target = args.targetElement as HTMLElement;
      const rootElement = args.rootElement as HTMLElement;

      const fieldName = (rootElement.parentNode.querySelector('.field-name .black-mark') as HTMLElement)?.innerText;
      this.setNodeValueWordSplit(target, fieldName, '.bklog-json-field-value');
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
      this.editor = new JsonView(this.getTargetRoot(), { onNodeExpand: this.handleExpandNode.bind(this), depth });
      this.editor.initClickEvent();
    }
  }

  setNodeExpand([currentDepth]) {
    this.editor.expand(currentDepth);
    const root = this.getTargetRoot();
    const fieldName = (root.querySelector('.field-name .black-mark') as HTMLElement)?.innerText;
    this.setNodeValueWordSplit(root, fieldName);
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
        target.innerHTML = this.config.jsonValue;
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
