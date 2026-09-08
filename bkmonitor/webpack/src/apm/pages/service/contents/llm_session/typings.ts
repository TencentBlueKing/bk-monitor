/** 视角：会话视角按会话字段折叠，Trace 视角按 trace_id 平铺 */
export type LlmViewMode = 'session' | 'trace';

/**
 * list_traces 返回的分组对象。
 * Trace 层与会话层结构一致，会话层额外返回 childs 且 input / output 为空串。
 */
export interface ILlmTraceItem {
  /** 分组内缓存写入 Token 总数 */
  cache_creation_input_tokens: number;
  /** 分组内缓存读取 Token 总数 */
  cache_read_input_tokens: number;
  /** 会话包含的 Trace 列表，仅 group_field !== trace_id 时返回 */
  childs?: ILlmTraceItem[];
  /** Trace 或会话持续时间，单位微秒 */
  elapsed_time: number;
  /** 当前分组字段 */
  group_field: string;
  /** 分组值：按 Trace 查询时等于 trace_id，按会话查询时为会话 ID */
  group_id: string;
  /** 逻辑根 Span 中最后一条用户文本，会话层为空串 */
  input: string;
  input_tokens: number;
  /** 逻辑根 Span 中最后一条助手文本，会话层为空串 */
  output: string;
  output_tokens: number;
  /** 根 Span 开始时间，单位微秒 */
  start_time: number;
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

/** Tokens 单元格，均为已格式化的展示文本 */
export interface ITokensCell {
  inputText: string;
  outputText: string;
  totalText: string;
}

/** Trace 行。展示字段在数据转换阶段一次性格式化完成，渲染期只做读取 */
export interface ITraceRow {
  /** 耗时原始值（微秒），供展开子表本地排序 */
  elapsedValue: number;
  elapsedText: string;
  ioSummary: string;
  key: string;
  /** 接口在 Trace 视角下不返回会话 ID，暂为空串 */
  sessionId: string;
  startTimeText: string;
  /** 开始时间原始值（微秒），供展开子表本地排序 */
  startTimeValue: number;
  /** 接口暂未返回状态字段，暂为空串 */
  status: string;
  tokens: ITokensCell;
  /** Tokens 总量原始值，供展开子表本地排序 */
  tokensTotalValue: number;
  traceId: string;
  userId: string;
}

/** 会话行。children 直接来自接口的 childs，展开时无需二次请求 */
export interface ISessionRow {
  children: ITraceRow[];
  firstActiveText: string;
  key: string;
  lastActiveText: string;
  sessionId: string;
  /** 接口暂未返回状态字段，暂为空串 */
  status: string;
  tokens: ITokensCell;
  traceCountText: string;
  userId: string;
}

export type LlmRow = ISessionRow | ITraceRow;

/**
 * 单元格类型。表格按此分发到对应的单元格实现，两个视角共用同一批实现。
 * tokens 为纯文本总量，tokensBadge 额外展示输入 / 输出徽标。
 */
export type LlmCellType = 'countLink' | 'link' | 'status' | 'text' | 'tokens' | 'tokensBadge';

/** 列定义。只描述元数据，渲染逻辑由表格组件按 cellType 决定 */
export interface ILlmColumn {
  cellType: LlmCellType;
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
