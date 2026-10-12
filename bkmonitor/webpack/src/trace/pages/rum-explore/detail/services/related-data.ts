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
import { rumRecords, rumStatistics } from 'monitor-api/modules/rum_query';

import type { IRumFilter, RumModeType } from '../../typings';
import type {
  IRumActionRelated,
  IRumDetailContext,
  IRumErrorRelated,
  IRumLongTaskRelated,
  IRumRecordDetail,
  IRumViewRelated,
} from '../typings';

const SILENT = { needMessage: false };

/** statistics 接口固定的基线时移标识，响应里同名字段即该时移下的统计值 */
const BASELINE = '0s';

interface IStatisticsParams {
  /** 统计方式：count 计数 / distinct 去重计数 */
  cal_type: 'count' | 'distinct';
  /** 统计字段 */
  field: string;
  filters: IRumFilter[];
  group_by: string[];
  /** 聚合粒度，仅按时间分桶时需要 */
  interval?: number;
  /** 对比时移，默认仅基线 */
  time_shifts?: string[];
}

interface IStatisticsRow {
  [shift: string]: unknown;
  dimensions: Record<string, number | string>;
  growth_rates?: Record<string, number>;
}

/** 按协议 3.x 拼装 statistics 请求并取回数据行 */
async function fetchStatistics(
  context: IRumDetailContext,
  mode: RumModeType,
  timeRange: { end_time: number; start_time: number },
  params: IStatisticsParams
): Promise<IStatisticsRow[]> {
  const res = await rumStatistics(
    {
      app_name: context.app_name,
      mode,
      group_name: 'origin',
      baseline: BASELINE,
      time_shifts: [BASELINE],
      ...timeRange,
      ...params,
    },
    SILENT
  ).catch(() => null);
  return res?.data || [];
}

/** 取数据行在基线时移下的统计值 */
const baselineValue = (row?: IStatisticsRow) => Number(row?.[BASELINE] ?? 0) || 0;

/**
 * @description Action 详情的关联数据：按 span_type 分组统计触发的请求数、错误数与 Long Task 数
 * 查询时间范围按协议取 [end_time - 1d, end_time + 1d]
 */
export async function getActionRelated(
  context: IRumDetailContext,
  mode: RumModeType,
  detail: IRumRecordDetail
): Promise<IRumActionRelated | null> {
  const actionId = String(detail.origin_data?.attributes?.['action.id'] || '');
  const rows = await fetchStatistics(
    context,
    mode,
    { start_time: context.end_time - 86400, end_time: context.end_time + 86400 },
    {
      cal_type: 'count',
      field: 'attributes.span_type',
      filters: [
        { key: 'attributes.action.id', operator: 'equal', value: [actionId] },
        { key: 'attributes.span_type', operator: 'equal', value: ['resource', 'error', 'long_task'] },
      ],
      group_by: ['attributes.span_type'],
    }
  );
  const pick = (spanType: string) =>
    baselineValue(rows.find(row => row.dimensions?.['attributes.span_type'] === spanType));
  return {
    resourceCount: pick('resource'),
    errorCount: pick('error'),
    longTaskCount: pick('long_task'),
  };
}

/**
 * @description Error 详情的关联数据：影响用户数（含环比）、发生次数、影响会话数与 24 小时趋势
 * @param errorFilters 定位同一个错误的过滤条件（文件、行列号、异常类型），由区块数据推导
 * @param timeRange 页面所选时间范围，影响面统计沿用该范围
 */
export async function getErrorRelated(
  context: IRumDetailContext,
  mode: RumModeType,
  errorFilters: IRumFilter[],
  timeRange: { end_time: number; start_time: number }
): Promise<IRumErrorRelated | null> {
  const filters: IRumFilter[] = [{ key: 'attributes.span_type', operator: 'equal', value: ['error'] }, ...errorFilters];
  /** 影响用户数额外带上「与查询区间等长」的时移，用于算环比 */
  const compareShift = `${Math.max(timeRange.end_time - timeRange.start_time, 1)}s`;
  const [userRows, countRows, sessionRows, trendRows] = await Promise.all([
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'distinct',
      field: 'attributes.user.id',
      filters,
      group_by: [],
      time_shifts: [BASELINE, compareShift],
    }),
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'count',
      field: 'attributes.span_type',
      filters,
      group_by: [],
    }),
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'distinct',
      field: 'attributes.session.id',
      filters,
      group_by: [],
    }),
    fetchStatistics(
      context,
      mode,
      { start_time: context.end_time - 86400, end_time: context.end_time },
      { cal_type: 'count', field: 'attributes.span_type', filters, group_by: ['time'], interval: 3600 }
    ),
  ]);
  return {
    userCount: baselineValue(userRows[0]),
    userGrowthRate: Number(userRows[0]?.growth_rates?.[compareShift] ?? 0) || 0,
    occurrenceCount: baselineValue(countRows[0]),
    sessionCount: baselineValue(sessionRows[0]),
    trend: trendRows.map(row => ({ time: Number(row.dimensions?.time ?? 0), value: baselineValue(row) })),
  };
}

/**
 * @description Long Task 详情的关联数据：回查触发它的 Action 记录
 * 查询时间范围按协议取 [end_time - 4h, end_time + 4h]，缺少 Action ID 时不请求
 */
export async function getLongTaskRelated(
  context: IRumDetailContext,
  mode: RumModeType,
  actionId: string
): Promise<IRumLongTaskRelated | null> {
  if (!actionId) return { actionName: '', actionType: '' };
  const res = await rumRecords(
    {
      app_name: context.app_name,
      mode,
      start_time: context.end_time - 4 * 3600,
      end_time: context.end_time + 4 * 3600,
      filters: [
        { key: 'attributes.span_type', operator: 'equal', value: ['action'] },
        { key: 'attributes.action.id', operator: 'equal', value: [actionId] },
      ],
      offset: 0,
      limit: 1,
      sort: ['-end_time'],
    },
    SILENT
  ).catch(() => null);
  const record = res?.list?.[0];
  return {
    actionName: String(record?.['attributes.action.target.name'] ?? ''),
    actionType: String(record?.['attributes.action.type'] ?? ''),
  };
}

/**
 * @description View 详情的关联数据：统计当前视图下触发的请求数（xhr / fetch）、错误数与 Span 总数
 * 按 view.id + session.id 定位，查询时间范围按协议取 [end_time - 1d, end_time + 1d]，
 * session_id 缺失时不请求，卡片侧展示占位值
 */
export async function getViewRelated(
  context: IRumDetailContext,
  mode: RumModeType,
  detail: IRumRecordDetail
): Promise<IRumViewRelated | null> {
  const viewId = String(detail.origin_data?.attributes?.['view.id'] || '');
  const sessionId = String(
    detail.overview?.items?.find(item => item.field_name === 'attributes.session.id')?.value ?? ''
  );
  if (!viewId || !sessionId) return null;
  const timeRange = { start_time: context.end_time - 86400, end_time: context.end_time + 86400 };
  const baseFilters: IRumFilter[] = [
    { key: 'attributes.view.id', operator: 'equal', value: [viewId] },
    { key: 'attributes.session.id', operator: 'equal', value: [sessionId] },
  ];
  const [resourceRows, errorRows, spanRows] = await Promise.all([
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'count',
      field: 'attributes.span_type',
      filters: [
        ...baseFilters,
        { key: 'attributes.span_type', operator: 'equal', value: ['resource'] },
        { key: 'attributes.resource.type', operator: 'equal', value: ['xhr', 'fetch'] },
      ],
      group_by: [],
    }),
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'count',
      field: 'attributes.span_type',
      filters: [...baseFilters, { key: 'attributes.span_type', operator: 'equal', value: ['error'] }],
      group_by: [],
    }),
    fetchStatistics(context, mode, timeRange, {
      cal_type: 'count',
      field: 'attributes.span_type',
      filters: [
        ...baseFilters,
        { key: 'attributes.span_type', operator: 'not_equal', value: ['view', 'vital', 'session'] },
      ],
      group_by: [],
    }),
  ]);
  return {
    resourceCount: baselineValue(resourceRows[0]),
    errorCount: baselineValue(errorRows[0]),
    spanCount: baselineValue(spanRows[0]),
  };
}
