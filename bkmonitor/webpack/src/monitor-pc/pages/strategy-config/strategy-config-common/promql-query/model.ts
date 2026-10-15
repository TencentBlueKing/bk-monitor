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
export interface PromqlQuery {
  [key: string]: unknown;
  agg_interval?: number | string;
  alias: string;
  data_source_label?: string;
  data_type_label?: string;
  expression_mode?: string;
  functions?: unknown[];
  promql: string;
}

export interface PromqlSourceData {
  errorMsg?: string;
  legacyExpression?: string;
  legacyMultiQuery?: boolean;
  legacyOriginSql?: string;
  legacyQueryConfigs?: PromqlQuery[];
  promqlError?: boolean;
  queryConfigs?: PromqlQuery[];
  /** 加载时的原始表达式，非多 PromQL 业务保存已有多查询时原样回写。 */
  rawExpression?: string;
  rawOriginSql?: string;
  rawQueryConfigs?: PromqlQuery[];
  sourceCode: string;
  sourceCodeCache?: string;
  step: number | string;
}

/** 仅该业务允许配置多 PromQL。 */
export const MULTI_PROMQL_BIZ_ID = 2;

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
    rawQueryConfigs: queries.map(query => ({ ...query })),
    rawExpression: expression,
    rawOriginSql: originSql,
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

export function getSourceQueries(source: PromqlSourceData): PromqlQuery[] {
  return source.queryConfigs?.length ? source.queryConfigs : [{ alias: 'a', promql: source.sourceCode || '' }];
}

/** 多条查询，或单条查询上填写了非别名表达式。 */
export function isExistingMultiPromql(source: PromqlSourceData, expression = '') {
  if (source.legacyMultiQuery) return true;
  const queries = getSourceQueries(source);
  if (queries.length > 1) return true;
  const value = expression.trim();
  return !!value && queries.length === 1 && value !== queries[0].alias;
}

export function isMultiPromqlBiz(bizId: null | number | string | undefined) {
  return Number(bizId) === MULTI_PROMQL_BIZ_ID;
}
