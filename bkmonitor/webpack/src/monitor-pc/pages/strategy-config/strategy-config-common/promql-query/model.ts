export interface PromqlQuery {
  alias: string;
  promql: string;
  agg_interval?: number | string;
  data_source_label?: string;
  data_type_label?: string;
  expression_mode?: string;
  functions?: unknown[];
  [key: string]: unknown;
}

export interface PromqlSourceData {
  errorMsg?: string;
  legacyExpression?: string;
  legacyMultiQuery?: boolean;
  legacyOriginSql?: string;
  legacyQueryConfigs?: PromqlQuery[];
  promqlError?: boolean;
  queryConfigs?: PromqlQuery[];
  sourceCode: string;
  sourceCodeCache?: string;
  step: number | string;
}

export function getSourceQueries(source: PromqlSourceData): PromqlQuery[] {
  return source.queryConfigs?.length ? source.queryConfigs : [{ alias: 'a', promql: source.sourceCode || '' }];
}

export function createPromqlSourceData(
  queries: PromqlQuery[],
  expression = '',
  originSql = '',
  step: number | string = 60
): PromqlSourceData {
  const queryConfigs = queries.length
    ? queries.map((query, index) => ({
        ...query,
        alias: query.alias || String.fromCharCode(97 + index),
        promql: query.promql || (queries.length === 1 ? originSql : ''),
      }))
    : [{ alias: 'a', promql: originSql }];
  const legacyMultiQuery = queries.length > 1 && !queries.every(query => query.expression_mode === 'promql');
  const sourceCode = queryConfigs[0].promql;
  return {
    queryConfigs,
    sourceCode,
    sourceCodeCache: sourceCode,
    step: queries[0]?.agg_interval ?? step,
    legacyMultiQuery,
    legacyQueryConfigs: legacyMultiQuery ? queries.map(query => ({ ...query })) : undefined,
    legacyExpression: legacyMultiQuery ? expression : undefined,
    legacyOriginSql: legacyMultiQuery ? originSql : undefined,
    promqlError: false,
    errorMsg: '',
  };
}
