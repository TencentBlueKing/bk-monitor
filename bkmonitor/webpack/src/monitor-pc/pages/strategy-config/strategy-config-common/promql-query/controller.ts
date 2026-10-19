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
import { parser } from '@prometheus-io/lezer-promql';

import { type PromqlQuery, type PromqlSourceData, getSourceQueries, isExistingMultiPromql } from './model';

const EMPTY_QUERY_MESSAGE = '查询 {alias} 不能为空，请填写 PromQL 或删除该查询。';

export interface PromqlValidateOptions {
  /** 为 false 时只校验单条 PromQL 与 Step；已有多查询不拦截保存。 */
  allowMulti?: boolean;
}

export interface PromqlValidationError {
  aliases?: string[];
  /** 无需等待提交校验即可展示的提示，例如表达式引用了空的查询。 */
  immediate?: boolean;
  message: string;
  params?: Record<string, string>;
}

/** 每个编辑器/预览独立缓存，仅重新解析发生变化的查询和表达式。 */
export class PromqlQueryController {
  private expressionCache = { value: '', aliases: [] as string[], invalid: false, unsupported: false };
  private queryCache = new Map<string, { invalid: boolean; value: string }>();

  analyzeExpression(expression: string) {
    if (this.expressionCache.value === expression) return this.expressionCache;
    const aliases = new Set<string>();
    let invalid = false;
    let unsupported = false;
    parser.parse(expression).iterate({
      enter(node) {
        if (node.type.isError) invalid = true;
        if (
          ['MatrixSelector', 'SubqueryExpr', 'OffsetExpr', 'StepInvariantExpr', 'LabelMatchers'].includes(node.name)
        ) {
          unsupported = true;
        }
        if (node.name === 'VectorSelector') {
          const identifier = node.node.getChild('Identifier');
          if (identifier) aliases.add(expression.slice(identifier.from, identifier.to));
        }
      },
    });
    this.expressionCache = { value: expression, aliases: [...aliases], invalid, unsupported };
    return this.expressionCache;
  }

  /** 未填写表达式时单查询默认取该查询别名；兜底值不视为用户主动引用。 */
  effectiveExpression(source: PromqlSourceData, expression: string) {
    const queries = getSourceQueries(source);
    return expression.trim() || (queries.length === 1 ? queries[0].alias : '');
  }

  nextAlias(queries: PromqlQuery[]) {
    const aliases = new Set(queries.map(query => query.alias.toLowerCase()));
    return 'abcdefghijklmnopqrstuvwxyz'.split('').find(alias => !aliases.has(alias));
  }

  validate(
    source: PromqlSourceData,
    expression: string,
    options?: PromqlValidateOptions
  ): null | PromqlValidationError {
    if (source.legacyMultiQuery) return null;
    if (options?.allowMulti === false && isExistingMultiPromql(source, expression)) return null;
    const queries = getSourceQueries(source);
    const aliases = new Set(queries.map(query => query.alias));
    for (const alias of this.queryCache.keys()) {
      if (!aliases.has(alias)) this.queryCache.delete(alias);
    }
    // 任一查询为空即为错误，提示与红框覆盖全部空查询，与表达式是否引用它们无关。
    const empty = queries.filter(query => !query.promql.trim()).map(query => query.alias);
    if (empty.length) {
      const referenced =
        options?.allowMulti === false
          ? new Set<string>()
          : new Set(expression.trim() ? this.analyzeExpression(expression).aliases : []);
      return {
        aliases: empty,
        // 表达式引用了空查询时立即提示；仅新增、尚未被引用的空查询仍等失焦或提交后再校验。
        immediate: empty.some(alias => referenced.has(alias)),
        message: options?.allowMulti === false ? '查询 {alias} 不能为空，请填写 PromQL。' : EMPTY_QUERY_MESSAGE,
        params: { alias: empty.join('、') },
      };
    }
    for (const query of queries) {
      if (this.queryCache.get(query.alias)?.value !== query.promql) {
        let invalid = false;
        parser.parse(query.promql).iterate({
          enter: node => {
            if (node.type.isError) invalid = true;
          },
        });
        this.queryCache.set(query.alias, { value: query.promql, invalid });
      }
      if (this.queryCache.get(query.alias).invalid) {
        return {
          message: '查询 {alias} 的 PromQL 语法有误，请检查。',
          params: { alias: query.alias },
          aliases: [query.alias],
        };
      }
    }
    if (!Number.isInteger(Number(source.step)) || Number(source.step) <= 0) {
      return { message: 'Step需填写合法的整数值' };
    }
    if (options?.allowMulti === false) return null;
    const effective = this.effectiveExpression(source, expression);
    if (!effective.trim()) return { message: '请填写计算表达式' };
    const analysis = this.analyzeExpression(effective);
    if (analysis.invalid) return { message: '表达式语法有误，请检查。' };
    if (analysis.unsupported) return { message: '时间范围、offset 和标签过滤请填写在各条 PromQL 查询中。' };
    const unknown = analysis.aliases.filter(alias => !aliases.has(alias));
    if (unknown.length) {
      return {
        message: '表达式引用了不存在的查询 {alias}，请修改表达式或添加查询。',
        params: { alias: unknown.join('、') },
      };
    }
    if (queries.length === 1 && effective.trim() !== queries[0].alias) {
      return {
        message: '单查询表达式应为 {alias}；复杂计算请填写在 PromQL 查询中。',
        params: { alias: queries[0].alias },
      };
    }
    return null;
  }
}
