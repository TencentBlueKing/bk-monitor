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
// @ts-expect-error
export const Time_Range_List = [
  {
    id: 0,
    name: 'off 关闭',
  },
  {
    id: 60_000,
    name: '1m',
  },
  {
    id: 300_000,
    name: '5m',
  },
  {
    id: 900_000,
    name: '15m',
  },
  {
    id: 1_800_000,
    name: '30m',
  },
  {
    id: 3_600_000,
    name: '1h',
  },
  {
    id: 7_200_000,
    name: '2h',
  },
  {
    id: 86_400_000,
    name: '1d',
  },
];

export const operatorMapping = {
  '=': '=',
  '!=': '!=',
  '<': '<',
  '>': '>',
  '<=': '<=',
  '>=': '>=',
  exists: '存在',
  'does not exists': '不存在',
  'is true': 'is true',
  'is false': 'is false',
  contains: '包含',
  'not contains': '不包含',
  'contains match phrase': '包含',
  'not contains match phrase': '不包含',
  'all contains match phrase': '全部包含',
  'all not contains match phrase': '全部不包含',
};

export const translateKeys = ['存在', '不存在', '包含', '不包含', '全部包含', '全部不包含'];
