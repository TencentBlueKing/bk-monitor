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

import { AiResourceEnum, EDITABLE_KEYS } from '../constants';
import { getSourceAnalysisRule } from '../services/source-analysis-rule';

import type { AiResourceType, CreateSourceAnalysisRuleParams, SourceAnalysisRuleDto } from '../typings';

/**
 * @description 源码分析规则详情管理
 * @returns 规则详情状态与增删改查方法
 */
export const useSourceAnalysisRuleDetail = () => {
  /** 规则详情（编辑态，随用户操作变更） */
  const detail = shallowRef<null | SourceAnalysisRuleDto>(null);
  /** 接口返回的原始数据快照（非响应式，仅用于 diff 对比基准） */
  let rawData: null | SourceAnalysisRuleDto = null;
  /** 加载中 */
  const loading = shallowRef(false);
  /** 当前请求的 AbortController，用于取消未完成的请求 */
  let abortController: AbortController | null = null;

  /**
   * @description 创建新增态默认详情
   * 仅初始化可编辑字段为合理空值，id/审计字段由服务端生成。
   * @returns {SourceAnalysisRuleDto} 默认详情
   */
  const createDefaultDetail = (): SourceAnalysisRuleDto => ({
    agent_id: undefined,
    bk_biz_id: undefined,
    bkci_project_id: undefined,
    conditions: [],
    created_at: 0,
    created_by: '',
    id: 0,
    is_default: false,
    is_enabled: false,
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
  const initDetail = (callback: (detail: SourceAnalysisRuleDto) => void) => {
    detail.value = createDefaultDetail();
    callback({
      ...detail.value,
    });
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
  const fetchDetail = async (id: number, callback: (detail: SourceAnalysisRuleDto) => void) => {
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
    callback(data);
  };

  /**
   * @description 获取资源类型默认值
   * @param {T} resource_type - 资源类型
   * @returns {SourceAnalysisRuleDto[T]} 对应资源类型的默认值
   */
  const getResourceDefaultValue = <T extends AiResourceType>(resource_type: T): SourceAnalysisRuleDto[T] => {
    if (resource_type === AiResourceEnum.AGENT) return '' as SourceAnalysisRuleDto[T];
    return [] as SourceAnalysisRuleDto[T];
  };

  /**
   * @description 写入资源 ID（智能体为单个 id，Skill / 知识库为 id 数组，整体覆盖）
   * @param {AiResourceType} resource_type - 资源类型
   * @param {SourceAnalysisRuleDto[AiResourceType]} resource_ids - 资源 ID 值
   */
  const setResourceIds = (resource_type: AiResourceType, resource_ids: SourceAnalysisRuleDto[AiResourceType]) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, [resource_type]: resource_ids };
  };

  /**
   * @description 移除指定资源 ID
   * @param {AiResourceType} resource_type - 资源类型
   * @param {string} resource_id - 资源 id
   */
  const removeResourceId = (resource_type: AiResourceType, resource_id: string) => {
    if (!detail.value) return;
    const nextDetail = { ...detail.value };
    if (resource_type === AiResourceEnum.AGENT) {
      nextDetail[resource_type] = getResourceDefaultValue(resource_type);
    } else {
      nextDetail[resource_type] = detail.value[resource_type].filter(item => item !== resource_id);
    }
    detail.value = nextDetail;
  };

  /**
   * @description 清空指定类型的资源 ID
   * @param {AiResourceType} resource_type - 资源类型
   */
  const clearResourceIds = (resource_type: AiResourceType) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, [resource_type]: getResourceDefaultValue(resource_type) };
  };

  /**
   * @description 对比 detail 与 rawData，返回需要变更的字段
   * 仅比较 CreateSourceAnalysisRuleParams 范围内的可编辑字段，避免将 id/审计字段误传出。
   * 新增态（无 rawData）时，所有可编辑字段均视为变更，返回全量可编辑字段。
   * @returns {Partial<CreateSourceAnalysisRuleParams>} 仅包含发生变化的字段
   */
  const getChangedFields = (otherParams: Record<string, any>): Partial<CreateSourceAnalysisRuleParams> => {
    const current = detail.value;
    if (!current) return {};
    const currentValue = {
      ...current,
      ...otherParams,
    };
    const base = (rawData ?? {}) as Partial<SourceAnalysisRuleDto>;
    const result: Partial<CreateSourceAnalysisRuleParams> = {};
    for (const key of EDITABLE_KEYS) {
      const prev = base[key];
      const next = currentValue[key];
      // 数组/对象按内容比较，原始值等价于 === 比较
      if (JSON.stringify(prev) !== JSON.stringify(next)) {
        Object.assign(result, { [key]: next });
      }
    }
    return result;
  };

  /**
   * @description 从 detail 中提取新增态所需的全量参数
   * @returns {CreateSourceAnalysisRuleParams | null} 新增参数，detail 为空时返回 null
   */
  const getCreateParams = (otherParams: Record<string, any>): CreateSourceAnalysisRuleParams | null => {
    if (!detail.value) return null;
    const params = {};
    const detailValue = {
      ...detail.value,
      ...otherParams,
    };
    for (const key of EDITABLE_KEYS) {
      Object.assign(params, { [key]: detailValue[key] });
    }
    return params as CreateSourceAnalysisRuleParams;
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
    /** 清空指定类型的资源 ID */
    clearResourceIds,
    /** 写入资源 ID（整体覆盖） */
    setResourceIds,
    /** 移除指定资源 ID */
    removeResourceId,
  };
};
