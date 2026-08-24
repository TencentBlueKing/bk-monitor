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
import type { IRumStatisticsGraph, IStatisticsInfo, ITopKField } from '../../typings';

/** 常见字段的候选值池，未命中的字段用合成值兜底 */
const FIELD_VALUE_POOL: Record<string, string[]> = {
  'attributes.span_type': ['view', 'resource', 'error', 'action', 'long_task', 'websocket', 'vital', 'custom'],
  'attributes.resource.type': ['xhr', 'fetch', 'script', 'css', 'image', 'font'],
  'attributes.http.request.method': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  'attributes.http.response.status_code': ['200', '204', '304', '400', '404', '500'],
  'attributes.user.id': ['harakoyang', 'carnielu', 'daisyhong', 'eilanzhang', 'miffyyang', 'kaichunwang'],
  'attributes.view.url_template': ['/order/submit', '/order/list', '/order/detail', '/user/profile'],
  'attributes.network.connection.type': ['wifi', '4g', '3g', 'ethernet'],
  'resource.user_agent.name': ['Chrome', 'Safari', 'Firefox', 'Edge', 'Brave'],
  'resource.user_agent.os.name': ['Windows', 'macOS', 'iOS', 'Android', 'Linux'],
  'resource.device.type': ['desktop', 'mobile', 'tablet'],
  'status.code': ['0', '1', '2'],
  kind: ['1', '2', '3', '4', '5'],
};

const IP_POOL = ['11.154.121.234', '9.434.23.101', '234.345.44.3', '99.234.23.234', '9.23.45.143'];

export function mockFieldsOptionValues(fields: string[], limit: number): Record<string, string[]> {
  return fields.reduce<Record<string, string[]>>((result, field) => {
    result[field] = getValuePool(field).slice(0, limit);
    return result;
  }, {});
}

export function mockFieldStatisticsGraph(field: {
  field_name: string;
  field_type: string;
  values?: Array<number | string>;
}): IRumStatisticsGraph {
  const now = Date.now();
  const pointCount = 12;
  const isNumeric = field.field_type !== 'keyword';
  const dimensionValues = isNumeric
    ? ['200', '300', '400', '500', '600', '700', '800', '900']
    : (field.values as string[])?.length
      ? (field.values as string[])
      : getValuePool(field.field_name).slice(0, 5);

  return {
    series: dimensionValues.map((value, seriesIndex) => ({
      dimensions: { [field.field_name]: value },
      target: `count(${field.field_name}){${field.field_name}=${value}}`,
      metric_field: '_result_',
      alias: '_result_',
      stat: {},
      type: isNumeric ? 'bar' : 'line',
      dimensions_translation: {},
      unit: '',
      datapoints: Array.from({ length: isNumeric ? 1 : pointCount }, (_, pointIndex) => {
        const value = 18 - seriesIndex * 2 - (pointIndex % 4);
        return [Math.max(value, 1), now - (pointCount - pointIndex) * 60 * 1000] as [number, number];
      }),
    })),
  };
}

export function mockFieldStatisticsInfo(field: { field_name: string; field_type: string }): IStatisticsInfo {
  const isNumeric = ['double', 'integer', 'long'].includes(field.field_type);
  const totalCount = 4647434;
  const base: IStatisticsInfo = {
    field: field.field_name,
    total_count: totalCount,
    field_count: Math.round(totalCount * 0.92),
    distinct_count: getValuePool(field.field_name).length + 3,
    field_percent: 92,
  };
  if (!isNumeric) return base;
  return {
    ...base,
    value_analysis: {
      min: 200,
      max: 900,
      avg: 700,
      median: 700,
    },
  };
}

export function mockFieldsTopK(fields: string[], limit: number): ITopKField[] {
  return fields.map(field => {
    const pool = getValuePool(field);
    const size = Math.min(limit, pool.length);
    const proportions = buildProportions(size);
    return {
      field,
      distinct_count: pool.length + 3,
      list: pool.slice(0, size).map((value, index) => ({
        value,
        count: Math.round(proportions[index] * 470),
        proportions: proportions[index],
      })),
    };
  });
}

/** 生成递减且总和接近 100% 的占比分布 */
function buildProportions(size: number) {
  const weights = Array.from({ length: size }, (_, index) => size - index);
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  return weights.map(weight => Number(((weight / total) * 100).toFixed(3)));
}

function getValuePool(field: string) {
  return FIELD_VALUE_POOL[field] || IP_POOL;
}
