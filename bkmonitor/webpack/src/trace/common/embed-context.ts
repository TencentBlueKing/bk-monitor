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

/**
 * 被宿主（APM 等）嵌入时的运行时上下文。
 *
 * 嵌入场景下宿主要求页面收敛到它自己的业务与过滤范围，且部分交互形态与主站不同；
 * 以前这些差异靠 `IS_APM_MONITOR` 条件编译产出两套代码，现在统一由 APM 适配层
 * （`*-apm.tsx`）在 setup 时写入、卸载时清理。未写入即代表主站直接访问。
 */
interface EmbedContext {
  /** 宿主的业务 ID，会覆盖业务侧传入的 bk_biz_ids */
  bizId: number;
  /** 宿主追加的过滤语句，与业务侧查询语句以 AND 合并；宿主未下发时为空串 */
  queryString?: string;
}

/**
 * 嵌入场景的 body 标记类。
 * 部分样式差异出现在 tippy 弹层上，而弹层被挂到 body 下、脱离了组件根节点，
 * 只能靠 body 上的标记类做作用域，因此在上下文写入/清理时同步维护。
 */
const EMBED_BODY_CLASS = 'is-monitor-embed';

let embedContext: EmbedContext | null = null;

export function clearEmbedContext(): void {
  embedContext = null;
  document.body.classList.remove(EMBED_BODY_CLASS);
}

export function getEmbedContext(): EmbedContext | null {
  return embedContext;
}

export function setEmbedContext(context: EmbedContext): void {
  embedContext = context;
  document.body.classList.add(EMBED_BODY_CLASS);
}

/**
 * 把宿主的业务 ID 与过滤语句合并进请求参数，非嵌入场景下原样返回。
 * 返回新对象，调用方需使用返回值而非依赖入参被改写。
 */
export function withEmbedQuery<T extends { bk_biz_ids?: unknown; query_string?: string }>(params: T): T {
  if (!embedContext) {
    return params;
  }
  const hostQueryString = embedContext.queryString || '';
  return {
    ...params,
    bk_biz_ids: [embedContext.bizId],
    // 语句模式下业务查询需整体加括号，避免与宿主语句 AND 拼接后运算符优先级出错
    query_string: params.query_string ? `(${params.query_string}) AND ${hostQueryString}` : hostQueryString,
  };
}
