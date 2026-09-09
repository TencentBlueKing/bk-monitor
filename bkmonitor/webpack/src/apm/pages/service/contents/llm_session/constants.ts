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
/** 后端视图配置中 LLM 会话面板的 type，CommonPage 依此把内容区交给本组件渲染 */
export const LLM_SESSION_PANEL_TYPE = 'llm_session';

/**
 * 需要同步到路由的查询条件 key。
 * customRouteQuery 由 CommonPage 的所有 tab 共享，故统一加 llm 前缀，避免与日志 tab 的 keyword、
 * 告警模板 tab 的 sort 等同名参数互相覆盖。CommonPage 只回填登记在白名单里的 key，新增需同步登记。
 */
export const LLM_SESSION_QUERY_KEYS = ['llmViewMode', 'llmKeyword', 'llmSort'];

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
