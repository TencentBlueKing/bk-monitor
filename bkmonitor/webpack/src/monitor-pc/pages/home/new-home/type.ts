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

export interface ISearchItem {
  bk_biz_id?: string;
  bk_biz_name?: string;
  name?: string;
  bk_host_innerip?: string;
  bk_cloud_id?: string;
  bk_cloud_name?: string;
  bk_host_name?: string;
  bk_host_id?: string;
  url?: string;
  alert_id?: number;
  nameSearch?: string;
  type?: string;
  strategy_id?: number;
  app_name?: string;
  trace_id?: string;
  bcs_cluster_id?: string;
}
export interface IDataItem {
  [key: string]: any;
}

export interface ISearchListItem {
  type: string;
  name: string;
  items: ISearchItem[];
}
export interface IRouteItem {
  name?: string;
  icon?: string;
  id?: string;
  path?: string;
  href?: string;
  canStore?: boolean;
}

export interface IRecentList {
  function: string;
  items: IRecentItem[];
  name: string;
  icon?: string;
}

interface IRecentItem {
  bk_biz_id: number;
  bk_biz_name: string;
  name?: string;
  url?: string;
}

export interface IRecentAlarmTab {
  bk_biz_id: number;
  bk_biz_name: string;
}

export interface IAlarmGraphConfig {
  name: string;
  strategy_ids: number[];
  status?: IAlarmGraphStatus[];
  strategy_names?: string[];
}

interface IAlarmGraphStatus {
  name: string;
  status: string;
  strategy_id: number;
}
