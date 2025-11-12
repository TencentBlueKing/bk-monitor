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
