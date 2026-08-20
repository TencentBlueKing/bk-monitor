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
import { type ShallowRef, computed, onScopeDispose, shallowRef } from 'vue';

import { AiResourceEnum } from '../constants';
import { getAgentsByIds, getKnowledgebasesByIds, getSkillsByIds } from '../services/ai-resources';

import type { AiResourceType, SourceAnalysisRuleDto } from '../typings';
import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

/** 资源类型 → 资源详情项类型映射 */
interface AiResourceItemMap {
  [AiResourceEnum.AGENT]: IAgent;
  [AiResourceEnum.KNOWLEDGE_BASE]: IKnowledgebase;
  [AiResourceEnum.SKILL]: ISkill;
}

/** 资源类型 → 批量查询接口 */
const FETCHER_MAP: { [K in AiResourceType]: (ids?: number[]) => Promise<AiResourceItemMap[K][]> } = {
  [AiResourceEnum.AGENT]: getAgentsByIds,
  [AiResourceEnum.KNOWLEDGE_BASE]: getKnowledgebasesByIds,
  [AiResourceEnum.SKILL]: getSkillsByIds,
};

/**
 * @description 单类 AI 资源管理实例
 * 方法签名（而非函数属性）声明，保证跨类型动态分发时参数双变兼容：
 * Record<AiResourceType, IAiResources<AiResourceType>> 可直接接收各具体类型实例。
 */
interface IAiResources<T extends AiResourceType> {
  /** 加载中 */
  loading: ShallowRef<boolean>;
  /** 已选资源详情列表 */
  resources: ShallowRef<AiResourceItemMap[T][]>;
  /** 清空已选资源 */
  clearResources(): void;
  /** 根据资源 ID 批量查询资源详情 */
  fetchResources(ids: (number | string)[]): Promise<void>;
  /** 移除指定资源 */
  removeResource(resourceId: string): void;
  /** 写入已选资源详情 */
  setResources(items: AiResourceItemMap[T][]): void;
}

/**
 * @description 单类已选 AI 资源详情管理工厂（内部使用）
 * 每个实例持有独立的 resources / loading / AbortController，任一类资源单独请求时不影响其他资源。
 * @param {T} resourceType 资源类型
 */
const createAiResource = <T extends AiResourceType>(resourceType: T): IAiResources<T> => {
  /** 已选资源详情列表 */
  const resources = shallowRef<AiResourceItemMap[T][]>([]) as ShallowRef<AiResourceItemMap[T][]>;
  /** 加载中 */
  const loading = shallowRef(false);
  /** 当前请求的 AbortController，用于取消未完成的请求 */
  let abortController: AbortController | null = null;

  /**
   * @description 根据资源 ID 批量查询资源详情；空 ID 列表时直接清空，不触发 loading
   * @param {(number | string)[]} ids 资源 ID 列表
   */
  const fetchResources = async (ids: (number | string)[]) => {
    // 取消上一次未完成的请求，避免快速连续触发时竞态
    abortController?.abort();
    if (!ids.length) {
      resources.value = [];
      return;
    }

    const controller = new AbortController();
    abortController = controller;
    const { signal } = controller;

    loading.value = true;
    const data = await FETCHER_MAP[resourceType](ids.map(Number)).catch(() => []);
    // 请求被取消（新请求发起 / 组件卸载），丢弃本次结果；loading 交由最新请求收尾，避免闪烁
    if (signal.aborted) return;
    resources.value = data;
    loading.value = false;
  };

  /**
   * @description 写入已选资源详情（弹窗确认后调用，数据来自弹窗回传）
   * @param {AiResourceItemMap[T][]} items 资源详情列表
   */
  const setResources = (items: AiResourceItemMap[T][]) => {
    resources.value = items;
  };

  /**
   * @description 移除指定资源
   * @param {string} resourceId 资源 id
   */
  const removeResource = (resourceId: string) => {
    resources.value = resources.value.filter(item => String(item.id) !== resourceId);
  };

  /**
   * @description 清空已选资源
   */
  const clearResources = () => {
    resources.value = [];
  };

  // 组件卸载（effect scope 释放）时终止未完成的请求
  onScopeDispose(() => {
    abortController?.abort();
    abortController = null;
  });

  return {
    loading,
    resources,
    clearResources,
    fetchResources,
    removeResource,
    setResources,
  };
};

/**
 * @description 已选 AI 资源详情管理（智能体 / Skill / 知识库）
 * 内部按资源类型拆分为三个独立实例（resources / loading 互不干扰），对外聚合为单一门面：
 * - 打开侧弹窗时根据规则中的资源 ID 批量查询（fetchAllResources）；
 * - 按类型操作时通过 getResourceByType 取实例（弹窗确认写入 / 删除 / 清空 / 单类型独立刷新）；
 * - 关闭侧弹窗 / 新增态时重置全部（resetAllResources）。
 */
export const useAiResources = () => {
  const agentResources = createAiResource(AiResourceEnum.AGENT);
  const skillResources = createAiResource(AiResourceEnum.SKILL);
  const knowledgebaseResources = createAiResource(AiResourceEnum.KNOWLEDGE_BASE);

  /** 资源类型 → 资源操作实例（mapped type 保证按字面量 / 泛型索引时类型精确） */
  const resourceMap: { [K in AiResourceType]: IAiResources<K> } = {
    [AiResourceEnum.AGENT]: agentResources,
    [AiResourceEnum.SKILL]: skillResources,
    [AiResourceEnum.KNOWLEDGE_BASE]: knowledgebaseResources,
  };

  /** 聚合 loading：任一类资源加载中 */
  const loading = computed(
    () => agentResources.loading.value || skillResources.loading.value || knowledgebaseResources.loading.value
  );

  /**
   * @description 按资源类型取操作实例，弹窗确认 / 删除 / 清空 / 单类型独立刷新时按类型动态分发
   * @param {T} resourceType 资源类型
   * @returns {IAiResources<T>} 对应类型的资源操作实例
   */
  const getResourceByType = <T extends AiResourceType>(resourceType: T): IAiResources<T> => resourceMap[resourceType];

  /**
   * @description 根据规则中的资源 ID 批量拉取三类已选资源详情（编辑态打开时调用）
   * @param {Pick<SourceAnalysisRuleDto, 'agent_id' | 'knowledge_base_ids' | 'skill_ids'>} rule 规则中的资源 ID
   */
  const fetchAllResources = (rule: Pick<SourceAnalysisRuleDto, 'agent_id' | 'knowledge_base_ids' | 'skill_ids'>) => {
    agentResources.fetchResources(rule.agent_id ? [rule.agent_id] : []);
    skillResources.fetchResources(rule.skill_ids ?? []);
    knowledgebaseResources.fetchResources(rule.knowledge_base_ids ?? []);
  };

  /**
   * @description 重置全部资源列表（关闭侧弹窗 / 新增态时调用）
   */
  const resetAllResources = () => {
    agentResources.clearResources();
    skillResources.clearResources();
    knowledgebaseResources.clearResources();
  };

  return {
    /** 已选智能体列表（单选，0 或 1 项） */
    agents: agentResources.resources,
    /** 已选 Skill 列表 */
    skills: skillResources.resources,
    /** 已选知识库列表 */
    knowledgebases: knowledgebaseResources.resources,
    /** 聚合加载中（任一类资源加载中） */
    loading,
    /** 智能体加载中 */
    agentLoading: agentResources.loading,
    /** Skill 加载中 */
    skillLoading: skillResources.loading,
    /** 知识库加载中 */
    knowledgebaseLoading: knowledgebaseResources.loading,
    /** 按资源类型取操作实例 */
    getResourceByType,
    /** 根据规则中的资源 ID 批量查询三类资源详情 */
    fetchAllResources,
    /** 重置全部资源列表 */
    resetAllResources,
  };
};
