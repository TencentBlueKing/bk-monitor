import { parser } from '@prometheus-io/lezer-promql';

import { getSourceQueries, type PromqlQuery, type PromqlSourceData } from './model';

export interface PromqlValidationError {
  message: string;
  params?: Record<string, string>;
  aliases?: string[];
}

/** 每个编辑器/预览独立缓存，仅重新解析发生变化的查询和表达式。 */
export class PromqlQueryController {
  private queryCache = new Map<string, { value: string; invalid: boolean }>();
  private expressionCache = { value: '', aliases: [] as string[], invalid: false, unsupported: false };

  analyzeExpression(expression: string) {
    if (this.expressionCache.value === expression) return this.expressionCache;
    const aliases = new Set<string>();
    let invalid = false;
    let unsupported = false;
    parser.parse(expression).iterate({
      enter(node) {
        if (node.type.isError) invalid = true;
        if (['MatrixSelector', 'SubqueryExpr', 'OffsetExpr', 'StepInvariantExpr', 'LabelMatchers'].includes(node.name)) {
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

  nextAlias(queries: PromqlQuery[]) {
    const aliases = new Set(queries.map(query => query.alias.toLowerCase()));
    return 'abcdefghijklmnopqrstuvwxyz'.split('').find(alias => !aliases.has(alias));
  }

  validate(source: PromqlSourceData, expression: string): PromqlValidationError | null {
    if (source.legacyMultiQuery) return null;
    const queries = getSourceQueries(source);
    const aliases = new Set(queries.map(query => query.alias));
    for (const alias of this.queryCache.keys()) {
      if (!aliases.has(alias)) this.queryCache.delete(alias);
    }
    const empty = queries.filter(query => !query.promql.trim()).map(query => query.alias);
    if (empty.length) {
      return {
        message: '查询 {alias} 不能为空，请填写 PromQL 或删除该查询。',
        params: { alias: empty.join('、') },
        aliases: empty,
      };
    }
    for (const query of queries) {
      if (this.queryCache.get(query.alias)?.value !== query.promql) {
        let invalid = false;
        parser.parse(query.promql).iterate({ enter: node => { if (node.type.isError) invalid = true; } });
        this.queryCache.set(query.alias, { value: query.promql, invalid });
      }
      if (this.queryCache.get(query.alias).invalid) {
        return { message: '查询 {alias} 的 PromQL 语法有误，请检查。', params: { alias: query.alias }, aliases: [query.alias] };
      }
    }
    if (!Number.isInteger(Number(source.step)) || Number(source.step) <= 0) {
      return { message: 'Step需填写合法的整数值' };
    }
    if (!expression.trim()) return { message: '请填写计算表达式' };
    const analysis = this.analyzeExpression(expression);
    if (analysis.invalid) return { message: '表达式语法有误，请检查。' };
    if (analysis.unsupported) return { message: '时间范围、offset 和标签过滤请填写在各条 PromQL 查询中。' };
    const unknown = analysis.aliases.filter(alias => !aliases.has(alias));
    if (unknown.length) {
      return {
        message: '表达式引用了不存在的查询 {alias}，请修改表达式或添加查询。',
        params: { alias: unknown.join('、') },
      };
    }
    if (queries.length === 1 && expression.trim() !== queries[0].alias) {
      return { message: '单查询表达式应为 {alias}；复杂计算请填写在 PromQL 查询中。', params: { alias: queries[0].alias } };
    }
    const referenced = new Set(analysis.aliases);
    const unused = queries.filter(query => !referenced.has(query.alias)).map(query => query.alias);
    if (unused.length) {
      return { message: '表达式需引用全部查询，尚未引用：{alias}。', params: { alias: unused.join('、') } };
    }
    return null;
  }
}
