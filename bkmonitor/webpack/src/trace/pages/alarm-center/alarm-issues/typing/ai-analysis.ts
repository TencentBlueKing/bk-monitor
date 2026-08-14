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

/* ============== AI 分析 - 通用请求参数 ============== */
/** AI 分析通用请求参数（查询类接口） */
export interface AIAnalysisBaseParams {
  /** 业务 ID */
  bk_biz_id: number;
  /** Issue ID */
  issue_id: string;
}

/** AI 分析快览聚合返回 */
export interface AIAnalysisOverview {
  /** 故障总结模块（后续接入，当前不返回） */
  fault_summary?: unknown;
  /** 源码分析模块 */
  source_analysis: SourceAnalysisOverview;
}

/** 结果卡片（结构化结论卡片） */
export interface ResultCard {
  /** 结论描述 */
  description: string;
  /** 责任提交（INSUFFICIENT_EVIDENCE 时为 null） */
  responsibility: null | ResultResponsibility;
}

/** 结果卡片中的责任提交（精简版，不含 committed_at 和 reason） */
export interface ResultResponsibility {
  /** 提交者姓名 */
  author_name: string;
  /** 蓝鲸用户名 */
  bk_username: string;
  /** 提交 ID */
  commit_id: string;
  /** 提交信息 */
  commit_message: string;
}

/** 源码分析配置可用性 */
export interface SourceAnalysisConfig {
  /** 是否匹配到当前可用的源码分析规则 */
  is_configured: boolean;
  /** 是否已配置蓝盾项目和代码库 */
  is_repository_configured: boolean;
  /** 不可用原因代码 */
  unavailable_reason: null | SourceAnalysisUnavailableReason;
  /** 不可用原因中文名 */
  unavailable_reason_display: null | string;
}

/* ============== 枚举类型 ============== */
/** 源码分析状态冲突原因（统一错误外壳中 data.reason 的稳定值） */
export type SourceAnalysisConflictReason =
  | 'source_analysis_already_running'
  | 'source_analysis_not_configured'
  | 'source_analysis_not_retryable'
  | 'source_analysis_result_not_found'
  | 'source_analysis_result_not_ready'
  | 'source_analysis_target_not_failed'
  | 'source_analysis_target_not_success';

/** 源码分析失败信息 */
export interface SourceAnalysisFailure {
  /** 错误代码（用于排障与统计，前端不解析） */
  code: string;
  /** 用户可见错误说明 */
  message: string;
  /** 请求 ID */
  request_id: string;
  /** 是否可重试 */
  retryable: boolean;
}

/** 源码分析失败阶段 */
export type SourceAnalysisFailureStage =
  | 'ai_analysis'
  | 'result_archive'
  | 'result_fetch'
  | 'result_persist'
  | 'result_validate'
  | 'source_prepare'
  | 'task_create'
  | 'task_execute';

/** 源码分析最新执行记录（完整版） */
export interface SourceAnalysisLatest {
  /** 本次分析使用的告警 ID */
  alert_id: string;
  /** BKM 执行记录 ID，也是四方链路幂等主键 */
  analysis_id: string;
  /** 尝试次数（首次/重新分析为 1，失败重试递增） */
  attempt: number;
  /** 失败信息（仅 failed 非空） */
  failure: null | SourceAnalysisFailure;
  /** 失败阶段（仅 failed 非空） */
  failure_stage: null | SourceAnalysisFailureStage;
  /** 终态时间（秒级 Unix 时间戳） */
  finished_at: null | number;
  /** 分析结果（仅 success 非空） */
  result: null | SourceAnalysisResult;
  /** 重试来源分析 ID（仅失败重试有值） */
  retry_of_analysis_id: null | string;
  /** 当前阶段（终态为 null） */
  stage: null | SourceAnalysisStage;
  /** 当前阶段中文名 */
  stage_display: null | string;
  /** 真正开始执行时间（秒级 Unix 时间戳） */
  started_at: null | number;
  /** 状态 */
  status: SourceAnalysisStatus;
  /** 状态中文名 */
  status_display: string;
  /** 触发类型 */
  trigger_type: SourceAnalysisTriggerType;
  /** 发起时间（秒级 Unix 时间戳） */
  triggered_at: number;
  /** 手动发起人 */
  triggered_by: string;
  /** 状态最后更新时间（秒级 Unix 时间戳） */
  updated_at: number;
}

/** 快览中的源码分析模块 */
export interface SourceAnalysisOverview extends SourceAnalysisConfig {
  /** 最新执行记录（从未执行时为 null） */
  latest: null | SourceAnalysisOverviewLatest;
}

/** 快览中的源码分析最新执行记录（精简版） */
export interface SourceAnalysisOverviewLatest {
  /** BKM 执行记录 ID */
  analysis_id: string;
  /** 失败信息（仅 failed 非空） */
  failure: null | SourceAnalysisFailure;
  /** 分析结果（仅 success 非空，快览精简版） */
  result: null | SourceAnalysisOverviewResult;
  /** 当前阶段（终态为 null） */
  stage: null | SourceAnalysisStage;
  /** 当前阶段中文名 */
  stage_display: null | string;
  /** 状态 */
  status: SourceAnalysisStatus;
  /** 状态中文名 */
  status_display: string;
  /** 状态最后更新时间（秒级 Unix 时间戳） */
  updated_at: number;
}

/** 源码分析快览结果（精简展示用，不返回 Markdown 正文） */
export interface SourceAnalysisOverviewResult {
  /** 结果卡片（结构化结论卡片） */
  result_card: ResultCard;
  /** 结果类型 */
  result_type: SourceAnalysisResultType;
}

/** 源码分析结果（版本化 envelope，包含结构化卡片和 Markdown 正文） */
export interface SourceAnalysisResult {
  /** Markdown 正文（前端原样展示，不得解析推导业务结构） */
  content: string;
  /** 内容类型 */
  content_type: 'text/markdown';
  /** 结果卡片（结构化结论卡片） */
  result_card: ResultCard;
  /** 结果类型 */
  result_type: SourceAnalysisResultType;
  /** Schema 版本 */
  schema_version: string;
}

/** 源码分析结果类型 */
export type SourceAnalysisResultType = 'HIGH_CONFIDENCE' | 'INSUFFICIENT_EVIDENCE';

/** 失败重试请求参数 */
export interface SourceAnalysisRetryParams extends AIAnalysisBaseParams {
  /** 目标失败记录的分析 ID */
  analysis_id: string;
}

/** 源码分析阶段（终态为 null） */
export type SourceAnalysisStage = 'analyzing' | 'archiving' | 'source_preparing' | 'validating' | 'waiting';

/** 源码分析状态 */
export type SourceAnalysisStatus = 'failed' | 'pending' | 'running' | 'success';

/** 源码分析触发类型 */
export type SourceAnalysisTriggerType = 'initial' | 'reanalyze' | 'retry';

/** 源码分析不可用原因 */
export type SourceAnalysisUnavailableReason = 'no_matched_rule' | 'rule_disabled';

/** SourceAnalysisView（查询最新状态/结果、首次分析、失败重试、重新分析统一返回） */
export interface SourceAnalysisView extends SourceAnalysisConfig {
  /** 最新执行记录（从未执行时为 null） */
  latest: null | SourceAnalysisLatest;
}
