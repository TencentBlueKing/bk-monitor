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

import type { DataTypeItem, RetrievalFormData } from './profiling-retrieval';

export enum DetailType {
  Application = 'application',
  UploadFile = 'uploadFile',
}

export enum PanelType {
  Favorite = 'favorite',
  Search = 'search',
}

export interface FileDetail {
  /** 应用名称 */
  app_name: string;
  /** 错误信息 */
  content: string;
  /** 数据上报时间 */
  data_time: string;
  /** 数据类型 */
  data_types: DataTypeItem[];
  /** 文件md5 */
  file_md5: string;
  /** 文件名 */
  file_name: string;
  /** 文件大小 */
  file_size: number;
  /** 文件类型 */
  file_type: string;
  /** 操作人 */
  operator: string;
  /** 原文件名 */
  origin_file_name: string;
  profile_id: string;
  /** 查询结束时间 */
  query_end_time: number;
  /** 查询开始时间 */
  query_start_time: number;
  /** 状态 */
  status: string;
  /** 上传时间 */
  uploaded_time: string;
}

export interface SearchState {
  /** 是否开启自动查询功能 */
  autoQuery: boolean;
  /** 自动查询时间器 */
  autoQueryTimer: number;
  /** 表单数据 */
  formData: RetrievalFormData;
  /** 是否展示查询面板 */
  isShow: boolean;
  /** 查询loading */
  loading: boolean;
}

export interface ServicesDetail {
  /** 应用 */
  app_name: string;
  /** 采样频率 */
  // frequency: string;
  /** 创建时间 */
  create_time: string;
  /** 数据类型 */
  data_types: DataTypeItem[];
  /** 最近上报时间 */
  last_report_time: string;
  /** 模块 */
  name: string;
  /** 周期 */
  period: string;
  /** 周期类型 */
  period_type: string;
}
