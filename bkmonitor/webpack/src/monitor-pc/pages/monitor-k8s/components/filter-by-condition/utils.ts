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
export enum EGroupBy {
  container = 'container',
  namespace = 'namespace',
  pod = 'pod',
  workload = 'workload',
}

export interface IFilterByItem {
  key: string;
  value: string[];
  method?: string;
}

interface IValue {
  id: string;
  name: string;
}

export interface ITagListItem {
  key: string;
  id: string;
  name: string;
  values: IValue[];
}

export interface IGroupOptionsItem {
  id: string;
  name: string;
  count: number;
}
export interface IValueItem {
  id: string;
  name: string;
  checked: boolean;
  count?: number;
  list?: {
    id: string;
    name: string;
    checked: boolean;
  }[];
}

export const GROUP_OPTIONS = [
  {
    id: EGroupBy.namespace,
    name: 'namespace',
    count: 12,
    list: [
      {
        id: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
        name: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
      },
      {
        id: '监控测试集群(BCS-1234562)',
        name: '监控测试集群(BCS-1234562)',
      },
      {
        id: '监控测试集群(BCS-1234563)',
        name: '监控测试集群(BCS-1234563)',
      },
      {
        id: '监控测试集群(BCS-1234564)',
        name: '监控测试集群(BCS-1234564)',
      },
      {
        id: '监控测试集群(BCS-1234565)',
        name: '监控测试集群(BCS-1234565)',
      },
      {
        id: '监控测试集群(BCS-1234566)',
        name: '监控测试集群(BCS-1234566)',
      },
      {
        id: '监控测试集群(BCS-1234567)',
        name: '监控测试集群(BCS-1234567)',
      },
      {
        id: '监控测试集群(BCS-1234568)',
        name: '监控测试集群(BCS-1234568)',
      },
      {
        id: '监控测试集群(BCS-1234569)',
        name: '监控测试集群(BCS-1234569)',
      },
      {
        id: '监控测试集群(BCS-12345610)',
        name: '监控测试集群(BCS-12345610)',
      },
    ],
  },
  {
    id: EGroupBy.workload,
    name: 'workload',
    count: 12,
    list: [
      {
        id: 'cate1',
        name: 'cate1',
        count: 12,
        list: [
          {
            id: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
            name: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
          },
          {
            id: '监控测试集群(BCS-1234562)',
            name: '监控测试集群(BCS-1234562)',
          },
          {
            id: '监控测试集群(BCS-1234563)',
            name: '监控测试集群(BCS-1234563)',
          },
          {
            id: '监控测试集群(BCS-1234564)',
            name: '监控测试集群(BCS-1234564)',
          },
          {
            id: '监控测试集群(BCS-1234565)',
            name: '监控测试集群(BCS-1234565)',
          },
          {
            id: '监控测试集群(BCS-1234566)',
            name: '监控测试集群(BCS-1234566)',
          },
          {
            id: '监控测试集群(BCS-1234567)',
            name: '监控测试集群(BCS-1234567)',
          },
          {
            id: '监控测试集群(BCS-1234568)',
            name: '监控测试集群(BCS-1234568)',
          },
          {
            id: '监控测试集群(BCS-1234569)',
            name: '监控测试集群(BCS-1234569)',
          },
          {
            id: '监控测试集群(BCS-12345610)',
            name: '监控测试集群(BCS-12345610)',
          },
        ],
      },
      {
        id: 'cate2',
        name: 'cate2',
        count: 12,
        list: [
          {
            id: '监控测试集群(BCS-1234561)a',
            name: '监控测试集群(BCS-1234561)a',
          },
          {
            id: '监控测试集群(BCS-1234562)b',
            name: '监控测试集群(BCS-1234562)b',
          },
          {
            id: '监控测试集群(BCS-1234563)c',
            name: '监控测试集群(BCS-1234563)c',
          },
          {
            id: '监控测试集群(BCS-1234564)c',
            name: '监控测试集群(BCS-1234564)c',
          },
        ],
      },
      {
        id: 'cate3',
        name: 'cate3',
        count: 12,
        list: [],
      },
      {
        id: 'cate4',
        name: 'cate4',
        count: 12,
        list: [],
      },
      {
        id: 'cate5',
        name: 'cate5',
        count: 12,
        list: [],
      },
    ],
  },
  {
    id: EGroupBy.pod,
    name: 'pod',
    count: 12,
    list: [
      {
        id: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
        name: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
      },
      {
        id: '监控测试集群(BCS-1234562)',
        name: '监控测试集群(BCS-1234562)',
      },
      {
        id: '监控测试集群(BCS-1234563)',
        name: '监控测试集群(BCS-1234563)',
      },
      {
        id: '监控测试集群(BCS-1234564)',
        name: '监控测试集群(BCS-1234564)',
      },
      {
        id: '监控测试集群(BCS-1234565)',
        name: '监控测试集群(BCS-1234565)',
      },
      {
        id: '监控测试集群(BCS-1234566)',
        name: '监控测试集群(BCS-1234566)',
      },
      {
        id: '监控测试集群(BCS-1234567)',
        name: '监控测试集群(BCS-1234567)',
      },
      {
        id: '监控测试集群(BCS-1234568)',
        name: '监控测试集群(BCS-1234568)',
      },
      {
        id: '监控测试集群(BCS-1234569)',
        name: '监控测试集群(BCS-1234569)',
      },
      {
        id: '监控测试集群(BCS-12345610)',
        name: '监控测试集群(BCS-12345610)',
      },
    ],
  },
  {
    id: EGroupBy.container,
    name: 'container',
    count: 12,
    list: [
      {
        id: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
        name: '监控测试集群(BCS-1234561)xxxxxxxxxxxxxxxx',
      },
      {
        id: '监控测试集群(BCS-1234562)',
        name: '监控测试集群(BCS-1234562)',
      },
      {
        id: '监控测试集群(BCS-1234563)',
        name: '监控测试集群(BCS-1234563)',
      },
      {
        id: '监控测试集群(BCS-1234564)',
        name: '监控测试集群(BCS-1234564)',
      },
      {
        id: '监控测试集群(BCS-1234565)',
        name: '监控测试集群(BCS-1234565)',
      },
      {
        id: '监控测试集群(BCS-1234566)',
        name: '监控测试集群(BCS-1234566)',
      },
      {
        id: '监控测试集群(BCS-1234567)',
        name: '监控测试集群(BCS-1234567)',
      },
      {
        id: '监控测试集群(BCS-1234568)',
        name: '监控测试集群(BCS-1234568)',
      },
      {
        id: '监控测试集群(BCS-1234569)',
        name: '监控测试集群(BCS-1234569)',
      },
      {
        id: '监控测试集群(BCS-12345610)',
        name: '监控测试集群(BCS-12345610)',
      },
    ],
  },
];
