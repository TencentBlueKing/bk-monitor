/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import type { Process, Span } from '../components/trace-view/typings';

export enum EListItemType {
  events = 'Events',
  process = 'Process',
  stageTime = 'StageTime',
  tags = 'Tags',
}

export enum ETopoType {
  service = 'service',
  time = 'time',
}

export type DirectionType = 'ltr' | 'rtl';

export interface IDetailInfo {
  [key: string]: any;
  app_name?: string;
  category?: string; // 调用类型
  error?: boolean; // 入口服务感叹号
  hierarchy_count: number;
  max_duration: number;
  min_duration: number;
  product_time: number;
  root_endpoint?: string;
  root_service?: string;
  root_span_id: string;
  service_count: number;
  time_error: boolean;
  trace_duration: number;
  trace_end_time?: number;
  trace_start_time?: number;
  status_code?: {
    type: string;
    value: number;
  };
}

export interface IDiffInfo {
  baseline: number;
  comparison: number;
  diff: number;
  mark: 'added' | 'changed' | 'removed' | 'unchanged';
}

export interface IEventsItem {
  titleRight?: any;
  list: {
    content: ITagContent[];
    header: {
      date: string;
      duration: string;
      name: string;
    };
    isExpan: boolean;
  }[];
}

export interface IInfo {
  list: IListItem[];
  title: string;
  header: {
    others: {
      content: any;
      label: string;
      title: string;
    }[];
    timeTag: string; // 时间
    // 头部
    title: string; // 标题
  };
}

export interface IListItem {
  [EListItemType.events]?: IEventsItem;
  [EListItemType.process]?: IProcessItem;
  [EListItemType.stageTime]?: IStageTimeItem;
  [EListItemType.tags]?: ITagsItem;
  isExpan: boolean;
  title?: string;
  type: EListItemType;
}

export interface IProcessItem {
  title: string;
  list: {
    content?: string;
    label: string;
    query_key: string;
    query_value: any;
  }[];
}

export interface IQueryParams {
  agg_method?: string;
  app_name?: string;
  bk_biz_id?: number;
  data_type?: string;
  diagram_types?: string[];
  diff_filter_labels?: any;
  diff_profile_id?: string;
  end: number;
  filter_labels?: Record<string, string>;
  global_query: boolean;
  is_compared?: boolean;
  offset?: number;
  profile_id?: string;
  sort?: string;
  start: number;
}

export interface IServiceSpanListItem {
  collapsed: boolean;
  collapsed_span_num: number;
  color: string;
  display_name: string;
  duration: number;
  icon: string;
  kind: number;
  operation_name: string;
  service_name: string;
  span_id: string;
  span_ids: string[];
  span_name: string;
  start_time: number;
}

export interface ISpanClassifyItem {
  app_name?: string;
  color: string;
  count: number;
  filter_key: string;
  filter_value: number | string;
  icon: string;
  name: string;
  type: string;
}

export interface ISpanDetail {
  origin_data: IOriginData;
  trace_tree: {
    processes: {
      [key: string]: object;
    };
    spans: {
      app_name: string;
      attributes: any[];
      color: string;
      duration: number;
      error: boolean;
      events: any[];
      flags: number;
      icon: string;
      id: string;
      kind: number;
      logs: any[];
      message: string;
      operationName: string;
      processID: string;
      references: {
        refType: string;
        spanID: string;
        traceID: string;
      }[];
      resource: any[];
      service_name: string;
      spanID: string;
      startTime: number;
      tags: {
        key: string;
        query_key: string;
        query_value: string;
        type: string;
        value: string;
      }[];
      traceID: string;
    }[];
  };
}

export interface ISpanListItem {
  [key: string]: any;
  elapsed_time: number | string;
  end_time: number | string;
  kind: number;
  parent_span_id: string;
  span_id: string;
  span_name: string;
  start_time: number | string;
  time: string;
  trace_id: string;
  trace_state: string;
  resource: {
    'bk.instance.id': string;
    bk_data_id: number;
    'service.name': string;
    'service.version': string;
    'telemetry.sdk.language': string;
    'telemetry.sdk.name': string;
    'telemetry.sdk.version': string;
  };
  status: {
    code: number;
    message: string;
  };
  status_code: {
    type: string;
    value: string;
  };
}

export interface IStageTimeItem {
  // 阶段耗时
  active: string;
  content: {
    [propName: string]: IStageTimeItemContent[];
  };
  list: {
    error: boolean;
    errorMsg: string;
    id: string;
    label: string;
  }[];
}

export interface IStageTimeItemContent {
  gapTime?: string;
  type: 'gapTime' | 'useTime';
  useTime?: {
    gap: { type: 'toLeft' | 'toRight'; value: string };
    tags: string[];
  };
}

export interface ITagContent {
  content?: string;
  isFormat?: boolean;
  label: string;
  query_key: string;
  query_value: any;
  type: string;
}
export interface ITagsItem {
  list: ITagContent[];
}

export interface ITopoNode {
  bgColor: string;
  collapsed: boolean;
  color: string;
  diff_info?: Record<string, IDiffInfo>;
  duration: number;
  error: boolean;
  icon: string;
  id: string;
  operationName: string;
  service_name: string;
  spans: string[];
}
export interface ITopoRelation {
  source: string;
  target: string;
}
export interface ITraceData extends ITraceListItem {
  [key: string]: any;
  ebpf_enabled?: boolean;
  original_data: any[];
  span_classify: ISpanClassifyItem[];
  topo_nodes: ITopoNode[];
  topo_relation: ITopoRelation[];
  trace_tree?: ITraceTree;
  streamline_service_topo?: {
    edges: any[];
    nodes: any[];
  };
}

export interface ITraceListItem {
  [key: string]: any;
  appName?: string;
  duration?: string;
  entryEndpoint?: string;
  entryService?: string;
  status?: string;
  statusCode?: number;
  time?: number;
  trace_id: string;
  trace_info: IDetailInfo;
  traceID?: string;
  type?: string;
}
export interface ITraceTree {
  [key: string]: any;
  duration?: number;
  endTime?: number;
  entryEndpoint?: string;
  entryService?: string;
  processes?: Record<string, Process>;
  spans: Span[];
  startTime?: number;
  status?: string;
  statusCode?: string;
  time?: string;
  traceID?: string;
  type?: string;
}

export interface OriginCrossAppSpanMap {
  [key: string]: Span[];
}

interface IOriginData {
  elapsed_time: number;
  end_time: number;
  events: any[];
  kind: number;
  links: any[];
  parent_span_id: string;
  span_id: string;
  span_name: string;
  start_time: number;
  time: string;
  trace_id: string;
  trace_state: string;
  attributes: {
    key: string;
    query_key: string;
    query_value: number;
    type: string;
    value: number;
  };
  resource: {
    key: string;
    query_key: string;
    query_value: string;
    type: string;
    value: string;
  };
  status: {
    code: number;
    message: string;
  };
}
