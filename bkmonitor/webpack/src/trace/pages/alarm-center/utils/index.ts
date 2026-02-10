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

import dayjs from 'dayjs';
import { tryURLDecodeParse } from 'monitor-common/utils';
import { isZh } from 'monitor-pc/common/constant';

import { type AlarmUrlParams } from '../typings';

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

export const actionConfigGroupList = (actionConfigList): any[] => {
  const groupMap = {};
  const groupList = [];
  actionConfigList.forEach(item => {
    if (groupMap?.[item.plugin_type]?.list.length) {
      groupMap[item.plugin_type].list.push({ id: item.id, name: item.name });
    } else {
      groupMap[item.plugin_type] = { groupName: item.plugin_name, list: [{ id: item.id, name: item.name }] };
    }
  });
  Object.keys(groupMap).forEach(key => {
    const obj = groupMap[key];
    groupList.push({ id: key, name: obj.groupName, children: obj.list });
  });
  return groupList;
};

/* 处理记录执行状态 */

export const getStatusInfo = (status: string, failureType?: string) => {
  const statusMap = {
    success: window.i18n.t('成功'),
    failure: window.i18n.t('失败'),
    running: window.i18n.t('执行中'),
    shield: window.i18n.t('已屏蔽'),
    skipped: window.i18n.t('被收敛'),
    framework_code_failure: window.i18n.t('系统异常'),
    timeout: window.i18n.t('执行超时'),
    execute_failure: window.i18n.t('执行失败'),
    unknown: window.i18n.t('失败'),
  };
  let text = statusMap[status];
  if (status === 'failure') {
    text = statusMap[failureType] || window.i18n.t('失败');
  }
  return {
    status,
    text,
  };
};

export const queryString = (type: 'defense' | 'trigger', id) => {
  if (type === 'trigger') {
    return isZh() ? `处理记录ID: ${id}` : `action_id: ${id}`;
  }
  return isZh() ? `收敛记录ID: ${id}` : `converge_id: ${id}`;
};

export const handleToAlertList = (
  type: 'defense' | 'trigger',
  detailInfo: { converge_id?: number; create_time: number; end_time: number; id: string },
  bizId
) => {
  const curUnix = dayjs.tz().unix() * 1000;
  const oneDay = 60 * 24 * 60 * 1000;
  const startTime = dayjs.tz(detailInfo.create_time * 1000 - oneDay).format('YYYY-MM-DD HH:mm:ss');
  const endTime = detailInfo.end_time
    ? dayjs
      .tz(detailInfo.end_time * 1000 + oneDay > curUnix ? curUnix : detailInfo.end_time * 1000 + oneDay)
      .format('YYYY-MM-DD HH:mm:ss')
    : dayjs.tz().format('YYYY-MM-DD HH:mm:ss');
  window.open(
    `${location.origin}${location.pathname}?bizId=${bizId}/#/trace/alarm-center?queryString=${queryString(
      type,
      detailInfo.id
    )}&form=${startTime}&to=${endTime}&filterMode=queryString&alarmType=alert`
  );
};
