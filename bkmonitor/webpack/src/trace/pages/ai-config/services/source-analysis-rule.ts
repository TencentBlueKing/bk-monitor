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

// TODO: 当前为 mock 实现，真实接口上线后将 import 来源替换为 'monitor-api/modules/issue' 即可
import {
  createSourceAnalysisRule as createSourceAnalysisRuleApi,
  deleteSourceAnalysisRule as deleteSourceAnalysisRuleApi,
  getSourceAnalysisRule as getSourceAnalysisRuleApi,
  listSourceAnalysisRules as listSourceAnalysisRulesApi,
  updateSourceAnalysisRule as updateSourceAnalysisRuleApi,
} from '../mock/source-analysis-rule';

// import {
//   createSourceAnalysisRule as createSourceAnalysisRuleApi,
//   deleteSourceAnalysisRule as deleteSourceAnalysisRuleApi,
//   getSourceAnalysisRule as getSourceAnalysisRuleApi,
//   listSourceAnalysisRules as listSourceAnalysisRulesApi,
//   updateSourceAnalysisRule as updateSourceAnalysisRuleApi,
// } from 'monitor-api/modules/issue';
import type { CreateSourceAnalysisRuleParams, SourceAnalysisRuleDto } from '../typings';

/**
 * @description 新增源码分析规则
 * @param {CreateSourceAnalysisRuleParams} params - 新增参数
 * @returns {Promise<SourceAnalysisRuleDto>} 新增后的规则详情
 */
export const createSourceAnalysisRule = async (
  params: CreateSourceAnalysisRuleParams
): Promise<SourceAnalysisRuleDto> => createSourceAnalysisRuleApi(params);

/**
 * @description 获取源码分析规则详情，失败返回 null
 * @param {number} id - 规则 id
 * @returns {Promise<SourceAnalysisRuleDto | null>} 规则详情
 */
export const getSourceAnalysisRule = (id: number): Promise<null | SourceAnalysisRuleDto> =>
  getSourceAnalysisRuleApi(id).catch(() => null);

/**
 * @description 更新源码分析规则（局部修改、启停或调整优先级）
 * @param {number} id - 规则 id
 * @param {Partial<CreateSourceAnalysisRuleParams>} params - 只传需要变更的字段
 * @returns {Promise<SourceAnalysisRuleDto>} 更新后的规则详情
 */
export const updateSourceAnalysisRule = (
  id: number,
  params: Partial<CreateSourceAnalysisRuleParams>
): Promise<SourceAnalysisRuleDto> => updateSourceAnalysisRuleApi(id, params);

/**
 * @description 删除源码分析规则
 * @param {number} id - 规则 id
 * @returns {Promise<void>}
 */
export const deleteSourceAnalysisRule = (id: number): Promise<void> => deleteSourceAnalysisRuleApi(id);

/**
 * @description 查询源码分析规则列表
 * @param {Record<string, unknown>} [params={}] - 查询参数
 * @returns {Promise<SourceAnalysisRuleDto[]>} 规则列表
 */
export const listSourceAnalysisRules = (params: Record<string, unknown> = {}): Promise<SourceAnalysisRuleDto[]> =>
  listSourceAnalysisRulesApi(params);
