/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
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

import type { TapdTypeEnum, TAPDWorkspaceBoundEnum } from '../../constant';
import type { GetEnumTypeTool } from 'monitor-pc/pages/query-template/typings/constants';

export * from './api';

export interface CreateTapdDefaultSetting {
  tapd_type?: '' | TapdType;
  workspace_id?: string;
}

/** Issue 活动日志项 */
export interface IssueActivityItem {
  activity_id: string;
  activity_type: string;
  bk_biz_id: number;
  content: null | string;
  from_value: null | string;
  operator: string;
  time: number;
  to_value: null | string;
}

export interface ITapdListItem {
  bk_biz_id: number;
  created: string;
  id: string;
  name: string;
  priority: string;
  status: TTapdStatus;
  tapd_type: string;
  workspace_id: number;
}

/** Tapd单据类型 */
export type TapdType = GetEnumTypeTool<typeof TapdTypeEnum>;

/** TAPD工作空间绑定类型 */
export type TAPDWorkspaceBoundType = GetEnumTypeTool<typeof TAPDWorkspaceBoundEnum>;

/** TAPD 项目信息 */
export interface TapdWorkspaceItem {
  is_bound: TAPDWorkspaceBoundType;
  workspace_id: string;
  workspace_name: string;
}

export const TapdStatus = {
  planning: 'planning',
  developing: 'developing',
  status_1: 'status_1',
  for_test: 'for_test',
  resolved: 'resolved',
  rejected: 'rejected',
  status_2: 'status_2',
  status_3: 'status_3',
  status_4: 'status_4',
  status_5: 'status_5',
  status_6: 'status_6',
  status_7: 'status_7',
  status_8: 'status_8',
  status_9: 'status_9',
  status_10: 'status_10',
  status_11: 'status_11',
  status_12: 'status_12',
  status_13: 'status_13',
  status_14: 'status_14',
} as const;

export type TTapdStatus = (typeof TapdStatus)[keyof typeof TapdStatus];

/** 开始态：新建 / 待处理 / 重新打开 */
const COLOR_START = '#28AB80';
/** 中间态：进行中 / 流转中 */
const COLOR_MIDDLE = '#0D68FF';
/** 结束态：终态（关闭/拒绝/验收通过） */
const COLOR_END = '#7C8597';

export const TapdStatusMap = {
  [TapdStatus.planning]: {
    text: 'backlog(新)',
    color: COLOR_START,
  },
  [TapdStatus.developing]: {
    text: 'todo(接受待排期)',
    color: COLOR_START,
  },
  [TapdStatus.status_1]: {
    text: '已实现',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.for_test]: {
    text: 'for test(转测试)',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.resolved]: {
    text: '已关闭',
    color: COLOR_END,
  },
  [TapdStatus.rejected]: {
    text: 'refuse(已拒绝)',
    color: COLOR_END,
  },
  [TapdStatus.status_2]: {
    text: 'for gray(发布运维环境)',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_3]: {
    text: 'done(发布上云环境)',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_4]: {
    text: '重新打开',
    color: COLOR_START,
  },
  [TapdStatus.status_5]: {
    text: 'for approve(echo 审批)',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_6]: {
    text: 'approved',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_7]: {
    text: 'doing',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_8]: {
    text: 'testing',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_9]: {
    text: 'tested',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_10]: {
    text: 'grayed(已在运维环境验收)',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_11]: {
    text: 'designing',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_12]: {
    text: 'design approved',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_13]: {
    text: 'for accept',
    color: COLOR_MIDDLE,
  },
  [TapdStatus.status_14]: {
    text: 'accepted',
    color: COLOR_END,
  },
};
