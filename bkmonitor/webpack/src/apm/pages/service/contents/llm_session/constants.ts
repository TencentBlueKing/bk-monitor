/** 后端视图配置中 LLM 会话面板的 type，CommonPage 依此把内容区交给本组件渲染 */
export const LLM_SESSION_PANEL_TYPE = 'llm_session';

/**
 * 会话视角的分组字段。
 * list_traces 的 group_field 查询 ES 原始 Span 字段，此处取 OTel GenAI 语义约定的会话 ID。
 * 若后续需要按数据源切换实际上报字段，只需替换此常量。
 */
export const SESSION_GROUP_FIELD = 'attributes.gen_ai.conversation.id';

/** Trace 视角的分组字段，与接口默认值一致 */
export const TRACE_GROUP_FIELD = 'trace_id';

/** 单次请求的分组数量，接口不返回 total，返回数不足一页即视为末页 */
export const PAGE_LIMIT = 20;

/** 接口未返回字段时的占位文案 */
export const EMPTY_TEXT = '--';

/** 输入 / 输出摘要的连接符 */
export const IO_SUMMARY_SEPARATOR = ' → ';
