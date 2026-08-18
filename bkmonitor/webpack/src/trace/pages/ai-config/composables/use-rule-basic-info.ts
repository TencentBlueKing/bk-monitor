import { shallowRef } from 'vue';

import { useI18n } from 'vue-i18n';

import type { SourceAnalysisCondition, SourceAnalysisRule } from '../typings';
import type { IWhereItem } from 'trace/components/retrieval-filter/typing';

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

/** 优先级允许的最大值 */
const PRIORITY_MAX = 10000;
/** 优先级允许的最小值 */
const PRIORITY_MIN = 1;

/** 表单项错误信息 key */
const CONDITION_ERROR_KEY = 'conditions';
const PRIORITY_ERROR_KEY = 'priority';

/** 后端匹配条件转换为检索过滤器可识别的 where 结构 */
export const toWhereItems = (conditions: SourceAnalysisCondition[]): IWhereItem[] =>
  (conditions ?? []).map(item => ({
    condition: item.condition,
    key: item.field,
    method: item.method,
    value: item.value,
  }));

/** 检索过滤器的 where 结构转换为后端匹配条件 */
const toConditions = (where: IWhereItem[]): SourceAnalysisCondition[] =>
  (where ?? []).map(item => ({
    condition: item.condition,
    field: item.key,
    method: item.method,
    value: (item.value ?? []).map(String),
  }));

/**
 * @description 新增/编辑规则弹窗的基础信息表单逻辑
 * 负责告警策略匹配规则、优先级、状态三个字段的状态维护、回填与校验
 */
export const useRuleBasicInfo = () => {
  const { t } = useI18n();

  /** 告警策略匹配规则（检索过滤器格式） */
  const conditions = shallowRef<IWhereItem[]>([]);
  /** 优先级 */
  const priority = shallowRef<number>(10);
  /** 是否启用 */
  const isEnabled = shallowRef(true);
  /** 校验错误信息 */
  const errors = shallowRef<Record<string, string>>({});

  /** 用规则数据回填表单 */
  const setFormData = (rule: null | SourceAnalysisRule) => {
    conditions.value = toWhereItems(rule?.conditions ?? []);
    priority.value = rule?.priority ?? 10;
    isEnabled.value = rule?.is_enabled ?? true;
    errors.value = {};
  };

  /** 清空表单并恢复默认值 */
  const reset = () => {
    conditions.value = [];
    priority.value = 10;
    isEnabled.value = true;
    errors.value = {};
  };

  const clearError = (key: string) => {
    if (!errors.value[key]) return;
    const nextErrors = { ...errors.value };
    delete nextErrors[key];
    errors.value = nextErrors;
  };

  const handleConditionsChange = (where: IWhereItem[]) => {
    conditions.value = where;
    clearError(CONDITION_ERROR_KEY);
  };

  const handlePriorityChange = (val: number | string) => {
    priority.value = Number(val);
    clearError(PRIORITY_ERROR_KEY);
  };

  const handleEnabledChange = (val: boolean) => {
    isEnabled.value = val;
  };

  /** 校验基础信息：匹配规则必填、优先级必填且在允许区间内 */
  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!conditions.value.length) {
      nextErrors[CONDITION_ERROR_KEY] = t('请添加告警策略匹配规则');
    }
    if (!priority.value) {
      nextErrors[PRIORITY_ERROR_KEY] = t('请输入优先级');
    } else if (priority.value < PRIORITY_MIN || priority.value > PRIORITY_MAX) {
      nextErrors[PRIORITY_ERROR_KEY] = t('优先级需在1-10000之间');
    }
    errors.value = nextErrors;
    return !Object.keys(nextErrors).length;
  };

  /** 获取用于保存的基础信息字段 */
  const getFormData = () => ({
    conditions: toConditions(conditions.value),
    priority: priority.value,
    is_enabled: isEnabled.value,
  });

  return {
    conditions,
    priority,
    isEnabled,
    errors,
    setFormData,
    reset,
    handleConditionsChange,
    handlePriorityChange,
    handleEnabledChange,
    validate,
    getFormData,
  };
};
