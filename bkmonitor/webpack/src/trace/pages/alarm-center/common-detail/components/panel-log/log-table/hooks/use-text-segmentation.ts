/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import LuceneSegment from '../utils/lucene.segment';
import { optimizedSplit } from '../utils/utils';

import type { IFieldInfo } from '../typing';

export type FormatterConfig = {
  options?: {
    content: boolean | number | string;
    data: any;
    field: IFieldInfo;
  };
};
export default class UseTextSegmentation {
  options = {
    field: null,
    content: '',
    data: {},
  };
  constructor(cfg: FormatterConfig) {
    Object.assign(this.options, cfg.options ?? {});
  }

  convertJsonStrToObj(str: string) {
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

  convertVirtaulObjToArray() {
    const target = this.options.data[this.options.field.field_name] ?? this.convertJsonStrToObj(this.options.content);

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

  escapeString(val: string) {
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

  getSplitList(field: IFieldInfo, content: any, forceSplit = false) {
    /** 检索高亮分词字符串 */
    const value = this.escapeString(`${content}`);

    if (this.isVirtualObjField(field)) {
      return this.convertVirtaulObjToArray();
    }

    if (this.isAnalyzed(field) || forceSplit) {
      if (field.tokenize_on_chars) {
        // 这里进来的都是开了分词的情况
        return optimizedSplit(value, field.tokenize_on_chars);
      }
      const luceneSegment = new LuceneSegment();
      return luceneSegment.split(value, 1000);
    }
    const markRegStr = '<mark>(.*?)</mark>';
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

  isAnalyzed(field: IFieldInfo) {
    return field?.is_analyzed ?? false;
  }
  isJSONStructure(str: string) {
    const trimmed = str.trim();
    const len = trimmed.length;
    if (len === 0) {
      return false;
    } // 空字符串直接返回

    const first = trimmed[0];
    const last = trimmed[len - 1];

    return (first === '{' && last === '}') || (first === '[' && last === ']');
  }
  isVirtualObjField(field: IFieldInfo) {
    return (field?.is_virtual_obj_node ?? false) && field?.field_type === 'object';
  }
}
