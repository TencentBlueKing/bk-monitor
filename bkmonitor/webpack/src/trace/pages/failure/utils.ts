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
import { type ComputedRef, inject, provide } from 'vue';

import type { ITraceAnalysis } from './types';

export const INCIDENT_ID_KEY = 'INCIDENT_ID_KEY';
export const useIncidentProvider = (incidentId: ComputedRef<string>) => {
  provide(INCIDENT_ID_KEY, incidentId);
};
export const useIncidentInject = () => inject<ComputedRef<string>>(INCIDENT_ID_KEY);

export const replaceSpecialCondition = (qs: string) => {
  // 由于验证 queryString 不允许使用单引号，为提升体验，这里单双引号的空串都会进行替换。
  const regExp = new RegExp(`${window.i18n.t('通知人')}\\s*:\\s*(""|'')`, 'gi');
  return qs.replace(regExp, `NOT ${window.i18n.t('通知人')} : *`);
};

/**
 * @description 检查文本是否溢出（超过n行）
 * @param el 元素
 * @param n 行数，默认3行
 * @returns 是否溢出
 */
export const checkOverflow = (el: HTMLElement, n = 3) => {
  if (!el) return false;

  // 使用getComputedStyle获取精确样式
  const styles = getComputedStyle(el);
  const lineHeight = parseInt(styles.lineHeight) || 22; // 默认22px

  // 计算n行高度
  const maxHeight = lineHeight * n;

  return el.scrollHeight > maxHeight;
};

/**
 * trace分析表格字段配置
 * 定义每个追踪字段的显示标签、跳转链接和查询参数生成逻辑
 */
export const TRACE_FIELD_CONFIG = {
  // 跳转到trace检索-span详情页侧滑
  span_id: {
    url: '/trace/home',
    label: 'Span ID',
    query: data => getTraceQueryParams(data, 'spanDetail'),
  },
  // 跳转到trace检索-trace详情页侧滑
  trace_id: {
    url: '/trace/home',
    label: '所属 Trace',
    query: data => getTraceQueryParams(data, 'traceDetail'),
  },
  // 应用名称配置 - 跳转到APM应用详情页
  app_name: {
    url: '/apm/home',
    label: '所属应用',
    query: data => ({ app_name: data.app_name }),
  },
  // 服务名称配置 - 跳转到APM服务详情页
  service_name: {
    url: '/apm/service/',
    label: '所属服务',
    query: data => ({
      'filter-app_name': data.app_name,
      'filter-service_name': data.service_name,
    }),
  },
  // 调用类型配置 - 纯展示字段，无跳转链接
  kind: {
    url: '',
    label: '调用类型',
  },
  // 异常信息配置 - 纯展示字段，无跳转链接
  demo_log: {
    url: '',
    label: '异常信息',
  },
};

// 提取重复的查询参数生成逻辑
const getTraceQueryParams = (data: ITraceAnalysis, type: 'spanDetail' | 'traceDetail') => {
  const incidentQuery = {
    type,
    trace_id: data.trace_id,
    span_id: data.span_id,
  };

  return {
    app_name: data.app_name,
    refreshInterval: '-1',
    filterMode: 'queryString',
    sceneMode: 'trace',
    query: `trace_id: /(${data.trace_id})/`,
    incident_query: encodeURIComponent(JSON.stringify(incidentQuery)),
  };
};

// 检查是否展示根因节点
export const checkIsRoot = (entity: any) => {
  if (!entity?.component_type) return false;

  return entity.is_root && entity.component_type === 'primary';
};
