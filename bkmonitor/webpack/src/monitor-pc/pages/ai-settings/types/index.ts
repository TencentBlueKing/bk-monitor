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

export type SceneType = 'host'; // host | k8s

export type NotificationType = 'INSTANCE' | 'SERVICE_TEMPLATE' | 'SET_TEMPLATE' | 'TOPO';

export type FieldType = 'host_service_template' | 'host_set_template' | 'host_topo_node' | 'ip';

export interface SchemeItem {
  id: number;
  name: string;
  ts_freq: number;
  ts_depend: string;
  visual_type: string;
  description: string;
  instruction: string;
  is_default: boolean;
  latest_release_id: number;
}

export interface AnomalyDetectionBase {
  is_enabled?: boolean;
  default_plan_id: number | undefined;
  default_sensitivity?: number;
  [key: string]: any;
}

export interface HostInfo {
  subMessageCount: number;
  messageCount: number;
  message: string;
  subMessage: string;
}

export interface AiSetting {
  kpi_anomaly_detection: AnomalyDetectionBase;
  multivariate_anomaly_detection: {
    [key in SceneType]: AnomalyDetectionBase;
  };
}

export interface CheckedData {
  type: NotificationType;
  data: TopologyData[];
}

export interface TopologyData {
  SERVICE_TEMPLATE?: number;
  agent_error_count?: number;
  count?: number;
  all_host?: string[];
  node_path?: string;
  labels?: { first: string; second: string }[];
  bk_biz_id?: number;
  bk_inst_id?: number;
  bk_inst_name?: string;
  bk_obj_id?: string;
  instances_count?: number;
  nodes_count?: number;

  bk_cloud_id?: number;
  agent_status?: string;
  bk_cloud_name?: string;
  bk_os_type?: string;
  bk_supplier_id?: string;
  is_external_ip?: boolean;
  is_innerip?: boolean;
  is_outerip?: false;
  ip?: string;
}

export interface HostValueItem {
  field: FieldType;
  value: TopologyData[];
  method: string;
}

export const targetFieldMap: { [key in NotificationType]: FieldType } = {
  INSTANCE: 'ip',
  TOPO: 'host_topo_node',
  SERVICE_TEMPLATE: 'host_service_template',
  SET_TEMPLATE: 'host_set_template',
};
