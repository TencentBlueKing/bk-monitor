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

export interface IDetailData {
  access_token: string;
  auto_discover?: boolean;
  bk_biz_id?: string;
  bk_data_id: string;
  bk_event_group_id?: string;
  data_label?: string;
  desc?: string;
  event_info_list?: any[];
  is_platform?: boolean;
  is_readonly?: boolean;
  last_time?: number | string;
  metric_json?: any[];
  name: string;
  protocol?: string;
  scenario: string;
  scenario_display: string[];
  table_id?: string;
  time_series_group_id?: string;
}

export interface IEditParams {
  bk_event_group_id?: string;
  data_label?: string;
  is_enable: boolean;
  is_platform?: boolean;
  name: string;
  scenario: string;
  time_series_group_id?: string;
}

export interface IParams {
  bk_event_group_id?: string;
  time_range: string;
  time_series_group_id?: string;
}

export interface IRefreshList {
  list: { name: string; value: number }[];
  value: number;
}

export interface IShortcuts {
  list: { name: string; value: number }[];
  value: number;
}

export interface ISideslider {
  data: Record<string, any>;
  isShow: boolean;
  title: string;
}
