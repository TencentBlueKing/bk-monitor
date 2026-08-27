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

import type { IWhereItem } from 'trace/components/retrieval-filter/typing';

/** 资源下拉选项（智能体 / Skill / 知识库通用） */
export type AiResourceOption = {
  id: string;
  name: string;
  /** 所属空间 id，接口新增字段 */
  space_id?: string;
  /** 所属空间名称，接口新增字段 */
  space_name?: string;
};

/** 资源下拉查询返回结果，接口不分页，一次返回当前用户全部可见资源 */
export type AiResourceResult = {
  list: AiResourceOption[];
  /** 总数，等于 list 长度 */
  total: number;
};

/** 侧弹窗 confirm 事件抛出数据 */
export type ConfirmPayload = {
  /** 提交参数：新增态为全量参数，编辑态为变更字段 */
  params: CreateSourceAnalysisRuleVo | Partial<CreateSourceAnalysisRuleVo>;
  /** 提交完成 Promise：resolve 表示成功（父组件关闭弹窗），reject 表示失败（保留弹窗） */
  promise: Promise<void>;
  /** 标记提交失败（供父组件调用） */
  reject: (err?: unknown) => void;
  /** 标记提交成功（供父组件调用） */
  resolve: () => void;
};

/** 新增源码分析规则的请求参数（id 与审计字段由服务端生成） */
export type CreateSourceAnalysisRuleParams = Pick<
  SourceAnalysisRuleDto,
  'agent_id' | 'conditions' | 'is_enabled' | 'knowledge_base_ids' | 'priority' | 'skill_ids'
>;

/** 新增/更新请求参数视图模型（Vo）：conditions 为 UI 格式的 IWhereItem[]，由 service 层转回后端格式 */
export type CreateSourceAnalysisRuleVo = Omit<CreateSourceAnalysisRuleParams, 'conditions'> & {
  conditions: SourceAnalysisRuleVo['conditions'];
};

/** 策略关联分析流程规则匹配条件 */
export type SourceAnalysisCondition = {
  /** 条件连接符，如 and / or */
  condition: string;
  /** 匹配字段 */
  field: string;
  /** 匹配方法，如 eq / contains */
  method: string;
  /** 匹配值列表 */
  value: string[];
};

/** 策略关联分析流程规则 */
export type SourceAnalysisRuleDto = {
  /** 智能体 id */
  agent_id: string;
  /** 业务 id */
  bk_biz_id: number;
  /** 蓝盾项目 id */
  bkci_project_id: string;
  /** 匹配条件列表 */
  conditions: SourceAnalysisCondition[];
  /** 创建时间戳 */
  created_at: number;
  /** 创建人 */
  created_by: string;
  /** 规则 id */
  id: number;
  /** 是否为默认规则 */
  is_default: boolean;
  /** 是否启用 */
  is_enabled: boolean;
  /** 关联知识库 id 列表 */
  knowledge_base_ids: string[];
  /** 优先级 */
  priority: number;
  /** 源码仓库别名 */
  repository_alias: string;
  /** 关联 skill id 列表 */
  skill_ids: string[];
  /** 更新时间戳 */
  updated_at: number;
  /** 更新人 */
  updated_by: string;
};

/** 详情视图模型（Vo）：conditions 已归一化为检索过滤器可识别的 IWhereItem[]，供侧弹窗直接渲染 */
export type SourceAnalysisRuleVo = Omit<SourceAnalysisRuleDto, 'conditions'> & {
  conditions: IWhereItem[];
};
