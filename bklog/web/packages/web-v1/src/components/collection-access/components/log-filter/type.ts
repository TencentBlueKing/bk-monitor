/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

export interface ISelectItem {
  id: string;
  name: string;
  value?: string;
}

export interface ITableRowItem {
  fieldindex: string;
  word: string;
  op: string;
  tableIndex: number;
  logic_op?: logicOpType;
}

type logicOpType = 'and' | 'or';

export type btnType = 'match' | 'none' | 'separator';

/** 操作符列表 */
export const operatorSelectList: ISelectItem[] = [
  {
    id: 'eq',
    name: window.mainComponent.$t('等于'),
  },
  {
    id: 'neq',
    name: window.mainComponent.$t('不等于'),
  },
  {
    id: 'include',
    name: window.mainComponent.$t('包含'),
  },
  {
    id: 'exclude',
    name: window.mainComponent.$t('不包含'),
  },
  {
    id: 'regex',
    name: window.mainComponent.$t('正则匹配'),
  },
  {
    id: 'nregex',
    name: window.mainComponent.$t('正则不匹配'),
  },
];

/** 过滤类型 */
export const btnGroupList: ISelectItem[] = [
  {
    id: 'match',
    name: window.mainComponent.$t('字符串'),
  },
  {
    id: 'separator',
    name: window.mainComponent.$t('分隔符'),
  },
];

/** 操作符映射 */
export const operatorMapping = {
  '!=': 'neq',
};

export const tableRowBaseObj: ITableRowItem = {
  fieldindex: '',
  word: '',
  op: '=',
  tableIndex: 0,
};

export const operatorMappingObj = {
  eq: window.mainComponent.$t('等于'),
  neq: window.mainComponent.$t('不等于'),
  include: window.mainComponent.$t('包含'),
  exclude: window.mainComponent.$t('不包含'),
  regex: window.mainComponent.$t('正则匹配'),
  nregex: window.mainComponent.$t('正则不匹配'),
};
