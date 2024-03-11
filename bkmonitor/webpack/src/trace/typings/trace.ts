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

import { Process, Span } from '../components/trace-view/typings';

export interface IDetailInfo {
  [key: string]: any;
  product_time: number;
  trace_duration: number;
  service_count: number;
  hierarchy_count: number;
  min_duration: number;
  max_duration: number;
  error?: boolean; // 入口服务感叹号
  root_service?: string;
  root_endpoint?: string;
  status_code?: {
    type: string;
    value: number;
  };
  category?: string; // 调用类型
  root_span_id: string;
  time_error: boolean;
  trace_start_time?: number;
  trace_end_time?: number;
  app_name?: string;
}

export interface ISpanClassifyItem {
  type: string;
  name: string;
  icon: string;
  count: number;
  filter_value: string | number;
  filter_key: string;
  color: string;
  app_name?: string;
}

export interface ITraceTree {
  [key: string]: any;
  traceID?: string;
  processes?: Record<string, Process>;
  spans: Span[];
  duration?: number;
  time?: string;
  entryService?: string;
  entryEndpoint?: string;
  statusCode?: string;
  status?: string;
  type?: string;
  startTime?: number;
  endTime?: number;
}

export interface ITopoNode {
  color: string;
  duration: number;
  operationName: string;
  error: boolean;
  icon: string;
  service_name: string;
  id: string;
  collapsed: boolean;
  spans: string[];
  bgColor: string;
  diff_info?: Record<string, IDiffInfo>;
}

export interface IDiffInfo {
  baseline: number;
  comparison: number;
  mark: string;
}

export interface ITopoRelation {
  target: string;
  source: string;
}

export interface ITraceListItem {
  [key: string]: any;
  trace_id: string;
  trace_info: IDetailInfo;
  traceID?: string;
  duration?: string;
  time?: number;
  entryService?: string;
  entryEndpoint?: string;
  statusCode?: number;
  status?: string;
  type?: string;
  appName?: string;
}

export interface ITraceData extends ITraceListItem {
  [key: string]: any;
  original_data: any[];
  span_classify: ISpanClassifyItem[];
  topo_nodes: ITopoNode[];
  topo_relation: ITopoRelation[];
  trace_tree?: ITraceTree;
}

export interface OriginCrossAppSpanMap {
  [key: string]: Span[];
}

export type DirectionType = 'ltr' | 'rtl';

export interface ISpanListItem {
  [key: string]: any;
  span_name: string;
  parent_span_id: string;
  start_time: number | string;
  trace_id: string;
  trace_state: string;
  resource: {
    'telemetry.sdk.language': string;
    'service.name': string;
    'service.version': string;
    'bk.instance.id': string;
    bk_data_id: number;
    'telemetry.sdk.version': string;
    'telemetry.sdk.name': string;
  };
  span_id: string;
  kind: number;
  end_time: number | string;
  elapsed_time: number | string;
  time: string;
  status: {
    code: number;
    message: string;
  };
  status_code: {
    type: string;
    value: string;
  };
}

export enum EListItemType {
  tags = 'Tags',
  events = 'Events',
  stageTime = 'StageTime',
  process = 'Process'
}

export interface ITagContent {
  label: string;
  content?: string;
  type: string;
  isFormat?: boolean;
  query_key: string;
  query_value: any;
}

export interface ITagsItem {
  list: ITagContent[];
}

export interface IEventsItem {
  titleRight?: any;
  list: {
    isExpan: boolean;
    header: {
      date: string;
      name: string;
      duration: string;
    };
    content: ITagContent[];
  }[];
}

export interface IStageTimeItemContent {
  type: 'useTime' | 'gapTime';
  useTime?: {
    tags: string[];
    gap: { type: 'toRight' | 'toLeft'; value: string };
  };
  gapTime?: string;
}
export interface IStageTimeItem {
  // 阶段耗时
  active: string;
  list: {
    id: string;
    label: string;
    error: boolean;
    errorMsg: string;
  }[];
  content: {
    [propName: string]: IStageTimeItemContent[];
  };
}

export interface IProcessItem {
  title: string;
  list: {
    label: string;
    content?: string;
    query_key: string;
    query_value: any;
  }[];
}
export interface IListItem {
  type: EListItemType;
  isExpan: boolean;
  title?: string;
  [EListItemType.tags]?: ITagsItem;
  [EListItemType.events]?: IEventsItem;
  [EListItemType.stageTime]?: IStageTimeItem;
  [EListItemType.process]?: IProcessItem;
}
export interface IInfo {
  title: string;
  header: {
    // 头部
    title: string; // 标题
    timeTag: string; // 时间
    others: {
      label: string;
      content: any;
      title: string;
    }[];
  };
  list: IListItem[];
}

interface IOriginData {
  span_name: string;
  elapsed_time: number;
  links: any[];
  resource: {
    type: string;
    key: string;
    value: string;
    query_key: string;
    query_value: string;
  };
  attributes: {
    type: string;
    key: string;
    value: number;
    query_key: string;
    query_value: number;
  };
  status: {
    code: number;
    message: string;
  };
  kind: number;
  end_time: number;
  events: any[];
  time: string;
  start_time: number;
  trace_state: string;
  parent_span_id: string;
  span_id: string;
  trace_id: string;
}
export interface ISpanDetail {
  origin_data: IOriginData;
  trace_tree: {
    spans: {
      id: string;
      app_name: string;
      traceID: string;
      spanID: string;
      duration: number;
      references: {
        refType: string;
        spanID: string;
        traceID: string;
      }[];
      flags: number;
      color: string;
      logs: any[];
      operationName: string;
      service_name: string;
      startTime: number;
      kind: number;
      tags: {
        key: string;
        value: string;
        type: string;
        query_key: string;
        query_value: string;
      }[];
      error: boolean;
      message: string;
      attributes: any[];
      resource: any[];
      events: any[];
      icon: string;
      processID: string;
    }[];
    processes: {
      [key: string]: Object;
    };
  };
}

export interface IQueryParams {
  bk_biz_id?: number;
  app_name?: string;
  start?: number;
  end?: number;
  data_type?: string;
  profile_id?: string;
  diff_profile_id?: string;
  offset?: number;
  diagram_types?: string[];
  sort?: string;
  filter_labels?: Record<string, string>;
  diff_filter_labels?: any;
  is_compared?: boolean;
}
