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
import type { IRumDetailOverview, IRumDetailSection, IRumHoverInfo } from './detail';
import type { IRumWaterfallVM } from './view-model';

/** 被折叠的一段连续同级 Span */
export interface IRumTimelineFoldVM {
  count: number;
  /** 折叠段标识，展开时回传 */
  key: string;
  level: number;
}

/** 链路上下文列表项：Span 行与折叠行按展示顺序混排 */
export type IRumTimelineItemVM =
  | { data: IRumTimelineFoldVM; kind: 'fold' }
  | { data: IRumTimelineSpanVM; kind: 'span' };

/** timeline 接口的节点树，顶层为 View 节点，子节点按开始时间升序 */
export interface IRumTimelineNode {
  children?: IRumTimelineNode[];
  /** 对应 records[].span_id */
  span_id: string;
}

/** timeline 接口里的节点详情，结构与同一 span_id 的 record_detail 一致，Span 节点通常只带 origin_data */
export interface IRumTimelineRecord {
  origin_data: Record<string, any>;
  overview?: IRumDetailOverview;
  sections?: IRumDetailSection[];
  span_id: string;
}

/** timeline 接口返回结构 */
export interface IRumTimelineResponse {
  /** 结束时间（微秒），未结束时为 null */
  end_time: null | number;
  records: IRumTimelineRecord[];
  /** 开始时间（微秒），缺失时为 null */
  start_time: null | number;
  tree: IRumTimelineNode[];
}

/** 链路上下文里的一行 Span */
export interface IRumTimelineSpanVM {
  /** 耗时文本 */
  durationText: string;
  /** 有子节点，可展开 */
  expandable: boolean;
  /** 子节点已展开 */
  expanded: boolean;
  /** 当前详情的 Span */
  isCurrent: boolean;
  /** 嵌套层级，顶层为 0 */
  level: number;
  spanId: string;
  spanType: string;
  /** 行尾 HTTP 状态码标签，仅登记了 showStatusCode 的类型返回 */
  statusCode?: { bgColor: string; color: string; text: string };
  /** 类型标签 */
  tag: { bgColor: string; icon: string; label: string };
  /** 开始时间，HH:mm:ss */
  timeText: string;
  title: string;
  /** 关联 Trace ID，origin_data.links 里没有时为空串 */
  traceId: string;
}

/** 链路上下文顶部的 View 头部视图模型 */
export interface IRumTimelineViewVM {
  /** 子节点中的 Action 数 */
  actionCount: number;
  /** 停留时长，缺失时为空串 */
  durationText: string;
  /** 当前详情的 Span 就是这个 View */
  isCurrent: boolean;
  /** 路由类型（loading_type 的枚举别名） */
  loadingType: string;
  /** 子树中 xhr / fetch 请求数 */
  requestCount: number;
  spanId: string;
  title: string;
  /** Web Vitals 指标列表 */
  vitalMetrics: IRumTimelineVitalVM[];
  /** 页面加载时序瀑布图，View 区块缺 waterfall 数据时为空 */
  waterfall?: IRumWaterfallVM;
}

/** View 头部的一个 Web Vitals 指标 */
export interface IRumTimelineVitalVM {
  /** 按评级着色 */
  color: string;
  /** hover 展示的指标说明 */
  hover?: IRumHoverInfo;
  /** 指标标识，如 lcp / cls */
  key: string;
  text: string;
}

/** 链路上下文列表的快捷筛选类别，取值口径见 timeline 接口协议 2.12.3 */
export type RumTimelineFilterCategoryType = 'action' | 'all' | 'error' | 'request' | 'slow_node' | 'third_party';
