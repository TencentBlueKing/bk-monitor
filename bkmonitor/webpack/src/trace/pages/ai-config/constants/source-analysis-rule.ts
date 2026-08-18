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
import { Module } from '@blueking/ai-ui-sdk/enums';

import { AiResourceEnum } from './enum';

import type { CreateSourceAnalysisRuleParams, IModuleConfig } from '../typings';

/** 参与变更对比的可编辑字段 key 列表（与 CreateSourceAnalysisRuleParams 保持一致） */
export const EDITABLE_KEYS: (keyof CreateSourceAnalysisRuleParams)[] = [
  'agent_id',
  'conditions',
  'is_enabled',
  'knowledge_base_ids',
  'priority',
  'skill_ids',
];

/** 资源选择弹窗标题 i18n key 映射 */
export const RESOURCE_DIALOG_TITLE_MAP: Partial<Record<Module, string>> = {
  [Module.Agent]: window.i18n.t('关联智能体'),
  [Module.Skill]: window.i18n.t('关联 Skill'),
  [Module.Knowledgebase]: window.i18n.t('关联知识库'),
};

/**
 * @description 模块映射配置
 * 将资源模块（Module）与「对应 dialogConfirm 回调数据字段、规则资源类型、是否单值」统一收敛到一处，
 * 确认时 hook 内部据此完成 id 提取，宿主只需负责写回。
 */
export const MODULE_CONFIG: Partial<Record<Module, IModuleConfig>> = {
  [Module.Agent]: { field: 'agents', resource: AiResourceEnum.AGENT, single: true },
  [Module.Skill]: { field: 'skills', resource: AiResourceEnum.SKILL, single: false },
  [Module.Knowledgebase]: { field: 'knowledgebases', resource: AiResourceEnum.KNOWLEDGE_BASE, single: false },
};
