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
  aiAnalysisOverview,
  reanalyzeSourceAnalysis,
  retrySourceAnalysis,
  sourceAnalysis,
  startSourceAnalysis,
} from 'monitor-api/modules/issue';

import type { RequestOptions } from '../../services/base';
import type {
  AIAnalysisBaseParams,
  AIAnalysisOverview,
  SourceAnalysisRetryParams,
  SourceAnalysisView,
} from '../typing';

/**
 * @description 查询 AI 分析快览（聚合接口），汇总右侧常驻模块需要的全部 AI 能力摘要
 * @param {AIAnalysisBaseParams} params - 查询请求参数（bk_biz_id / issue_id）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<AIAnalysisOverview>} AI 分析快览聚合数据
 */
export const getIssueAiAnalysisOverview = (
  params: AIAnalysisBaseParams,
  options?: RequestOptions
): Promise<AIAnalysisOverview> => {
  return aiAnalysisOverview(params, options);
};

/**
 * @description 查询最新源码分析状态/结果，进入 AI 分析页签与完整结果轮询共用
 * @param {AIAnalysisBaseParams} params - 查询请求参数（bk_biz_id / issue_id）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<SourceAnalysisView>} 源码分析视图数据
 */
export const getIssueSourceAnalysis = (
  params: AIAnalysisBaseParams,
  options?: RequestOptions
): Promise<SourceAnalysisView> => {
  return sourceAnalysis(params, options);
};

/**
 * @description 首次源码分析，仅在已配置且从未执行时可用
 * @param {AIAnalysisBaseParams} params - 触发请求参数（bk_biz_id / issue_id）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<SourceAnalysisView>} 源码分析视图数据
 */
export const startIssueSourceAnalysis = (
  params: AIAnalysisBaseParams,
  options?: RequestOptions
): Promise<SourceAnalysisView> => {
  return startSourceAnalysis(params, options);
};

/**
 * @description 失败重试源码分析，复用目标失败记录的 alert_id
 * @param {SourceAnalysisRetryParams} params - 重试请求参数（bk_biz_id / issue_id / analysis_id）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<SourceAnalysisView>} 源码分析视图数据
 */
export const retryIssueSourceAnalysis = (
  params: SourceAnalysisRetryParams,
  options?: RequestOptions
): Promise<SourceAnalysisView> => {
  return retrySourceAnalysis(params, options);
};

/**
 * @description 重新分析源码分析，只允许从成功终态发起，重新选择当前最新告警
 * @param {AIAnalysisBaseParams} params - 重新分析请求参数（bk_biz_id / issue_id）
 * @param {RequestOptions} options - 请求配置选项
 * @returns {Promise<SourceAnalysisView>} 源码分析视图数据
 */
export const reanalyzeIssueSourceAnalysis = (
  params: AIAnalysisBaseParams,
  options?: RequestOptions
): Promise<SourceAnalysisView> => {
  return reanalyzeSourceAnalysis(params, options);
};
