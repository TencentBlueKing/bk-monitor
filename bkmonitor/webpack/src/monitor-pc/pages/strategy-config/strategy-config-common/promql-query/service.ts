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
import { promqlToQueryConfig, queryConfigToPromql } from 'monitor-api/modules/strategies';

import { type PromqlSourceData, getSourceQueries } from './model';

export function buildPromqlItem(source: PromqlSourceData, expression: string, options?: { preserveMulti?: boolean }) {
  if (source.legacyMultiQuery) {
    return {
      expression: source.legacyExpression,
      origin_sql: source.legacyOriginSql,
      query_configs: source.legacyQueryConfigs.map(query => ({ ...query })),
    };
  }
  if (options?.preserveMulti && source.rawQueryConfigs?.length) {
    return {
      expression: source.rawExpression ?? expression,
      origin_sql: source.rawOriginSql ?? source.sourceCode,
      query_configs: source.rawQueryConfigs.map(query => ({ ...query })),
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

export function convertFormToPromql(expression: string, queryConfigs: unknown[]) {
  return queryConfigToPromql(
    '',
    { query_config_format: 'strategy', expression, query_configs: queryConfigs },
    { needMessage: false }
  );
}

export function convertPromqlToForm(promql: string, step: number | string) {
  return promqlToQueryConfig('', { promql, step }, { needMessage: false });
}
