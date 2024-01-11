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

export enum SearchType {
  Profiling = 'profiling',
  Upload = 'upload'
}

export enum ConditionType {
  /** 查询项 */
  Where = 'where',
  /** 对比项 */
  Comparison = 'comparison'
}

export interface ConditionItem {
  key: string;
  method: 'eq';
  value: string | string[];
}
export interface RetrievalFormData {
  /** 查询类型 */
  type: SearchType;
  /** 是否开启对比模式 */
  isComparison: boolean;
  /** 应用/服务 */
  server: {
    app_name: string;
    service_name: string;
  };
  /** 查询项条件 */
  where: ConditionItem[];
  /** 对比项条件 */
  comparisonWhere: ConditionItem[];
}

export const retrievalDataTypeList = [
  {
    id: 'cpu',
    name: 'CPU'
  },
  {
    id: 'mem',
    name: 'MEM'
  },
  {
    id: 'alloc',
    name: 'ALLOC'
  },
  {
    id: 'mutex',
    name: 'MUTEX'
  }
] as const;

export interface ApplicationItem {
  [key: string]: any;
}
