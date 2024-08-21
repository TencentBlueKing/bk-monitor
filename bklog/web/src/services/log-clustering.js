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
 * 通知列表
 */
const getConfig = {
  url: '/clustering_config/:index_set_id/config/',
  method: 'get',
};

const getDefaultConfig = {
  url: '/clustering_config/default_config/',
  method: 'get',
};

const changeConfig = {
  url: '/clustering_config/:index_set_id/create_or_update/',
  method: 'post',
};

const preview = {
  url: '/clustering_config/preview/',
  method: 'post',
};

const clusterSearch = {
  url: '/pattern/:index_set_id/search/',
  method: 'post',
};

const closeClean = {
  url: '/databus/collectors/:collector_config_id/close_clean/',
  method: 'post',
};

const updateStrategies = {
  url: '/clustering_monitor/:index_set_id/update_strategies/',
  method: 'post',
};

const getFingerLabels = {
  url: '/pattern/:index_set_id/labels/',
  method: 'post',
};

const updateNewClsStrategy = {
  url: '/clustering_monitor/:index_set_id/update_new_cls_strategy/',
  method: 'post',
};

const checkRegexp = {
  url: '/clustering_config/check_regexp/',
  method: 'post',
};

// 设置备注
const setRemark = {
  url: '/pattern/:index_set_id/remark/ ',
  method: 'post',
};

// 更新备注
const updateRemark = {
  url: '/pattern/:index_set_id/update_remark/ ',
  method: 'put',
};

// 删除备注
const deleteRemark = {
  url: '/pattern/:index_set_id/delete_remark/ ',
  method: 'delete',
};

// 设置负责人
const setOwner = {
  url: '/pattern/:index_set_id/owner/',
  method: 'post',
};

// 获取当前pattern所有负责人列表
const getOwnerList = {
  url: '/pattern/:index_set_id/list_owners/',
  method: 'get',
};

// 第一次进数据指纹时候的分组
const updateInitGroup = {
  url: '/pattern/:index_set_id/group_fields/',
  method: 'post',
};

export {
  getConfig,
  getDefaultConfig,
  changeConfig,
  preview,
  clusterSearch,
  closeClean,
  updateStrategies,
  getFingerLabels,
  updateNewClsStrategy,
  checkRegexp,
  setRemark,
  setOwner,
  updateRemark,
  deleteRemark,
  getOwnerList,
  updateInitGroup,
};
