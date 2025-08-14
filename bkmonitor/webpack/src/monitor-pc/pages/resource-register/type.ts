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

export enum EClusterType {
  Argus = 'argus',
  ES = 'elasticsearch',
  Influxdb = 'influxdb',
  Kafka = 'kafka',
  Transfer = 'transfer',
}

/* 表格筛选项 */
export const FILTER_LIST = [
  {
    id: 'all',
    icon: '',
    name: window.i18n.tc('全部'),
  },
  {
    id: EClusterType.Kafka,
    icon: 'icon-Kafka',
    name: window.i18n.tc('Kafka 集群'),
  },
  {
    id: EClusterType.Transfer,
    icon: 'icon-Transfer',
    name: window.i18n.tc('Transfer 集群'),
  },
  {
    id: EClusterType.Influxdb,
    icon: 'icon-DB1',
    name: window.i18n.tc('influxdb 集群'),
  },
  {
    id: EClusterType.ES,
    icon: 'icon-ES',
    name: window.i18n.tc('ES 集群'),
  },
];
export enum EScopes {
  allSpace = 'all-space',
  currentSpace = 'current-space',
  multiSpace = 'multi-space',
  spaceType = 'space-type',
}
export const EsSpaceScopes = [
  { id: EScopes.currentSpace, name: window.i18n.tc('当前业务可见') },
  { id: EScopes.multiSpace, name: window.i18n.tc('多业务选择') },
  { id: EScopes.allSpace, name: window.i18n.tc('全平台') },
  { id: EScopes.spaceType, name: window.i18n.tc('按业务属性选择') },
];

export enum ETableColumn {
  description = 'description',
  name = 'name',
  operate = 'operate',
  operator = 'operator',
  pipeline = 'pipeline',
  status = 'status',
  use = 'use',
}

export interface IChildDataRow {
  host: string;
  port: number;
  schema: any;
  version: any;
}

export interface IInfluxdbChildData {
  id: string;
  isExpand?: boolean;
  name: string;
  data: {
    columns: { id: string; name: string }[];
    data: any[];
  };
}
export interface ITableDataRow {
  cluster_id: number;
  cluster_name: string;
  cluster_type: EClusterType;
  creator: string;
  description: string;
  label: string;
  labelArr: string[];
  pipeline_name?: string;
  username: string;
  childData:
    | any
    | {
        data: IChildDataRow[];
      };
}

export interface ITableRowConfig {
  operationType: string;
  rowData?: any | ITableDataRow;
}
