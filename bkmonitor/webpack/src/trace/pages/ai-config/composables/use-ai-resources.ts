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
import { shallowRef } from 'vue';

import { listAgents, listKnowledgebases, listSkills } from '../services/ai-resources';

import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

/**
 * @description AI 资源池管理（智能体 / Skill / 知识库）
 * 当前接入 ai-resources.ts 中的占位接口，后续替换为真实全量接口即可。
 */
export const useAiResources = () => {
  /** 智能体列表 */
  const agents = shallowRef<IAgent[]>([]);
  /** Skill 列表 */
  const skills = shallowRef<ISkill[]>([]);
  /** 知识库列表 */
  const knowledgebases = shallowRef<IKnowledgebase[]>([]);
  /** 加载中 */
  const loading = shallowRef(false);

  /**
   * @description 拉取全量资源池数据
   */
  const fetchResources = async () => {
    loading.value = true;
    try {
      const [agentList, skillList, knowledgebaseList] = await Promise.all([
        listAgents().catch(() => []),
        listSkills().catch(() => []),
        listKnowledgebases().catch(() => []),
      ]);
      agents.value = agentList;
      skills.value = skillList;
      knowledgebases.value = knowledgebaseList;
    } finally {
      loading.value = false;
    }
  };

  /**
   * @description 删除指定智能体
   */
  const removeAgent = (agent: IAgent) => {
    agents.value = agents.value.filter(item => item.id !== agent.id);
  };

  /**
   * @description 清空智能体列表
   */
  const clearAgents = () => {
    agents.value = [];
  };

  /**
   * @description 删除指定 Skill
   */
  const removeSkill = (skill: ISkill) => {
    skills.value = skills.value.filter(item => item.id !== skill.id);
  };

  /**
   * @description 清空 Skill 列表
   */
  const clearSkills = () => {
    skills.value = [];
  };

  /**
   * @description 删除指定知识库
   */
  const removeKnowledgebase = (knowledgebase: IKnowledgebase) => {
    knowledgebases.value = knowledgebases.value.filter(item => item.id !== knowledgebase.id);
  };

  /**
   * @description 清空知识库列表
   */
  const clearKnowledgebases = () => {
    knowledgebases.value = [];
  };

  return {
    /** 智能体列表 */
    agents,
    /** Skill 列表 */
    skills,
    /** 知识库列表 */
    knowledgebases,
    /** 加载中 */
    loading,
    /** 拉取全量资源池数据 */
    fetchResources,
    /** 删除指定智能体 */
    removeAgent,
    /** 清空智能体列表 */
    clearAgents,
    /** 删除指定 Skill */
    removeSkill,
    /** 清空 Skill 列表 */
    clearSkills,
    /** 删除指定知识库 */
    removeKnowledgebase,
    /** 清空知识库列表 */
    clearKnowledgebases,
  };
};
