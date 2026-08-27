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
import type { Ref } from 'vue';

import { useI18n } from 'vue-i18n';

import { ErrorKeyEnum } from '../constants';

import type { SourceAnalysisRuleVo } from '../typings';

/** 优先级允许的最大值 */
const PRIORITY_MAX = 10000;
/** 优先级允许的最小值 */
const PRIORITY_MIN = 1;

/**
 * @description 源码分析规则校验逻辑
 * 仅负责匹配规则必填、优先级必填且在允许区间的校验与错误信息维护；
 * 规则状态（conditions / priority / is_enabled）统一由 useSourceAnalysisRuleDetail.detail 持有。
 * @param {Ref<null | SourceAnalysisRuleVo>} detail - 规则详情响应式引用
 * @returns {{
 *   errors: ShallowRef<Record<string, string>>;
 *   clearError: (key: string) => void;
 *   validate: () => boolean;
 * }} 校验状态与方法集合
 */
export const useRuleVerification = (detail: Ref<null | SourceAnalysisRuleVo>) => {
  const { t } = useI18n();

  /** 校验错误信息 key-value 映射（key 对应 ErrorKeyEnum 字段） */
  const errors = shallowRef<Record<string, string>>({});

  /**
   * @description 清除指定字段的校验错误
   * @param {string} key - ErrorKeyEnum 对应的字段 key
   */
  const clearError = (key: string) => {
    if (!errors.value[key]) return;
    const nextErrors = { ...errors.value };
    delete nextErrors[key];
    errors.value = nextErrors;
  };

  /**
   * @description 校验规则基础信息
   * 必填项包括：告警策略匹配规则（conditions）、智能体（agent_id）、知识库（knowledge_base_ids）、Skill（skill_ids）；
   * 优先级（priority）必填且必须在 PRIORITY_MIN 与 PRIORITY_MAX 之间。
   * @returns {boolean} 全部校验通过返回 true，否则返回 false 并写入 errors
   */
  const validate = () => {
    const nextErrors: Record<string, string> = {};
    // 告警策略匹配规则：至少存在一条条件
    if (!detail.value?.conditions?.length) {
      nextErrors[ErrorKeyEnum.CONDITIONS] = t('请添加告警策略匹配规则');
    }
    // 智能体：必须选择
    if (!detail.value?.agent_id) {
      nextErrors[ErrorKeyEnum.AGENT] = t('请选择智能体');
    }
    // 知识库：至少选择一个
    if (!detail.value?.knowledge_base_ids?.length) {
      nextErrors[ErrorKeyEnum.KNOWLEDGE_BASE] = t('请选择知识库');
    }
    // Skill：至少选择一个
    if (!detail.value?.skill_ids?.length) {
      nextErrors[ErrorKeyEnum.SKILL] = t('请选择Skill');
    }
    // 优先级：必填，且必须在允许区间
    const priority = detail.value?.priority;
    if (!priority) {
      nextErrors[ErrorKeyEnum.PRIORITY] = t('请输入优先级');
    } else if (priority < PRIORITY_MIN || priority > PRIORITY_MAX) {
      nextErrors[ErrorKeyEnum.PRIORITY] = t('优先级需在1-10000之间');
    }
    errors.value = nextErrors;
    return !Object.keys(nextErrors).length;
  };

  return {
    errors,
    clearError,
    validate,
  };
};
