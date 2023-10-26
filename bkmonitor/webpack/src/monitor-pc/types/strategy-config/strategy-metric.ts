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
export interface IDataSource {
  bk_monitor_time_series?: IDataSourceItem;
  log_time_series?: IDataSourceItem;
  bk_data_time_series?: IDataSourceItem;
  custom_time_series?: IDataSourceItem;
  bk_monitor_log?: IDataSourceItem;
  custom_event?: IDataSourceItem;
  bk_monitor_event?: IDataSourceItem;
}
export interface IDataSourceItem {
  count: number;
  dataSourceLabel: string;
  dataTypeLabel: string;
  sourceType: string;
  sourceName: string;
  list: any[];
}
export interface IPage {
  bk_monitor_time_series: number;
  bk_data_time_series: number;
  custom_time_series: number;
  log_time_series: number;
}

export interface ISearchObj {
  keyWord: { values: { id: string; name: string }[]; id: string; name: string }[];
  data: ISearchOption[];
}

export interface IMetric {
  dataSourceLabel: string;
  dataTypeLabel: string;
  id: number;
  metricName: string;
  resultTableId: string;
  relatedId: string;
  relatedName: string;
}

export interface ITimeSelect {
  value: number;
  list: { id: number; name: string }[];
}

export type ITag = {
  value: string;
  list: ITimeSelect['list'];
};

export interface ISearchOption {
  id: string;
  name: string;
  children: any[];
}

export interface IStaticParams {
  bk_biz_id: number;
  data_source_label: string | string[];
  data_type_label: string;
  result_table_label: string;
}
