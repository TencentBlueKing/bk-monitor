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
  method: 'get',
  url: '/external_permission/get_maintainer/',
};

// 修改授权人
const createOrUpdateAuthorizer = {
  method: 'post',
  url: '/external_permission/maintainer/',
};

// 获取授权人
const getAuthorizer = {
  method: 'get',
  url: '/external_permission/authorizer/',
};

// 获取审批记录
const getApplyRecordList = {
  method: 'get',
  url: '/external_permission/apply_record/',
};

// 获取授权列表
const getExternalPermissionList = {
  method: 'get',
  url: '/external_permission/',
};

// 删除外部权限
const deleteExternalPermission = {
  method: 'post',
  url: '/external_permission/drop/',
};

// 创建或更新外部权限
const createOrUpdateExternalPermission = {
  method: 'post',
  url: '/external_permission/create_or_update/',
};

// 获取操作类型对应的资源列表
const getByAction = {
  method: 'get',
  url: '/external_permission/resource_by_action/',
};

// 获取操作类型
const getActionList = {
  method: 'get',
  url: '/external_permission/action/',
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
