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
export interface IUserGroup {
  id: string;
  name: string;
  hidden?: boolean;
  members: {
    id: string;
    name: string;
  }[];
}
/** 获取默认用户组同步用法 */
export const getDefaultUserGroupListSync = (groupList = []): IUserGroup[] => {
  const defaultUserGroupList = [
    {
      id: 'bk_biz_maintainer',
      display_name: '运维人员',
      logo: '',
      type: 'group',
    },
    {
      id: 'bk_biz_productor',
      display_name: '产品人员',
      logo: '',
      type: 'group',
    },
    {
      id: 'bk_biz_tester',
      display_name: '测试人员',
      logo: '',
      type: 'group',
    },
    {
      id: 'bk_biz_developer',
      display_name: '开发人员',
      logo: '',
      type: 'group',
    },
    {
      id: 'operator',
      display_name: '主负责人',
      logo: '',
      type: 'group',
    },
    {
      id: 'bk_bak_operator',
      display_name: '备份负责人',
      logo: '',
      type: 'group',
    },
  ];

  const userGroup = groupList?.length ? groupList : defaultUserGroupList;
  return userGroup.map(item => ({
    id: item.id,
    name: item.display_name,
    hidden: false,
    members:
      item?.members?.map?.(member => ({
        id: member.id,
        name: member.display_name,
      })) || [],
  }));
};

/** 获取默认用户组异步用法 */
export const getDefaultUserGroupList = async (groupList = []): Promise<IUserGroup[]> => {
  return getDefaultUserGroupListSync(groupList);
};
