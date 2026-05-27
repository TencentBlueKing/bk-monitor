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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

// =====================================================================
// Issue 合并/拆分 功能 — 统一类型声明
// =====================================================================

/** 查询合并来源请求参数 */
export interface ListMergeSourcesParams {
  /** 业务 ID */
  bk_biz_id: number;
  /** 主 Issue ID */
  main_issue_id: string;
}

/** 查询合并来源响应 data */
export interface ListMergeSourcesResponse {
  /** 当前活跃的成员列表 */
  active_members: MergeSourceActiveMember[];
  /** 主 Issue ID */
  main_issue_id: string;
  /** 已拆分的历史记录列表 */
  split_history: MergeSourceSplitHistoryItem[];
}

/** 合并 Issue 请求参数 */
export interface MergeIssueParams {
  /** 业务 ID，所有 Issue 必须属于同一业务 */
  bk_biz_id: number;
  /** 主 Issue ID，合并后作为展示主体 */
  main_issue_id: string;
  /** 并入的 Issue ID 列表，1~100 条，自动去重保序 */
  members: string[];
  /** 合并依据列表，至少 1 条 */
  reasons: string[];
}

/** 合并 Issue 响应 data */
export interface MergeIssueResponseData {
  /** 主 Issue ID */
  main_issue_id: string;
  /** 实际并入的 Issue ID 列表（去重并剔除 main_issue_id 后） */
  members: string[];
  /** 操作结果，成功时固定为 'ok' */
  status: 'ok';
}

/** 合并关系中活跃成员摘要（Issue 列表 merge_status.active_members 中使用） */
export interface MergeMember {
  /** 成员 Issue ID */
  member_issue_id: string;
  /** 执行合并操作的用户 */
  merge_operator: string;
  /** 合并依据列表 */
  merge_reasons: string[];
  /** 合并时间（Unix 秒级时间戳） */
  merge_time: number;
}

/** 合并来源 - 活跃成员详情（merge_sources 响应中 active_members 条目） */
export interface MergeSourceActiveMember extends MergeSourceMemberBase {
  /** 关系状态，活跃成员固定为 'active' */
  status: 'active';
}

/** 合并来源中成员的公共基础字段（active_members 与 split_history 共用） */
export interface MergeSourceMemberBase {
  /** 异常信息 */
  anomaly_message: string;
  /** 成员 Issue ID */
  member_issue_id: string;
  /** 成员 Issue 名称，ES 中不存在时显示 '{issue_id} (已删除)' */
  member_name: string;
  /** 合并操作人 */
  merge_operator: string;
  /** 合并依据列表 */
  merge_reasons: string[];
  /** 合并时间（Unix 秒级时间戳） */
  merge_time: number;
}

/** 合并来源 - 拆分历史条目（merge_sources 响应中 split_history 条目） */
export interface MergeSourceSplitHistoryItem extends MergeSourceMemberBase {
  /** 拆分触发类型：manual=手动拆分 / by_main_resolve=主Issue解决时级联拆分 / by_main_archive=主Issue归档时级联拆分 */
  split_kind: null | SplitKind;
  /** 拆分操作人 */
  split_operator: null | string;
  /** 拆分依据列表 */
  split_reasons: null | string[];
  /** 拆分时间（Unix 秒级时间戳），无则 0 */
  split_time: number;
  /** 关系状态，已拆分固定为 'split' */
  status: 'split';
}

/**
 * Issue 合并状态（后端 hydrate_aggregations 注入）
 * - 普通 Issue（未参与合并）：merge_status 字段不存在
 * - 主 Issue：merge_status.role = 'main'，持有 active_members
 * - 成员 Issue：merge_status.role = 'member'，持有 main_issue_id
 */
export interface MergeStatus {
  /** 当前活跃的被合并成员列表（role=main 时有值，role=member 时为 null） */
  active_members: MergeMember[] | null;
  /** 所属主 Issue 的 ID（role=member 时有值，role=main 时为 null） */
  main_issue_id: null | string;
  /** 角色：main=主Issue / member=已被合并的成员Issue */
  role: 'main' | 'member';
}

/** 拆分 Issue 请求参数 */
export interface SplitIssueParams {
  /** 业务 ID */
  bk_biz_id: number;
  /** 待拆分的成员 Issue ID，必须处于活跃合并状态 */
  member_issue_id: string;
  /** 拆分依据列表，至少 1 条 */
  reasons: string[];
}

/** 拆分 Issue 响应 data */
export interface SplitIssueResponseData {
  /** 已拆分的成员 Issue ID */
  member_issue_id: string;
  /** 操作结果，固定为 'ok' */
  status: 'ok';
}

/** 拆分触发类型 */
export type SplitKind = 'by_main_archive' | 'by_main_resolve' | 'manual';
