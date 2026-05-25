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
export interface ActiveMember {
  anomaly_message: string;
  member_issue_id: string;
  member_name: string;
  merge_operator: string;
  merge_reasons: string[];
  merge_time: number;
  status: 'active' | 'split';
}

export interface IssueMergeSource {
  active_members: ActiveMember[];
  main_issue_id: string;
  split_history: SplitHistory[];
}

export interface SplitHistory {
  /** 异常信息 */
  anomaly_message: string;
  /** 拆分成员 Issue ID */
  member_issue_id: string;
  /** 拆分成员 Issue 名称*/
  member_name: string;
  /** 合并操作人 */
  merge_operator: string;
  /** 合并原因 */
  merge_reasons: string[];
  /** 合并时间（Unix 秒级时间戳）*/
  merge_time: number;
  /** 拆分触发类型：`"manual"`（手动拆分）/ `"by_main_resolve"`（主 Issue 解决时级联拆分）/ `"by_main_archive"`（主 Issue 归档时级联拆分） */
  split_kind: 'by_main_archive' | 'by_main_resolve' | 'manual';
  /** 拆分操作人 */
  split_operator: string;
  /** 拆分原因 */
  split_reasons: string[];
  /** 拆分时间（Unix 秒级时间戳）*/
  split_time: number;
  /** 关系状态，已拆分固定为 `"split"` */
  status: 'split';
}
