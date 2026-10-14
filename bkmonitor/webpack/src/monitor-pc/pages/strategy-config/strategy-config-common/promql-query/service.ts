import { promqlToQueryConfig, queryConfigToPromql } from 'monitor-api/modules/strategies';

import { getSourceQueries, type PromqlSourceData } from './model';

export function buildPromqlItem(source: PromqlSourceData, expression: string) {
  if (source.legacyMultiQuery) {
    return {
      expression: source.legacyExpression,
      origin_sql: source.legacyOriginSql,
      query_configs: source.legacyQueryConfigs.map(query => ({ ...query })),
    };
  }
  const queries = getSourceQueries(source);
  return {
    expression: expression || queries[0].alias,
    // 与 master 已合并的保存参数一致：单条和多条都提交首条 PromQL，不把多查询 origin_sql 置空。
    origin_sql: source.sourceCode,
    query_configs: queries.map(query => ({
      data_source_label: 'prometheus',
      data_type_label: 'time_series',
      promql: query.promql,
      agg_interval: source.step,
      alias: query.alias,
      ...(queries.length > 1 ? { expression_mode: 'promql' } : {}),
    })),
  };
}

export function buildPromqlPreview(source: PromqlSourceData, expression: string) {
  const item = buildPromqlItem(source, expression);
  const queries = source.legacyMultiQuery ? [] : getSourceQueries(source);
  return {
    expression: item.expression,
    ...(!source.legacyMultiQuery && item.query_configs.length > 1 ? { promql_multi_expression: true } : {}),
    query_configs: item.query_configs.map((query, index) => {
      const { agg_interval, expression_mode, ...rest } = query;
      const functions = queries[index]?.functions;
      return {
        ...rest,
        interval: agg_interval,
        ...(Array.isArray(functions) ? { functions } : {}),
      };
    }),
  };
}

export function convertPromqlToForm(promql: string, step: number | string) {
  return promqlToQueryConfig('', { promql, step }, { needMessage: false });
}

export function convertFormToPromql(expression: string, queryConfigs: unknown[]) {
  return queryConfigToPromql(
    '',
    { query_config_format: 'strategy', expression, query_configs: queryConfigs },
    { needMessage: false }
  );
}
