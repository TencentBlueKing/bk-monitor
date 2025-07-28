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
import { Component, Vue } from 'vue-property-decorator';

@Component
export default class documentLinkMixin extends Vue {
  public aggConditionColorMap: {
    '!=': '#FF9C01';
    '<': '#FF9C01';
    '<=': '#FF9C01';
    '=': '#FF9C01';
    '>': '#FF9C01';
    '>=': '#FF9C01';
    AND: '#3A84FF';
    between: '#FF9C01';
    exclude: '#FF9C01';
    include: '#FF9C01';
    is: '#FF9C01';
    'is not': '#FF9C01';
    'is not one of': '#FF9C01';
    'is one of': '#FF9C01';
    like: '#FF9C01';
    OR: '#3A84FF';
    reg: '#FF9C01';
  };
  public aggConditionFontMap: {
    '!=': 'bold';
    '<': 'bold';
    '<=': 'bold';
    '=': 'bold';
    '>': 'bold';
    '>=': 'bold';
    between: 'bold';
    exclude: 'bold';
    include: 'bold';
    like: 'bold';
    reg: 'bold';
  };
  public methodMap: {
    between: 'between';
    eq: '=';
    exclude: 'exclude';
    gt: '>';
    gte: '>=';
    include: 'include';
    is: 'is';
    'is not': 'is not';
    'is not one of': 'is not one of';
    'is one of': 'is one of';
    like: 'like';
    lt: '<';
    lte: '<=';
    neq: '!=';
    nreg: 'nregex';
    reg: 'regex';
  };
}
export const methodMap = {
  gte: '>=',
  gt: '>',
  lte: '<=',
  lt: '<',
  eq: '=',
  neq: '!=',
  like: 'like',
  between: 'between',
  is: 'is',
  'is one of': 'is one of',
  'is not': 'is not',
  'is not one of': 'is not one of',
  include: 'include',
  exclude: 'exclude',
  reg: 'regex',
  nreg: 'nregex',
};
export const aggConditionFontMap = {
  '=': 'bold',
  '>': 'bold',
  '<': 'bold',
  '<=': 'bold',
  '>=': 'bold',
  '!=': 'bold',
  like: 'bold',
  between: 'bold',
  include: 'bold',
  exclude: 'bold',
  reg: 'bold',
};
export const aggConditionColorMap = {
  and: '#3A84FF',
  or: '#3A84FF',
  '=': '#FF9C01',
  '>': '#FF9C01',
  '<': '#FF9C01',
  '<=': '#FF9C01',
  '>=': '#FF9C01',
  '!=': '#FF9C01',
  like: '#FF9C01',
  between: '#FF9C01',
  is: '#FF9C01',
  'is one of': '#FF9C01',
  'is not': '#FF9C01',
  'is not one of': '#FF9C01',
  include: '#FF9C01',
  exclude: '#FF9C01',
  reg: '#FF9C01',
};
