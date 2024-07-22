/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { docCookies, LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';

/**
 * @description 在关注人里面但不在通知人则禁用操作
 * @param follower
 * @param assignee
 */
export function getOperatorDisabled(follower: string[], assignee: string[]) {
  const username = window.user_name || window.username;
  const hasFollower = (follower || []).some(u => u === username);
  const hasAssignee = (assignee || []).some(u => u === username);
  return hasAssignee ? false : hasFollower;
}

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';

// 告警事件告警状态筛选区域初始化数据
export const INIT_COMMON_FILTER_DATA = [
  {
    id: 'alert',
    name: isEn ? 'Alarm' : '告警',
    count: 0,
    children: [
      {
        id: 'MINE',
        name: isEn ? 'My Alarm' : '我的告警',
        count: 0,
      },
      {
        id: 'MY_APPOINTEE',
        name: isEn ? 'My Assigned' : '我负责的',
        count: 0,
      },
      {
        id: 'MY_FOLLOW',
        name: isEn ? 'My Followed' : '我关注的',
        count: 0,
      },
      {
        id: 'MY_ASSIGNEE',
        name: isEn ? 'My Received' : '我收到的',
        count: 0,
      },
      {
        id: 'NOT_SHIELDED_ABNORMAL',
        name: isEn ? 'Not Recovered' : '未恢复',
        count: 0,
      },
      {
        id: 'SHIELDED_ABNORMAL',
        name: isEn ? 'Active (muted)' : '未恢复(已屏蔽)',
        count: 0,
      },
      {
        id: 'RECOVERED',
        name: isEn ? 'Recovered' : '已恢复',
        count: 6186,
      },
    ],
  },
  {
    id: 'action',
    name: isEn ? 'Action' : '处理记录',
    count: 0,
    children: [
      {
        id: 'success',
        name: isEn ? 'Success' : '成功',
        count: 0,
      },
      {
        id: 'failure',
        name: isEn ? 'Failure' : '失败',
        count: 0,
      },
    ],
  },
];
