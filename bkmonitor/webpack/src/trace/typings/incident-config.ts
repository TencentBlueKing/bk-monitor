/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

// 配置列表响应
export interface ConfigListData<T> {
  current_page: number;
  has_next: boolean;
  has_previous: boolean;
  objects: ConfigObject<T>[];
  total_items: number;
  total_pages: number;
}

// 配置列表项
export interface ConfigObject<T> {
  bk_tenant_id?: string;
  config_type?: string;
  content: T;
  created_at?: string;
  created_by?: string;
  id: number;
  scope_id?: string;
  scope_type?: string;
  scope_value?: string;
  updated_at?: string;
  updated_by?: string;
}

// 数据接入 - 配置项
export interface DataSourceConfigItem {
  display_name: string;
  module: Record<string, ModuleCell>;
  name: string;
}

// 数据接入 content
export interface DataSourceContent {
  config: DataSourceConfigItem[];
  labels: DataSourceLabelItem[];
}

// 数据接入 - 标签项
export interface DataSourceLabelItem {
  display_name: string;
  name: string;
}

// 获取配置列表参数
export interface FetchConfigListParams {
  bk_biz_id?: number;
  config_type?: string;
  scope_type?: string;
  scope_value?: string;
}

// 数据接入 - 单元格
export interface ModuleCell {
  connect_status: 'connect' | 'empty' | 'unconnect';
  select_status: string;
}
