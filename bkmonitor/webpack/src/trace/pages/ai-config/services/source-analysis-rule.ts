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
  listSourceAnalysisAgents,
  listSourceAnalysisKnowledgeBases,
  listSourceAnalysisSkills,
} from 'monitor-api/modules/issue';
import {
  createSourceAnalysisRule as createSourceAnalysisRuleApi,
  deleteSourceAnalysisRule as deleteSourceAnalysisRuleApi,
  getSourceAnalysisRule as getSourceAnalysisRuleApi,
  listSourceAnalysisRules as listSourceAnalysisRulesApi,
  updateSourceAnalysisRule as updateSourceAnalysisRuleApi,
} from 'monitor-api/modules/issue';

import { toConditions, toWhereItems } from '../utils/condition';

import type {
  AiResourceResult,
  CreateSourceAnalysisRuleParams,
  CreateSourceAnalysisRuleVo,
  SourceAnalysisRuleDto,
  SourceAnalysisRuleVo,
} from '../typings';

/**
 * @description 新增源码分析规则
 * @param {CreateSourceAnalysisRuleVo} params - 新增参数（conditions 为 UI 格式的 IWhereItem[]）
 * @returns {Promise<SourceAnalysisRuleDto>} 新增后的规则详情
 */
export const createSourceAnalysisRule = async (params: CreateSourceAnalysisRuleVo): Promise<SourceAnalysisRuleDto> =>
  createSourceAnalysisRuleApi({ ...params, conditions: toConditions(params.conditions) });

/**
 * @description 获取源码分析规则详情，conditions 已归一化为检索过滤器格式的 IWhereItem[]，失败返回 null
 * @param {number} id - 规则 id
 * @returns {Promise<SourceAnalysisRuleVo | null>} 归一化后的规则详情
 */
export const getSourceAnalysisRule = (id: number): Promise<null | SourceAnalysisRuleVo> =>
  getSourceAnalysisRuleApi(id)
    .then(data => ({ ...data, conditions: toWhereItems(data.conditions) }))
    .catch(() => null);

/**
 * @description 更新源码分析规则（局部修改、启停或调整优先级）
 * @param {number} id - 规则 id
 * @param {Partial<CreateSourceAnalysisRuleVo>} params - 只传需要变更的字段（conditions 为 UI 格式的 IWhereItem[]）
 * @returns {Promise<SourceAnalysisRuleDto>} 更新后的规则详情
 */
export const updateSourceAnalysisRule = (
  id: number,
  params: Partial<CreateSourceAnalysisRuleVo>
): Promise<SourceAnalysisRuleDto> => {
  const { conditions, ...rest } = params;
  const body: Partial<CreateSourceAnalysisRuleParams> = conditions
    ? { ...rest, conditions: toConditions(conditions) }
    : rest;
  return updateSourceAnalysisRuleApi(id, body);
};

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

/** 查询智能体列表（全量，无分页参数） */
export const getAgents = (): Promise<AiResourceResult> =>
  listSourceAnalysisAgents().catch(() => ({
    list: [],
    total: 0,
  }));

/** 查询 Skill 列表（全量，无分页参数） */
export const getSkills = (): Promise<AiResourceResult> =>
  listSourceAnalysisSkills().catch(() => ({
    list: [],
    total: 0,
  }));

/** 查询知识库列表（全量，无分页参数） */
export const getKnowledgeBases = (): Promise<AiResourceResult> =>
  listSourceAnalysisKnowledgeBases().catch(() => ({
    list: [],
    total: 0,
  }));
