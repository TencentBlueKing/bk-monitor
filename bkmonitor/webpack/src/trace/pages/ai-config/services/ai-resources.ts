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

import { mockAgentList, mockKnowledgebaseList, mockSkillList } from '../mock/ai-resources';

import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

/* ---------- 侧弹资源池占位接口（后续替换为真实接口） ---------- */

/**
 * @description 查询智能体列表（占位接口）
 * @returns {Promise<IAgent[]>} 智能体列表
 */
export const listAgents = async (): Promise<IAgent[]> => {
  return await Promise.resolve([...mockAgentList]);
};

/**
 * @description 查询 Skill 列表（占位接口）
 * @returns {Promise<ISkill[]>} Skill 列表
 */
export const listSkills = async (): Promise<ISkill[]> => {
  return await Promise.resolve([...mockSkillList]);
};

/**
 * @description 查询知识库列表（占位接口）
 * @returns {Promise<IKnowledgebase[]>} 知识库列表
 */
export const listKnowledgebases = async (): Promise<IKnowledgebase[]> => {
  return await Promise.resolve([...mockKnowledgebaseList]);
};
