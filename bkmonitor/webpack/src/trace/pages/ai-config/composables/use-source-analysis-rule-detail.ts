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
    priority: undefined,
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
   * @description 重置详情状态，关闭弹窗时调用以清理残留数据
   */
  const resetState = () => {
    detail.value = null;
    rawData = null;
  };

  /**
   * @description 查询规则详情
   * @param {number} id - 规则 id
   */
  const fetchDetail = async (id: number) => {
    loading.value = true;
    try {
      const data = await getSourceAnalysisRule(id);
      // detail 持深拷贝副本以便自由编辑，rawData 直接持有接口原始数据作为 diff 基准
      detail.value = JSON.parse(JSON.stringify(data));
      rawData = data;
    } finally {
      loading.value = false;
    }
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
   * @description 添加资源
   * @param {AiResourceType} resource_type - 资源类型
   * @param {SourceAnalysisRuleDto[AiResourceType]} resource - 资源数据
   */
  const handleAddResource = (resource_type: AiResourceType, resource: SourceAnalysisRuleDto[AiResourceType]) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, [resource_type]: resource };
  };

  /**
   * @description 删除资源
   * @param {AiResourceType} resource_type - 资源类型
   * @param {string} resource_id - 资源 id
   */
  const handleRemoveResource = (resource_type: AiResourceType, resource_id: string) => {
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
   * @description 清除资源
   * @param {AiResourceType} resource_type - 资源类型
   */
  const handleClearResources = (resource_type: AiResourceType) => {
    if (!detail.value) return;
    detail.value = { ...detail.value, [resource_type]: getResourceDefaultValue(resource_type) };
  };

  /**
   * @description 对比 detail 与 rawData，返回需要变更的字段
   * 仅比较 CreateSourceAnalysisRuleParams 范围内的可编辑字段，避免将 id/审计字段误传出。
   * 新增态（无 rawData）时，所有可编辑字段均视为变更，返回全量可编辑字段。
   * @returns {Partial<CreateSourceAnalysisRuleParams>} 仅包含发生变化的字段
   */
  const getChangedFields = (): Partial<CreateSourceAnalysisRuleParams> => {
    const current = detail.value;
    if (!current) return {};
    const base = (rawData ?? {}) as Partial<SourceAnalysisRuleDto>;
    const result: Partial<CreateSourceAnalysisRuleParams> = {};
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
   * @returns {CreateSourceAnalysisRuleParams | null} 新增参数，detail 为空时返回 null
   */
  const getCreateParams = (): CreateSourceAnalysisRuleParams | null => {
    if (!detail.value) return null;
    const params = {};
    for (const key of EDITABLE_KEYS) {
      Object.assign(params, { [key]: detail.value[key] });
    }
    return params as CreateSourceAnalysisRuleParams;
  };

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
    /** 清除资源 */
    handleClearResources,
    /** 添加资源 */
    handleAddResource,
    /** 删除资源 */
    handleRemoveResource,
  };
};
