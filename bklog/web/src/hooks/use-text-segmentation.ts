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

export type FormatterConfig = {
  onSegmentClick: (args: any) => void;
  options?: {
    content: boolean | number | string;
    field: any;
    data: any;
  };
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

  getCellClickHandler(e: MouseEvent, value) {
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

    virtualTarget.style.setProperty('left', `${x}px`);
    virtualTarget.style.setProperty('top', `${y}px`);

    this.handleSegmentClick(virtualTarget, value);
  }

  getTextCellClickHandler(e: MouseEvent) {
    if ((e.target as HTMLElement).classList.contains('valid-text')) {
      this.handleSegmentClick(e.target, (e.target as HTMLElement).innerHTML);
    }
  }

  getChildNodes() {
    let start = 0;
    return this.getSplitList(this.options.field, this.options.content).map(item => {
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

    const activeField = this.getField();
    const target = ['date', 'date_nanos'].includes(activeField?.field_type)
      ? this.options.data?.[activeField?.field_name]
      : currentValue;

    const option = {
      fieldName: activeField?.field_name,
      operation: val === 'not' ? 'is not' : val,
      value: (target ?? currentValue).replace(/<mark>/g, '').replace(/<\/mark>/g, ''),
      depth,
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

  // Object.assign(item, { startIndex: start, endIndex: start + (text?.length ?? 0) });
  private splitParticipleWithStr(str: string, delimiterPattern: string) {
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
        const formatValue = item.replace(/<mark>/g, '').replace(/<\/mark>/g, '');
        list.push({
          text: formatValue,
          isMark: true,
          isCursorText: true,
        });
      } else {
        const arr = item.split(regex);
        arr.forEach(text => {
          if (text) {
            list.push({
              text,
              isMark: false,
              isCursorText: !regex.test(text),
            });
          }
        });
      }
      return list;
    }, []);

    return parts;
  }

  private escapeString(val: string) {
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

  private getSplitList(field: any, content: any) {
    /** 检索高亮分词字符串 */
    const markRegStr = '<mark>(.*?)</mark>';
    const value = this.escapeString(`${content}`);
    if (this.isAnalyzed(field)) {
      // 这里进来的都是开了分词的情况
      return this.splitParticipleWithStr(value, this.getCurrentFieldRegStr(field));
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
