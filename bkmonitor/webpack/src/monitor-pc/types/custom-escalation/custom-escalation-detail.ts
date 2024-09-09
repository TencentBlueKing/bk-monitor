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
export interface ISideslider {
  isShow: boolean;
  title: string;
  data: Record<string, any>;
}

export interface IParams {
  time_range: string;
  bk_event_group_id?: string;
  time_series_group_id?: string;
}

export interface IEditParams {
  bk_event_group_id?: string;
  time_series_group_id?: string;
  name: string;
  scenario: string;
  is_enable: boolean;
  data_label: string;
  is_platform: boolean;
}

export interface IDetailData {
  bk_data_id: string;
  access_token: string;
  name: string;
  scenario: string;
  bk_event_group_id?: string;
  time_series_group_id?: string;
  scenario_display: string[];
  event_info_list?: any[];
  metric_json?: any[];
  last_time?: number | string;
  table_id?: string;
  data_label?: string;
  is_platform?: boolean;
  is_readonly?: boolean;
  protocol?: string;
  desc?: string;
  bk_biz_id?: string;
}

export interface IShortcuts {
  list: { value: number; name: string }[];
  value: number;
}

export interface IRefreshList {
  list: { value: number; name: string }[];
  value: number;
}
