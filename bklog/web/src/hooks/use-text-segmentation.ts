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
import segmentPopInstance from '../global/utils/segment-pop-instance';
import {
  getClickTargetElement,
  resolveOuterValidText,
  setPointerCellClickTargetHandler,
} from './hooks-helper';
import UseSegmentPropInstance from './use-segment-pop';
import { splitRenderText } from '../storage/utils/retrieve-render-meta';

import type { Ref } from 'vue';

export type FormatterConfig = {
  onSegmentClick: (args: any) => void;
  options?: {
    content: boolean | number | string;
    field: any;
    data: any;
    precomputedSegments?: WordListItem[];
  };
};

export type WordListItem = {
  text: string;
  isMark: boolean;
  isCursorText: boolean;
  isBlobWord?: boolean;
  resultRanges?: Array<{ start: number; end: number; keywordIndex?: number }>;
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
  options: FormatterConfig['options'] = {
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
    const target = setPointerCellClickTargetHandler(e, { offsetY, offsetX });
    this.handleSegmentClick(target, value);
  }

  getTextCellClickHandler(e: MouseEvent) {
    const validTextElement = resolveOuterValidText(e.target as HTMLElement);
    if (validTextElement) {
      const { offsetY, offsetX } = getClickTargetElement(e);
      const offsetTarget = setPointerCellClickTargetHandler(e, { offsetY, offsetX });
      this.handleSegmentClick(offsetTarget, validTextElement.textContent);
    }
  }

  getChildNodes(forceSplit = false) {
    let start = 0;
    return this.getSplitList(this.options.field, this.options.content, forceSplit).map(item => {
      Object.assign(item, {
        startIndex: start,
        endIndex: start + item.text.length,
      });
      start += item.text.length;
      return item;
    });
  }

  update(cfg) {
    Object.assign(this.options, cfg.options ?? {});
  }

  formatValue() {
    return this.escapeString(`${this.options.content}`)
      .replace(/<mark>/g, '')
      .replace(/<\/mark>/g, '');
  }

  private getField() {
    return this.options?.field;
  }

  private getCellValue(target) {
    if (typeof target === 'string') {
      return target.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
    }
    return target;
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

    const selected = this.getCellValue(currentValue);
    const fullPlain = this.getCellValue(this.options?.content ?? '');
    let operation = val === 'not' ? 'is not' : val;
    // 与 JSON 分词点击一致：完整 VALUE → is；部分分词 → contains，保证同词多次点击稳定
    if ((val === 'is' || val === 'not') && fullPlain && selected && fullPlain !== selected) {
      operation = val === 'not' ? 'not contains match phrase' : 'contains match phrase';
    }

    const option = {
      fieldName: activeField?.field_name,
      operation,
      value: this.getCellValue(target ?? currentValue),
      depth,
      isNestedField,
    };

    this.onSegmentClick?.({ option, isLink });
    segmentPopInstance.hide();

    if (val === 'is' || val === 'not' || val === 'new-search-page-is') {
      window.getSelection()?.removeAllRanges();
    }
  }

  private isValidTraceId(traceId) {
    const traceIdPattern = /^[a-f0-9]{32}$/;
    return traceIdPattern.test(traceId);
  }

  private handleSegmentClick(target, value) {
    if (!value.toString() || value === '--') {
      return;
    }

    this.clickValue = value;
    const content = this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this));
    const traceView = content.value.querySelector('.bklog-trace-view')?.closest('.segment-event-box') as HTMLElement;
    traceView?.style.setProperty('display', this.isValidTraceId(value) ? 'inline-flex' : 'none');
    segmentPopInstance.show(target, this.getSegmentContent(this.keyRef, this.onSegmentEnumClick.bind(this)));
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

  private isJSONStructure(str: string) {
    const trimmed = str.trim();
    const len = trimmed.length;
    if (len === 0) {
      return false;
    } // 空字符串直接返回

    const first = trimmed[0];
    const last = trimmed[len - 1];

    return (first === '{' && last === '}') || (first === '[' && last === ']');
  }

  private convertJsonStrToObj(str: string) {
    if (this.isJSONStructure(str)) {
      try {
        return JSON.parse(str);
      } catch (e) {
        console.error(e);
        return str;
      }
    }

    return str;
  }

  private convertVirtaulObjToArray() {
    const target = this.options.data[this.options.field.field_name] ?? this.convertJsonStrToObj(`${this.options.content}`);

    const convertObjToArray = (root: object, isValue = false) => {
      const result: Record<string, any>[] = [];

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

        for (const [key, value] of Object.entries(root)) {
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
        }

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
      const newValue = this.escapeString(`${root}`);
      const formatValue = newValue.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
      const isMark = new RegExp(markRegStr).test(newValue);

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
      : val.replace(new RegExp(`(${Object.keys(map).join('|')})`, 'g'), match => map[match]);
  }

  private getSplitList(field: any, content: any, forceSplit = false) {
    // forceSplit 是当前嵌套展示上下文，旧缓存未携带该模式时不能覆盖运行时判断。
    if (!forceSplit && Array.isArray(this.options.precomputedSegments)) {
      return this.options.precomputedSegments;
    }

    const value = this.escapeString(String(content));

    // JSON 解析关闭后的虚拟 Object 是序列化复合值：标点不可点，KEY/VALUE 可点。
    if (this.isVirtualObjField(field)) {
      const rawValue = this.options.data?.[field.field_name] ?? content;
      const serializedValue = rawValue !== null && typeof rawValue === 'object'
        ? JSON.stringify(rawValue)
        : value;
      return splitRenderText(serializedValue, field, { isSerializedComposite: true });
    }

    return splitRenderText(value, field, { forceSplit });
  }
}
