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
import {
  rumDownloadTopK,
  rumFieldsOptionValues,
  rumFieldStatisticsGraph,
  rumFieldStatisticsInfo,
  rumFieldsTopK,
  rumGenerateQueryString,
  rumRecords,
  rumViewConfig,
} from 'monitor-api/modules/rum_query';
import pinyin from 'tiny-pinyin';

import { SPAN_TYPE_FIELD } from '../constants';
import {
  mockDelay,
  mockFieldsOptionValues,
  mockFieldStatisticsGraph,
  mockFieldStatisticsInfo,
  mockFieldsTopK,
  mockRecordList,
  mockViewConfig,
} from './mocks';

import type {
  IRumCommonParams,
  IRumField,
  IRumQueryParams,
  IRumRawField,
  IRumRawViewConfig,
  IRumSpanRecord,
  IRumStatisticsGraphField,
  IRumViewConfig,
} from '../typings';
import type { AxiosRequestConfig } from 'axios';

/**
 * 后端接口尚未就绪，当前统一走本地 mock 数据。
 * 联调时把这里改成 false 即可切换到真实接口，无需改动上层 composable 与组件。
 */
const USE_MOCK = false;

/** 请求失败时不弹全局错误提示，由调用方决定降级展示 */
const SILENT: AxiosRequestConfig & { needMessage: boolean } = { needMessage: false };

/**
 * 把接口字段结构归一化成与 trace 检索一致的维度字段结构，
 * 这样 FieldTypeIcon、convertToTree、StatisticsList、ExploreFieldSetting 可以直接复用。
 */
function normalizeField(raw: IRumRawField): IRumField {
  const alias = raw.field_alias || raw.field_name;
  return {
    name: raw.field_name,
    alias,
    type: raw.field_type,
    field_unit: raw.field_unit || '',
    is_real: !!raw.is_real,
    is_searched: !!raw.is_searchable,
    is_dimensions: !!raw.is_agg,
    can_displayed: !!raw.is_list,
    option_values: raw.option_values || [],
    supported_operations: raw.supported_operations || [],
    pinyinStr: pinyin.convertToPinyin(`${alias}(${raw.field_name})`, '').toLocaleLowerCase(),
  };
}

function normalizeViewConfig(raw: IRumRawViewConfig): IRumViewConfig {
  const fields = (raw?.fields || []).map(normalizeField);
  const fieldMap = new Map(fields.map(field => [field.name, field]));
  return {
    fields,
    default_sort: raw?.default_sort || [],
    display_fields: raw?.display_fields || [],
    span_type_display_fields: raw?.span_type_display_fields || {},
    groups: (raw?.groups || []).map(group => ({
      name: group.name,
      alias: group.alias || group.name,
      supported_span_types: group.supported_span_types || [],
      fields: (group.field_names || []).map(name => fieldMap.get(name)).filter(Boolean),
    })),
  };
}

const EMPTY_VIEW_CONFIG: IRumViewConfig = {
  fields: [],
  groups: [],
  default_sort: [],
  display_fields: [],
  span_type_display_fields: {},
};

interface IFieldsOptionValuesParams extends IRumQueryParams {
  fields: string[];
  limit: number;
}

interface IRecordListParams extends IRumQueryParams {
  limit: number;
  offset: number;
  sort: string[];
}

/** 下载字段 Top-K 数据，返回 CSV 文本与文件名 */
export function downloadTopK(params: Record<string, unknown>) {
  if (USE_MOCK) {
    const [topK] = mockFieldsTopK(params.fields as string[], params.limit as number);
    const data = (topK?.list || []).map(item => `${item.value},${item.count},${item.proportions}%`).join('\n');
    return mockDelay({ data, filename: `topk_${params.app_name}_${topK?.field}.csv` }, 200);
  }
  return rumDownloadTopK(params, SILENT);
}

/** 把 UI 模式的过滤条件转换为等价的查询语句 */
export async function generateQueryString(params: Pick<IRumCommonParams, 'app_name' | 'filters' | 'mode'>) {
  if (USE_MOCK) {
    const queryString = params.filters
      .map(item => `${item.key}: (${item.value.map(value => `"${value}"`).join(' OR ')})`)
      .join(' AND ');
    return mockDelay(queryString, 120);
  }
  const res = await rumGenerateQueryString(params, SILENT).catch(() => '');
  return res || '';
}

/** 批量查询字段可选枚举值，返回以字段名为 key 的字典 */
export async function getFieldsOptionValues(
  params: IFieldsOptionValuesParams,
  requestConfig?: AxiosRequestConfig
): Promise<Record<string, string[]>> {
  if (USE_MOCK) {
    return mockDelay(mockFieldsOptionValues(params.fields, params.limit), 200);
  }
  const res = await rumFieldsOptionValues(params, { ...SILENT, ...requestConfig }).catch(() => null);
  return res || {};
}

/** 查询字段统计图表：字符类返回 Top5 时序，数值类返回分布直方图 */
export function getFieldStatisticsGraph(params: Record<string, unknown>, requestConfig?: AxiosRequestConfig) {
  if (USE_MOCK) {
    return mockDelay(mockFieldStatisticsGraph(params.field as IRumStatisticsGraphField));
  }
  return rumFieldStatisticsGraph(params, { ...SILENT, ...requestConfig });
}

/*
 * 以下四个统计分析接口直接注入给共享的 StatisticsList 组件，
 * 所以签名保持 (params, config) 且不在这里吞掉异常——组件内部已有取消与兜底逻辑。
 */

/** 查询字段覆盖率、去重数等统计信息，数值类字段额外返回极值分析 */
export function getFieldStatisticsInfo(params: Record<string, unknown>, requestConfig?: AxiosRequestConfig) {
  if (USE_MOCK) {
    return mockDelay(mockFieldStatisticsInfo(params.field as { field_name: string; field_type: string }));
  }
  return rumFieldStatisticsInfo(params, { ...SILENT, ...requestConfig });
}

/** 查询字段 Top-K 分布 */
export function getFieldsTopK(params: Record<string, unknown>, requestConfig?: AxiosRequestConfig) {
  if (USE_MOCK) {
    return mockDelay(mockFieldsTopK(params.fields as string[], params.limit as number));
  }
  return rumFieldsTopK(params, { ...SILENT, ...requestConfig });
}

/** 分页查询记录列表 */
export async function getRecordList(
  params: IRecordListParams,
  requestConfig?: AxiosRequestConfig
): Promise<IRumSpanRecord[]> {
  if (USE_MOCK) {
    const spanTypeFilter = params.filters?.find(item => item.key === SPAN_TYPE_FIELD);
    return mockDelay(
      mockRecordList({
        offset: params.offset,
        limit: params.limit,
        endTime: params.end_time,
        spanType: spanTypeFilter?.value?.[0] as string,
      })
    );
  }
  const res = await rumRecords(params, { ...SILENT, ...requestConfig }).catch(() => null);
  return res?.list || [];
}

/** 获取页面视图配置：字段全集、字段分组、默认列与默认排序 */
export async function getViewConfig(
  params: Omit<IRumQueryParams, 'filters' | 'query_string'>
): Promise<IRumViewConfig> {
  if (USE_MOCK) {
    return normalizeViewConfig(await mockDelay(mockViewConfig));
  }
  const raw = await rumViewConfig(params, SILENT).catch(() => null);
  return raw ? normalizeViewConfig(raw) : EMPTY_VIEW_CONFIG;
}

/** 供 StatisticsList 直接注入的接口集合 */
export const statisticsApi = {
  fieldsTopK: getFieldsTopK,
  fieldStatisticsInfo: getFieldStatisticsInfo,
  fieldStatisticsGraph: getFieldStatisticsGraph,
  downloadTopK,
};
