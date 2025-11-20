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
 * 外部版授权相关接口
 */

// 获取运维人员列表呢
const getAuthorizerList = {
  url: '/external_permission/get_maintainer/',
  method: 'get',
};

// 修改授权人
const createOrUpdateAuthorizer = {
  url: '/external_permission/maintainer/',
  method: 'post',
};

// 获取授权人
const getAuthorizer = {
  url: '/external_permission/authorizer/',
  method: 'get',
};

// 获取审批记录
const getApplyRecordList = {
  url: '/external_permission/apply_record/',
  method: 'get',
};

// 获取授权列表
const getExternalPermissionList = {
  url: '/external_permission/',
  method: 'get',
};

// 删除外部权限
const deleteExternalPermission = {
  url: '/external_permission/drop/',
  method: 'post',
};

// 创建或更新外部权限
const createOrUpdateExternalPermission = {
  url: '/external_permission/create_or_update/',
  method: 'post',
};

// 获取操作类型对应的资源列表
const getByAction = {
  url: '/external_permission/resource_by_action/',
  method: 'get',
};

// 获取操作类型
const getActionList = {
  url: '/external_permission/action/',
  method: 'get',
};

export {
  getAuthorizerList,
  createOrUpdateAuthorizer,
  getAuthorizer,
  getApplyRecordList,
  getExternalPermissionList,
  deleteExternalPermission,
  createOrUpdateExternalPermission,
  getByAction,
  getActionList,
};
