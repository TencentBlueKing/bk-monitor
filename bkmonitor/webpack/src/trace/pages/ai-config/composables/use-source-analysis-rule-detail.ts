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
import { onScopeDispose, shallowRef } from 'vue';

import { EDITABLE_KEYS } from '../constants';
import { getSourceAnalysisRule } from '../services/source-analysis-rule';

import type { AiResourceType, CreateSourceAnalysisRuleVo, SourceAnalysisRuleVo } from '../typings';
import type { IWhereItem } from 'trace/components/retrieval-filter/typing';

/**
 * @description 源码分析规则详情管理
 * @returns 规则详情状态与增删改查方法
 */
export const useSourceAnalysisRuleDetail = () => {
  /** 规则详情（编辑态，随用户操作变更；conditions 为 UI 格式 IWhereItem[]，由 service 层归一化返回） */
  const detail = shallowRef<null | SourceAnalysisRuleVo>(null);
  /** 接口返回的原始数据快照（非响应式，仅用于 diff 对比基准） */
  let rawData: null | SourceAnalysisRuleVo = null;
  /** 加载中 */
  const loading = shallowRef(false);
  /** 当前请求的 AbortController，用于取消未完成的请求 */
  let abortController: AbortController | null = null;

  /**
   * @description 创建新增态默认详情
   * 仅初始化可编辑字段为合理空值，id/审计字段由服务端生成。
   * @returns {SourceAnalysisRuleDto} 默认详情
   */
  const createDefaultDetail = (): SourceAnalysisRuleVo => ({
    agent_id: undefined,
    bk_biz_id: undefined,
    bkci_project_id: undefined,
    conditions: [],
    created_at: 0,
    created_by: '',
    id: 0,
    is_default: false,
    is_enabled: true,
    knowledge_base_ids: [],
    priority: 10,
    repository_alias: '',
    skill_ids: [],
    updated_at: 0,
    updated_by: '',
  });

  /**
   * @description 初始化新增态详情，供新增场景使用
   */
  const initDetail = () => {
    detail.value = createDefaultDetail();
    rawData = null;
  };

  /**
   * @description 重置详情状态，关闭弹窗时调用以清理残留数据；同时终止未完成的查询请求
   */
  const resetState = () => {
    // 取消未完成的查询，避免关闭弹窗后过期响应回写状态
    abortController?.abort();
    detail.value = null;
    rawData = null;
  };

  /**
   * @description 查询规则详情
   * @param {number} id - 规则 id
   */
  const fetchDetail = async (id: number) => {
    // 取消上一次未完成的请求，避免快速连续触发时竞态
    abortController?.abort();
    const controller = new AbortController();
    abortController = controller;
    const { signal } = controller;

    loading.value = true;
    const data = await getSourceAnalysisRule(id);
    // 请求被取消（新请求发起 / 弹窗关闭 / 组件卸载），丢弃本次结果；loading 交由最新请求收尾，避免闪烁
    if (signal.aborted) return;
    loading.value = false;
    if (!data) return;
    // detail 持深拷贝副本以便自由编辑，rawData 直接持有接口原始数据作为 diff 基准
    rawData = JSON.parse(JSON.stringify(data));
    detail.value = data;
  };

  /**
   * @description 写入资源 ID（智能体为单个 id，Skill / 知识库为 id 数组，整体覆盖）
   * @param {AiResourceType} resource_type - 资源类型
   * @param {SourceAnalysisRuleDto[AiResourceType]} resource_ids - 资源 ID 值
   */
  const setResourceIds = (resource_type: AiResourceType, resource_ids: SourceAnalysisRuleVo[AiResourceType]) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, [resource_type]: resource_ids };
  };

  /**
   * @description 写入匹配规则条件（UI 格式 IWhereItem[]，直接落库于 detail，提交时再转回后端格式）
   * @param {IWhereItem[]} where - 检索过滤器条件
   */
  const setConditions = (where: IWhereItem[]) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, conditions: where };
  };

  /**
   * @description 写入优先级
   * @param {number} val - 优先级
   */
  const setPriority = (val: number) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, priority: val };
  };

  /**
   * @description 写入启用状态
   * @param {boolean} val - 是否启用
   */
  const setEnabled = (val: boolean) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, is_enabled: val };
  };

  /**
   * @description 对比 detail 与 rawData，返回需要变更的字段
   * 仅比较 CreateSourceAnalysisRuleVo 范围内的可编辑字段，避免将 id/审计字段误传出。
   * 新增态（无 rawData）时，所有可编辑字段均视为变更，返回全量可编辑字段。
   * @returns {Partial<CreateSourceAnalysisRuleVo>} 仅包含发生变化的字段
   */
  const getChangedFields = (): Partial<CreateSourceAnalysisRuleVo> => {
    const current = detail.value;
    if (!current) return {};
    const base = (rawData ?? {}) as Partial<SourceAnalysisRuleVo>;
    const result: Partial<CreateSourceAnalysisRuleVo> = {};
    for (const key of EDITABLE_KEYS) {
      const prev = base[key];
      const next = current[key];
      // 数组/对象按内容比较，原始值等价于 === 比较
      if (JSON.stringify(prev) !== JSON.stringify(next)) {
        Object.assign(result, { [key]: next });
      }
    }
    return result;
  };

  /**
   * @description 从 detail 中提取新增态所需的全量参数
   * @returns {CreateSourceAnalysisRuleVo | null} 新增参数，detail 为空时返回 null
   */
  const getCreateParams = (): CreateSourceAnalysisRuleVo | null => {
    if (!detail.value) return null;
    const params: Partial<CreateSourceAnalysisRuleVo> = {};
    const detailValue = detail.value;
    for (const key of EDITABLE_KEYS) {
      Object.assign(params, { [key]: detailValue[key] });
    }
    return params as CreateSourceAnalysisRuleVo;
  };

  // 组件卸载（effect scope 释放）时终止未完成的请求
  onScopeDispose(() => {
    abortController?.abort();
    abortController = null;
  });

  return {
    /** 规则详情（编辑态） */
    detail,
    /** 加载中 */
    loading,
    /** 查询规则详情 */
    fetchDetail,
    /** 初始化新增态详情 */
    initDetail,
    /** 重置详情状态 */
    resetState,
    /** 获取新增态全量参数 */
    getCreateParams,
    /** 获取需要变更的字段（供更新/新增规则时使用） */
    getChangedFields,
    /** 写入资源 ID（整体覆盖） */
    setResourceIds,
    /** 写入匹配规则条件 */
    setConditions,
    /** 写入优先级 */
    setPriority,
    /** 写入启用状态 */
    setEnabled,
  };
};
