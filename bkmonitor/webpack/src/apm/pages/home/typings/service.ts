export interface IAPMService {
  app_name: string;
  avg_duration: IMetric;
  category: string;
  collect: ICollect;
  error_rate: IMetric;
  kind: string;
  language: string;
  log_data_status: IDataStatus;
  metric_data_status: IDataStatus;
  operation: IOperation[];
  profiling_data_status: IDataStatus;
  request_count: IMetric;
  service_name: IServiceName;
  trace_data_status: IDataStatus;
  type: string;
}

export interface ICollect {
  api: string;
  is_collect: boolean;
  params: IParams;
}

export interface IDataStatus {
  icon: string;
}

export interface IMetric {
  datapoints: any; // You can replace 'any' with a more specific type if you have it
  unit: null | string;
}

export interface IOperation {
  icon: string;
  key: string;
  target: string;
  url: string;
  value: string;
}

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
  app_name: string;
  service_name: string;
}

export interface IServiceName {
  icon: string;
  key: string;
  syncTime: boolean;
  target: string;
  url: string;
  value: string;
}
