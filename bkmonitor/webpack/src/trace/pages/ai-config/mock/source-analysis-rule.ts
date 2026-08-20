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

import type { CreateSourceAnalysisRuleParams, SourceAnalysisRuleDto } from '../typings';

/** 模拟网络延迟（ms） */
const MOCK_LATENCY = 300;

/** mock 当前用户（模拟服务端生成的审计字段） */
const MOCK_USER = 'admin';

/**
 * @description 内存规则存储（模拟服务端数据，增删改直接作用于该数组）
 * 资源 id 与 mock/ai-resources.ts 中的数据对应，便于联调资源详情查询
 */
const mockRuleList: SourceAnalysisRuleDto[] = [
  {
    agent_id: '1',
    bk_biz_id: 2,
    bkci_project_id: 'bkci-demo',
    conditions: [{ condition: 'and', field: 'alert_name', method: 'contains', value: ['OOM'] }],
    created_at: 1785542400,
    created_by: 'admin',
    id: 1,
    is_default: false,
    is_enabled: true,
    knowledge_base_ids: ['1'],
    priority: 1,
    repository_alias: 'demo-repo',
    skill_ids: ['1', '2'],
    updated_at: 1785542400,
    updated_by: 'admin',
  },
  {
    agent_id: '2',
    bk_biz_id: 2,
    bkci_project_id: 'bkci-demo',
    conditions: [{ condition: 'and', field: 'alert_name', method: 'contains', value: ['CPU'] }],
    created_at: 1785542400,
    created_by: 'admin',
    id: 2,
    is_default: false,
    is_enabled: false,
    knowledge_base_ids: ['2'],
    priority: 10,
    repository_alias: 'demo-repo',
    skill_ids: ['3'],
    updated_at: 1785542400,
    updated_by: 'admin',
  },
];

/** mock 成功响应：延迟后 resolve */
const mockResolve = <T>(data: T): Promise<T> =>
  new Promise(resolve => {
    setTimeout(() => resolve(data), MOCK_LATENCY);
  });

/** mock 失败响应：延迟后 reject（模拟 404 等异常场景） */
const mockReject = (message: string): Promise<never> =>
  new Promise((_, reject) => {
    setTimeout(() => reject(new Error(message)), MOCK_LATENCY);
  });

/** 按 id 查询规则：不存在时返回 null */
const findRule = (id: number): null | SourceAnalysisRuleDto => mockRuleList.find(item => item.id === id) ?? null;

/**
 * @description 查询源码分析规则列表（mock）
 * @description 真实接口：`GET fta/issue/source_analysis_rules/`
 * @param {Record<string, unknown>} [_params={}] - 查询参数
 * @returns {Promise<SourceAnalysisRuleDto[]>} 规则列表
 */
export const listSourceAnalysisRules = (_params: Record<string, unknown> = {}): Promise<SourceAnalysisRuleDto[]> =>
  mockResolve(mockRuleList.map(item => ({ ...item })));

/**
 * @description 新增源码分析规则（mock）：id 与审计字段由「服务端」生成
 * @description 真实接口：`POST fta/issue/source_analysis_rules/`
 * @param {CreateSourceAnalysisRuleParams} params - 新增参数
 * @returns {Promise<SourceAnalysisRuleDto>} 新增后的规则详情
 */
export const createSourceAnalysisRule = (params: CreateSourceAnalysisRuleParams): Promise<SourceAnalysisRuleDto> => {
  const now = Math.floor(Date.now() / 1000);
  const rule: SourceAnalysisRuleDto = {
    ...params,
    bk_biz_id: 2,
    bkci_project_id: '',
    created_at: now,
    created_by: MOCK_USER,
    id: Math.max(0, ...mockRuleList.map(item => item.id)) + 1,
    is_default: false,
    repository_alias: '',
    updated_at: now,
    updated_by: MOCK_USER,
  };
  mockRuleList.push(rule);
  return mockResolve({ ...rule });
};

/**
 * @description 获取源码分析规则详情（mock）：规则不存在时 reject
 * @description 真实接口：`GET fta/issue/source_analysis_rules/{pk}/`
 * @param {number} id - 规则 id
 * @returns {Promise<SourceAnalysisRuleDto>} 规则详情
 */
export const getSourceAnalysisRule = (id: number): Promise<SourceAnalysisRuleDto> => {
  const rule = findRule(id);
  return rule ? mockResolve({ ...rule }) : mockReject(`mock: 规则 ${id} 不存在`);
};

/**
 * @description 更新源码分析规则（mock）：局部合并变更字段
 * @description 真实接口：`PATCH fta/issue/source_analysis_rules/{pk}/`
 * @param {number} id - 规则 id
 * @param {Partial<CreateSourceAnalysisRuleParams>} params - 只传需要变更的字段
 * @returns {Promise<SourceAnalysisRuleDto>} 更新后的规则详情
 */
export const updateSourceAnalysisRule = (
  id: number,
  params: Partial<CreateSourceAnalysisRuleParams>
): Promise<SourceAnalysisRuleDto> => {
  const rule = findRule(id);
  if (!rule) return mockReject(`mock: 规则 ${id} 不存在`);
  const nextRule: SourceAnalysisRuleDto = {
    ...rule,
    ...params,
    updated_at: Math.floor(Date.now() / 1000),
    updated_by: MOCK_USER,
  };
  mockRuleList.splice(mockRuleList.indexOf(rule), 1, nextRule);
  return mockResolve({ ...nextRule });
};

/**
 * @description 删除源码分析规则（mock）：规则不存在时 reject
 * @description 真实接口：`DELETE fta/issue/source_analysis_rules/{pk}/`
 * @param {number} id - 规则 id
 * @returns {Promise<void>}
 */
export const deleteSourceAnalysisRule = (id: number): Promise<void> => {
  const rule = findRule(id);
  if (!rule) return mockReject(`mock: 规则 ${id} 不存在`);
  mockRuleList.splice(mockRuleList.indexOf(rule), 1);
  return mockResolve(undefined);
};
