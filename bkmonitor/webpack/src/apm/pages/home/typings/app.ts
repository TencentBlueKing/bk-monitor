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
import type { INodeType, TargetObjectType } from 'monitor-pc/components/monitor-ip-selector/typing';

export interface IAppListItem {
  app_alias: string;
  app_name: string;
  application_id: number;
  data_status: string;
  firstCode: string;
  firstCodeColor: string;
  loading: false;
  metric_result_table_id: string;
  profiling_data_status: string;
  service_count?: number;
  trace_result_table_id: string;
  permission: {
    [key: string]: boolean;
  };
}

export interface ICreateAppFormData {
  desc: string;
  enableProfiling: boolean;
  enableTracing: boolean;
  enName: string;
  name: string;
  pluginId: string;
  plugin_config?: {
    data_encoding: string;
    paths: string[];
    target_node_type: INodeType;
    target_nodes: any[];
    target_object_type: TargetObjectType;
  };
}

export interface IGuideLink {
  access_url: string;
  best_practice: string;
  metric_description: string;
}
