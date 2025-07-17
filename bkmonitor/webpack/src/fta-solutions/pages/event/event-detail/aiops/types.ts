/* eslint-disable @typescript-eslint/no-duplicate-enum-values */
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
export enum ETabNames {
  diagnosis = 'diagnosis',
  dimension = 'dimension',
  index = 'index',
}

export enum DimensionTypes {
  application_check = 'icon-mc-business',
  component = 'icon-mc-component',
  hardware_device = 'icon-mc-equipment',
  host_device = 'icon-mc-host',
  host_process = 'icon-mc-aiops-process',
  kubernetes = 'icon-mc-aiops-kubernetes',
  os = 'icon-operating-system',
  other_rt = 'icon-mc-other',
  service_module = 'icon-mc-service-test',
  uptimecheck = 'icon-mc-service-test',
}

export interface IInfo {
  anomaly_dimension_count?: number;
  anomaly_dimension_value_count?: number;
  configured_metric_count?: number;
  recommended_metric_count?: number;
  default_column?: number;
  recommended_metric?: number;
}

export interface IDistribution {
  metric_alias: string;
  median: number;
  data: any[];
  [key: string]: any;
}
export interface IAnomalyDimensions {
  anomaly_dimension?: string;
  anomaly_dimension_alias?: string;
  dimension_anomaly_value_count?: number;
  dimension_value_total_count?: number;
  dimension_value_percent?: number;
  anomaly_score_top10?: any[];
  anomaly_score_distribution?: IDistribution;
  [key: string]: any;
}

export enum EventReportType {
  Click = 'event_detail_click',
  Tips = 'event_detail_tips',
  View = 'event_detail_view',
}

export interface TabConfig {
  name: string;
  icon: string;
  titleKey: string;
  loading: boolean;
  error?: string;
  infoType: 'dimensionInfo' | 'indexInfo';
  contentRenderer?: () => void;
  dataItems: {
    path: string;
    labelKey: string;
    showComma?: boolean;
  }[];
}

export interface IIncidentDetail {
  id: string;
  incident_name: string;
  status_alias: string;
  duration: string;
  bk_biz_name: string;
  current_topology: Record<string, unknown>;
  begin_time: number;
  end_time: number;
}
