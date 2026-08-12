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

/** 责任提交 */
export interface AnalysisResponsibility {
  /** 提交者姓名 */
  author_name: string;
  /** 蓝鲸用户名 */
  bk_username: string;
  /** 提交 ID */
  commit_id: string;
  /** 提交信息 */
  commit_message: string;
  /** 提交时间（ISO 8601） */
  committed_at: string;
  /** 定责原因 */
  reason: string;
}

/** 分析摘要 */
export interface AnalysisSummary {
  /** 结论 */
  conclusion: string;
  /** 影响范围 */
  impact_scope: null | string;
  /** 证据不足原因（仅 INSUFFICIENT_EVIDENCE 有值） */
  insufficient_evidence_reason: null | string;
  /** 根因 */
  root_cause: null | string;
}

/** 代码关联信息 */
export interface CodeAssociation {
  /** 关联查询状态 */
  association_query_status: string;
  /** 默认分支 */
  default_branch: string;
  /** 降级原因 */
  fallback_reason: null | string;
  /** 代码库别名 */
  repository_alias: string;
  /** 解析模式 */
  resolution_mode: string;
  /** 解析出的分支 */
  resolved_branch: null | string;
  /** 解析出的提交 ID */
  resolved_commit_id: null | string;
  /** SCM 类型 */
  scm_type: string;
}

/** 证据链项 */
export interface EvidenceChainItem {
  /** 证据 ID */
  evidence_id: string;
  /** 摘录 */
  excerpt: string;
  /** 来源信息 */
  source: EvidenceSource;
  /** 摘要 */
  summary: string;
  /** 标题 */
  title: string;
  /** 证据类型 */
  type: string;
}

/** 证据来源 */
export interface EvidenceSource {
  /** 构建 ID */
  build_id: null | string;
  /** 提交 ID */
  commit_id: null | string;
  /** 结束行号 */
  end_line: null | number;
  /** 文件路径 */
  file_path: null | string;
  /** 引用 ID */
  reference_id: string;
  /** 引用类型 */
  reference_type: string;
  /** 请求 ID */
  request_id: null | string;
  /** 起始行号 */
  start_line: null | number;
  /** 来源系统 */
  system: string;
  /** Trace ID */
  trace_id: null | string;
}

/** 下一步动作 */
export interface NextAction {
  /** 描述 */
  description: string;
  /** 标题 */
  title: string;
}

/** 修复变更项 */
export interface RepairChange {
  /** 变更说明 */
  changes: string;
  /** 当前代码 */
  current_code: string;
  /** diff 内容 */
  diff: string;
  /** 结束行号 */
  end_line: number;
  /** 说明 */
  explanation: string;
  /** 文件路径 */
  file_path: string;
  /** 起始行号 */
  start_line: number;
  /** 建议代码 */
  suggested_code: string;
  /** 符号名 */
  symbol: string;
}

/** 修复建议 */
export interface RepairSuggestion {
  /** 变更列表 */
  changes: RepairChange[];
  /** 修复策略 */
  fix_strategy: string;
  /** 问题描述 */
  problem_description: string;
  /** 验证建议 */
  validation_suggestions: string[];
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

/** 源码分析快览结果（精简展示用） */
export interface SourceAnalysisOverviewResult {
  /** 结果类型 */
  result_type: SourceAnalysisResultType;
  /** 分析摘要 */
  analysis_summary: {
    /** 结论 */
    conclusion: string;
    /** 证据不足原因（仅 INSUFFICIENT_EVIDENCE 有值） */
    insufficient_evidence_reason: null | string;
  };
  /** 证据链（快览只返回首条摘要） */
  evidence_chain: {
    /** 摘要 */
    summary: string;
    /** 标题 */
    title: string;
  }[];
  /** 下一步动作（INSUFFICIENT_EVIDENCE 时可能非空） */
  next_actions: {
    /** 描述 */
    description: string;
    /** 标题 */
    title: string;
  }[];
  /** 修复建议（INSUFFICIENT_EVIDENCE 时为 null） */
  repair_suggestion: {
    /** 修复策略 */
    fix_strategy: string;
  } | null;
  /** 责任提交（INSUFFICIENT_EVIDENCE 时为 null） */
  responsibility: {
    /** 提交者姓名 */
    author_name: string;
    /** 蓝鲸用户名 */
    bk_username: string;
    /** 提交 ID */
    commit_id: string;
    /** 提交信息 */
    commit_message: string;
  } | null;
}

/** 查看原始 JSON 请求参数 */
export interface SourceAnalysisRawParams extends AIAnalysisBaseParams {
  /** 目标成功记录的分析 ID */
  analysis_id: string;
}

/** 源码分析结果（页面展示 DTO，不含 execution_context 和 COS URL） */
export interface SourceAnalysisResult {
  /** 分析摘要 */
  analysis_summary: AnalysisSummary;
  /** 代码关联信息 */
  code_association: CodeAssociation;
  /** 证据链 */
  evidence_chain: EvidenceChainItem[];
  /** 下一步动作 */
  next_actions: NextAction[];
  /** 修复建议（INSUFFICIENT_EVIDENCE 时为 null） */
  repair_suggestion: null | RepairSuggestion;
  /** 责任提交（INSUFFICIENT_EVIDENCE 时为 null） */
  responsibility: AnalysisResponsibility | null;
  /** 结果类型 */
  result_type: SourceAnalysisResultType;
  /** Schema 版本 */
  schema_version: string;
  /** 来源构建信息 */
  source_build: SourceBuild;
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

/** 来源构建信息 */
export interface SourceBuild {
  /** 构建 ID */
  build_id: string;
  /** 构建编号 */
  build_number: number;
  /** 结束时间（ISO 8601） */
  finished_at: string;
  /** 流水线 ID */
  pipeline_id: string;
  /** 蓝盾构建项目 ID */
  project_id: string;
  /** 开始时间（ISO 8601） */
  started_at: string;
  /** 发起人 */
  started_by: string;
  /** 构建状态 */
  status: string;
}
