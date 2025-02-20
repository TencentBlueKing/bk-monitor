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

export enum EMode {
  ql = 'ql',
  ui = 'ui',
}
export enum ECondition {
  and = 'and',
}
export enum EMethod {
  eq = 'eq',
  exclude = 'exclude',
  include = 'include',
  ne = 'ne',
}
export enum EFieldType {
  all = 'all',
  date = 'date',
  integer = 'integer',
  keyword = 'keyword',
  text = 'text',
}

export const fieldTypeMap = {
  all: {
    name: window.i18n.tc('数字'),
    icon: '*',
    color: '#979BA5',
    bgColor: '#E8EAF0',
  },
  integer: {
    name: window.i18n.tc('数字'),
    icon: 'icon-monitor icon-number',
    color: '#60A087',
    bgColor: '#DDEBE6',
  },
  keyword: {
    name: window.i18n.tc('字符串'),
    icon: 'icon-monitor icon-string',
    color: '#6498B3',
    bgColor: '#D9E5EB',
  },
  text: {
    name: window.i18n.tc('文本'),
    icon: 'icon-monitor icon-text',
    color: '#508CC8',
    bgColor: '#E1E7F2',
  },
  date: {
    name: window.i18n.tc('时间'),
    icon: 'icon-monitor icon-mc-time',
    color: '#CDAE71',
    bgColor: '#EDE7DB',
  },
};
export interface IFilterField {
  name: string;
  alias: string;
  type: EFieldType;
  is_option_enabled: boolean; // 是否可自定选项
  supported_operations: {
    alias: string;
    value: EMethod;
    options?: {
      label: string;
      name: string;
    };
  }[]; // 支持的操作
}
export interface IFilterItem {
  key: { id: string; name: string };
  condition: { id: ECondition; name: string };
  method: { id: EMethod; name: string };
  value: { id: string; name: string }[];
  hide?: boolean;
}
export const MODE_LIST = [
  { id: EMode.ui, name: window.i18n.tc('UI 模式') },
  { id: EMode.ql, name: window.i18n.tc('语句模式') },
];

/**
 * 获取字符长度，汉字两个字节
 * @param str 需要计算长度的字符
 * @returns 字符长度
 */
export function getCharLength(str) {
  const len = str.length;
  let bitLen = 0;

  for (let i = 0; i < len; i++) {
    if ((str.charCodeAt(i) & 0xff00) !== 0) {
      bitLen += 1;
    }
    bitLen += 1;
  }
  return bitLen;
}
