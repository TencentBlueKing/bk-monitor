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

import segmentPopInstance from '../global/utils/segment-pop-instance';
import UseSegmentPropInstance from './use-segment-pop';
import { optimizedSplit } from './hooks-helper';

export type FormatterConfig = {
  onSegmentClick: (args: any) => void;
  options?: {
    content: boolean | number | string;
    field: any;
    data: any;
  };
};

export type WordListItem = {
  text: string;
  isMark: boolean;
  isCursorText: boolean;
  startIndex?: number;
  endIndex?: number;
  left?: number;
  top?: number;
  width?: number;
  renderWidth?: number;
  split?: WordListItem[];
  line?: number;
};

export type SegmentAppendText = { text: string; onClick?: (...args) => void; attributes?: Record<string, string> };
export default class UseTextSegmentation {
  getSegmentContent: (keyRef: object, fn: (...args) => void) => Ref<HTMLElement>;
  onSegmentClick: (...args) => void;
  clickValue: string;
  keyRef: any;
  options = {
    field: null,
    content: '',
    data: {},
  };
  constructor(cfg: FormatterConfig) {
    this.keyRef = {};
    this.getSegmentContent = UseSegmentPropInstance.getSegmentContent.bind(UseSegmentPropInstance);
    this.onSegmentClick = cfg.onSegmentClick;
    this.clickValue = '';
    Object.assign(this.options, cfg.options ?? {});
  }

  getCellClickHandler(e: MouseEvent, value, { offsetY = 0, offsetX = 0 }) {
    const x = e.clientX;
    const y = e.clientY;
    let virtualTarget = document.body.querySelector('.bklog-virtual-target') as HTMLElement;
    if (!virtualTarget) {
      virtualTarget = document.createElement('span') as HTMLElement;
      virtualTarget.className = 'bklog-virtual-target';
      virtualTarget.style.setProperty('position', 'absolute');
      virtualTarget.style.setProperty('visibility', 'hidden');
      virtualTarget.style.setProperty('z-index', '-1');
      document.body.appendChild(virtualTarget);
    }

    virtualTarget.style.setProperty('left', `${x + offsetX}px`);
    virtualTarget.style.setProperty('top', `${y + offsetY}px`);

    this.handleSegmentClick(virtualTarget, value);
  }

  getTextCellClickHandler(e: MouseEvent) {
    if ((e.target as HTMLElement).classList.contains('valid-text')) {
      this.handleSegmentClick(e.target, (e.target as HTMLElement).innerHTML);
    }
  }

  getChildNodes(forceSplit = false) {
    let start = 0;
    return this.getSplitList(this.options.field, this.options.content, forceSplit).map(item => {
      Object.assign(item, {
        startIndex: start,
        endIndex: start + item.text.length,
      });
      start = start + item.text.length;
      return item;
    });
  }

  update(cfg) {
    Object.assign(this.options, cfg.options ?? {});
  }

  formatValue() {
    return this.escapeString(this.options.content)
      .replace(/<mark>/g, '')
      .replace(/<\/mark>/g, '');
  }

  private getField() {
    return this.options?.field;
  }

  private onSegmentEnumClick(val, isLink) {
    const tippyInstance = segmentPopInstance.getInstance();
    const currentValue = this.clickValue;
    const depth = tippyInstance.reference.closest('[data-depth]')?.getAttribute('data-depth');
    const isNestedField = tippyInstance.reference.closest('[is-nested-value]')?.getAttribute('is-nested-value');

    const activeField = this.getField();
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.options.data?.[activeField?.field_name]
      : currentValue;

    const option = {
      fieldName: activeField?.field_name,
      operation: val === 'not' ? 'is not' : val,
      value: (target ?? currentValue).replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      depth,
      isNestedField,
    };

    this.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();
  }

  private isValidTraceId(traceId) {
    const traceIdPattern = /^[a-f0-9]{32}$/;
    return traceIdPattern.test(traceId);
  }

  private handleSegmentClick(target, value) {
    if (!value.toString() || value === '--') return;

    this.clickValue = value;
    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('.bklog-trace-view')?.closest('.segment-event-box') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');
    segmentPopInstance.show(target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
  }

  private getCurrentFieldRegStr(field: any) {
    /** 默认分词字符串 */
    const segmentRegStr = ',&*+:;?^=!$<>\'"{}()|[]\\/\\s\\r\\n\\t-';
    if (field.tokenize_on_chars) {
      return field.tokenize_on_chars;
    }

    return segmentRegStr;
  }

  private isTextField(field: any) {
    return field?.field_type === 'text';
  }

  private isAnalyzed(field: any) {
    return field?.is_analyzed ?? false;
  }

  /**
   * @description: 判断是否为虚拟对象字段, 字段来源：Object对象字段添加为列表字段
   * @param {any} field
   * @return {*}
   */
  private isVirtualObjField(field: any) {
    return (field?.is_virtual_obj_node ?? false) && field?.field_type === 'object';
  }

  private convertVirtaulObjToArray() {
    // this.options.content值为--时，直接JSON.parse会转义报错
    const target =
      this.options.data[this.options.field.field_name] ??
      (['', '--'].includes(this.options.content) ? this.options.content : JSON.parse(this.options.content));
    const convertObjToArray = (root: object, isValue = false) => {
      const result = [];

      if (typeof root === 'object') {
        if (Array.isArray(root)) {
          result.push({
            text: '[',
            isCursorText: false,
            isMark: false,
          });
          result.push(root.map(child => convertObjToArray(child)));
          result.push({
            text: ']',
            isCursorText: false,
            isMark: false,
          });

          result.push({
            text: ',',
            isCursorText: false,
            isMark: false,
          });
          return result;
        }

        result.push({
          text: '{',
          isCursorText: false,
          isMark: false,
        });

        Object.entries(root).forEach(([key, value]) => {
          result.push({
            text: `"${key}":`,
            isCursorText: false,
            isMark: false,
          });

          if (result.length < 1000) {
            result.push(...convertObjToArray(value, true));
          } else {
            result.push({
              text: value,
              isCursorText: false,
              isMark: false,
            });
          }
        });

        const lastRow = result.at(-1);
        if (lastRow?.text === ',') {
          result.pop();
        }

        result.push({
          text: '}',
          isCursorText: false,
          isMark: false,
        });

        result.push({
          text: ',',
          isCursorText: false,
          isMark: false,
        });
        return result;
      }

      /** 检索高亮分词字符串 */
      const markRegStr = '<mark>(.*?)</mark>';
      const value = this.escapeString(`${root}`);
      const formatValue = value.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
      const isMark = new RegExp(markRegStr).test(value);

      result.push({
        text: '"',
        isCursorText: false,
        isMark: false,
      });

      result.push({
        text: formatValue,
        isCursorText: isValue,
        isMark,
      });

      result.push({
        text: '"',
        isCursorText: false,
        isMark: false,
      });

      result.push({
        text: ',',
        isCursorText: false,
        isMark: false,
      });
      return result;
    };

    const output = convertObjToArray(target);
    const lastRow = output.at(-1);
    if (lastRow?.text === ',') {
      output.pop();
    }

    return output;
  }

  // private optimizedSplit(str: string, delimiterPattern: string) {
  //   if (!str) return [];

  //   const MAX_TOKENS = 500;
  //   const CHUNK_SIZE = 200;

  //   // 转义特殊字符，并构建用于分割的正则表达式
  //   const regexPattern = delimiterPattern
  //     .split('')
  //     .map(delimiter => `\\${delimiter}`)
  //     .join('|');

  //   const DELIMITER_REGEX = new RegExp(`(${regexPattern})`);
  //   const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;

  //   let tokens = [];
  //   let processedLength = 0;

  //   const segments = str.split(/(<mark>.*?<\/mark>)/gi);

  //   for (const segment of segments) {
  //     if (tokens.length >= MAX_TOKENS) break;
  //     const isMark = MARK_REGEX.test(segment);

  //     const normalTokens = segment
  //       .split(DELIMITER_REGEX)
  //       .filter(Boolean)
  //       .slice(0, MAX_TOKENS - tokens.length);

  //     tokens.push(
  //       ...normalTokens.map(t => {
  //         processedLength += t.length;
  //         return {
  //           text: t,
  //           isMark,
  //           isCursorText: !DELIMITER_REGEX.test(t),
  //         };
  //       }),
  //     );
  //   }

  //   if (processedLength < str.length) {
  //     const remaining = str.slice(processedLength);
  //     const chunkCount = Math.ceil(remaining.length / CHUNK_SIZE);

  //     for (let i = 0; i < chunkCount; i++) {
  //       tokens.push({
  //         text: remaining.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
  //         isMark: false,
  //         isCursorText: false,
  //       });
  //     }
  //   }

  //   return tokens;
  // }

  private escapeString(val: string) {
    const map = {
      '&amp;': '&',
      '&lt;': '<',
      '&gt;': '>',
      '&quot;': '"',
      '&#x27;': "'",
      // ' ': '\u2002',
    };

    return typeof val !== 'string'
      ? `${val}`
      : val.replace(RegExp(`(${Object.keys(map).join('|')})`, 'g'), match => map[match]);
  }

  private getSplitList(field: any, content: any, forceSplit = false) {
    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = this.escapeString(`${content}`);

    if (this.isVirtualObjField(field)) {
      return this.convertVirtaulObjToArray();
    }

    if (this.isAnalyzed(field) || forceSplit) {
      // 这里进来的都是开了分词的情况
      return optimizedSplit(value, this.getCurrentFieldRegStr(field));
    }

    const formatValue = value.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
    const isMark = new RegExp(markRegStr).test(value);
    return [
      {
        text: formatValue,
        isCursorText: true,
        isMark,
      },
    ];
  }
}
