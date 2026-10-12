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
/** 输入 / 输出摘要单元格，两侧各自缩略，中间用箭头分隔 */
export interface IIoSummaryCell {
  input: string;
  output: string;
}

/** 列定义。只描述元数据，渲染逻辑由表格组件按 cellType 决定 */
export interface ILlmColumn {
  cellType: LlmCellType;
  /** 同时挂到表头 th 与单元格 td，用于列级样式 */
  className?: string;
  /** 列 id，同时是视图行上的取值字段 */
  id: string;
  label: string;
  minWidth?: number;
  /** 本地排序取值字段，指向视图行上的原始数值，供展开子表使用 */
  sortBy?: string;
  /** 远程排序字段；缺省表示接口暂未提供该列的排序键 */
  sortField?: string;
  width?: number;
}

/**
 * list_traces 返回的分组对象。
 * Trace 层与会话层结构一致，会话层额外返回 childs。
 */
export interface ILlmTraceItem {
  /** 分组内缓存读取 Token 总数 */
  cache_read_input_tokens: number;
  /** 分组内缓存写入 Token 总数 */
  cache_write_input_tokens: number;
  /** 会话包含的 Trace 列表，仅 group_field !== trace_id 时返回 */
  childs?: ILlmTraceItem[];
  /** Trace 所属会话，不能用 Trace 分组的 group_id 代替 */
  conversation_id?: string;
  /** Trace 或会话持续时间，单位微秒 */
  elapsed_time: number;
  /** 最近活动时间，单位微秒 */
  end_time: number;
  /** 当前分组字段 */
  group_field: string;
  /** 分组值：按 Trace 查询时等于 trace_id，按会话查询时为会话 ID */
  group_id: string;
  /** Trace 逻辑根 Span 的最后一条用户文本；会话取最早的非空输入 */
  input: string;
  input_tokens: number;
  /** Trace 逻辑根 Span 的最后一条助手文本；会话取最近的非空输出 */
  output: string;
  output_tokens: number;
  /** 根 Span 开始时间，单位微秒 */
  start_time: number;
  /** 会话或 Trace 状态 */
  status?: LlmStatus;
  /** 仅 Trace 层对象返回 */
  trace_id?: string;
  user_id: string;
}

/** 接口不返回 total，items 为空即表示没有下一页 */
export interface ILlmTraceListData {
  items: ILlmTraceItem[];
  limit: number;
  offset: number;
}

/** 会话行。children 直接来自接口的 childs，展开时无需二次请求 */
export interface ISessionRow {
  children: ITraceRow[];
  /** 完整耗时，供紧凑展示的悬停提示使用 */
  elapsedDetailText: string;
  elapsedText: string;
  ioSummary: IIoSummaryCell;
  key: string;
  lastActiveText: string;
  sessionId: string;
  /** 未返回或非法枚举时为空串，渲染期回退占位 */
  status: '' | LlmStatus;
  tokens: ITokensCell;
  traceCountText: string;
  userId: string;
}

/** Tokens 单元格，均为已格式化的展示文本 */
export interface ITokensCell {
  inputText: string;
  outputText: string;
  totalText: string;
}

/** Trace 行。展示字段在数据转换阶段一次性格式化完成，渲染期只做读取 */
export interface ITraceRow {
  /** 完整耗时，供紧凑展示的悬停提示使用 */
  elapsedDetailText: string;
  elapsedText: string;
  /** 耗时原始值（微秒），供展开子表本地排序 */
  elapsedValue: number;
  ioSummary: IIoSummaryCell;
  key: string;
  lastActiveText: string;
  /** 最近活动时间原始值（微秒），供展开子表本地排序 */
  lastActiveValue: number;
  sessionId: string;
  /** 未返回或非法枚举时为空串，渲染期回退占位 */
  status: '' | LlmStatus;
  tokens: ITokensCell;
  /** Tokens 总量原始值，供展开子表本地排序 */
  tokensTotalValue: number;
  traceId: string;
  userId: string;
}

/**
 * 单元格类型。表格按此分发到对应的单元格实现，两个视角共用同一批实现。
 * tokens 与 tokensBadge 均展示总量及输入 / 输出徽标。
 * ioSummary 为输入 / 输出两侧各自缩略，中间箭头分隔。
 */
export type LlmCellType =
  | 'countLink'
  | 'duration'
  | 'ioSummary'
  | 'link'
  | 'status'
  | 'text'
  | 'tokens'
  | 'tokensBadge';

export type LlmRow = ISessionRow | ITraceRow;

/** 会话或 Trace 状态，接口枚举 */
export type LlmStatus = 'error' | 'success';

/** 视角：会话视角按会话字段折叠，Trace 视角按 trace_id 平铺 */
export type LlmViewMode = 'session' | 'trace';
