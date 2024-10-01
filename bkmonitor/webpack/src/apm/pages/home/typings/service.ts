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
export interface IParams {
  service_name: string;
  app_name: string;
}

export interface ICollect {
  is_collect: boolean;
  api: string;
  params: IParams;
}

export interface IServiceName {
  target: string;
  value: string;
  url: string;
  key: string;
  icon: string;
  syncTime: boolean;
}

export interface IDataStatus {
  icon: string;
}

export interface IOperation {
  target: string;
  value: string;
  url: string;
  key: string;
  icon: string;
}

export interface IMetric {
  datapoints: any; // You can replace 'any' with a more specific type if you have it
  unit: null | string;
}

export interface IAPMService {
  app_name: string;
  collect: ICollect;
  service_name: IServiceName;
  type: string;
  language: string;
  metric_data_status: IDataStatus;
  log_data_status: IDataStatus;
  trace_data_status: IDataStatus;
  profiling_data_status: IDataStatus;
  operation: IOperation[];
  category: string;
  kind: string;
  request_count: IMetric;
  error_rate: IMetric;
  avg_duration: IMetric;
}
