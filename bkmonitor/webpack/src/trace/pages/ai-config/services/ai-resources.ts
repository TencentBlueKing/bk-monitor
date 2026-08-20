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

// TODO: 当前为 mock 实现，真实接口上线后将 import 来源替换为真实 API 模块即可
import {
  getAgentsByIds as getAgentsByIdsApi,
  getKnowledgebasesByIds as getKnowledgebasesByIdsApi,
  getSkillsByIds as getSkillsByIdsApi,
} from '../mock/ai-resources';

import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

/* ---------- 侧栏资源选择弹窗：资源详情批量查询接口 ---------- */

/**
 * @description 批量查询智能体详情
 * @description 真实接口：`POST {apiPrefix}/agent/v1/agent/batch/`
 * @param {number[]} [agentIds] 智能体 ID 列表
 * @returns {Promise<IAgent[]>} 智能体详情列表
 */
export const getAgentsByIds = (agentIds?: number[]): Promise<IAgent[]> => getAgentsByIdsApi(agentIds);

/**
 * @description 批量查询 Skill 详情
 * @description 真实接口：`POST {apiPrefix}/skill/v1/skill/batch/`
 * @param {number[]} [skillIds] Skill ID 列表
 * @returns {Promise<ISkill[]>} Skill 详情列表
 */
export const getSkillsByIds = (skillIds?: number[]): Promise<ISkill[]> => getSkillsByIdsApi(skillIds);

/**
 * @description 批量查询知识库详情
 * @description 真实接口：`POST {apiPrefix}/knowledgebase/v1/knowledgebase/batch/`
 * @param {number[]} [knowledgebaseIds] 知识库 ID 列表
 * @returns {Promise<IKnowledgebase[]>} 知识库详情列表
 */
export const getKnowledgebasesByIds = (knowledgebaseIds?: number[]): Promise<IKnowledgebase[]> =>
  getKnowledgebasesByIdsApi(knowledgebaseIds);
