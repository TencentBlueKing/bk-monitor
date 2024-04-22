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

export interface metric {
  aliaName?: string;
  englishName?: string;
  groupId?: string;
  metric?: string;
  type?: string;
  unit?: string;
  dimension_list?: { id: string; name: string }[];
}
export interface variable {
  value: string[];
  dimension: string;
  dimensionList: metric[];
  aliaName: string;
  preview: { label?: string; value?: string }[];
}

export interface collectConfigParams {
  variableResult: { key: string; value: string[]; groupId?: string; name: string }[]; // 变量结果
  metricGroup: {
    id: string;
    metrics: metric[];
    result_table_id: string;
  }[]; // 指标集
  type: 'collect-config';
  groupBy?: { key: string; value: string[]; groupId?: string; name: string }[];
  dimensionsPreviews?: { [propName: string]: variable['preview'] };
}
export interface viewSettingParams {
  variableResult: collectConfigParams['groupBy'];
}

export interface orderList {
  id: string;
  title: string;
  panels: {
    hidden: boolean;
    id: string;
    title: string;
  }[];
}

export interface sceneList {
  name: string;
  variables: { id: string; name: string }[];
}

export interface addSceneResult {
  name: string;
  variables: sceneList['variables'];
  order: orderList[];
}
