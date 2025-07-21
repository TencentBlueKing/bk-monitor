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
  method: 'get',
  url: '/clustering_config/:index_set_id/config/',
};

const getDefaultConfig = {
  method: 'get',
  url: '/clustering_config/default_config/',
};

const debug = {
  method: 'post',
  url: '/clustering_config/debug/',
};

const clusterSearch = {
  method: 'post',
  url: '/pattern/:index_set_id/search/',
};

const closeClean = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/close_clean/',
};

const updateStrategies = {
  method: 'post',
  url: '/clustering_monitor/:index_set_id/update_strategies/',
};

const getFingerLabels = {
  method: 'post',
  url: '/pattern/:index_set_id/labels/',
};

const updateNewClsStrategy = {
  method: 'post',
  url: '/clustering_monitor/:index_set_id/update_new_cls_strategy/',
};

const checkRegexp = {
  method: 'post',
  url: '/clustering_config/check_regexp/',
};

// 设置备注
const setRemark = {
  method: 'post',
  url: '/pattern/:index_set_id/remark/ ',
};

// 更新备注
const updateRemark = {
  method: 'put',
  url: '/pattern/:index_set_id/update_remark/ ',
};

// 删除备注
const deleteRemark = {
  method: 'delete',
  url: '/pattern/:index_set_id/delete_remark/ ',
};

// 设置负责人
const setOwner = {
  method: 'post',
  url: '/pattern/:index_set_id/owner/',
};

// 获取当前pattern所有负责人列表
const getOwnerList = {
  method: 'get',
  url: '/pattern/:index_set_id/list_owners/',
};

// 第一次进数据指纹时候的分组
const updateInitGroup = {
  method: 'post',
  url: '/pattern/:index_set_id/group_fields/',
};

// 模板列表
const ruleTemplate = {
  method: 'get',
  url: '/regex_template/?space_uid=:space_uid',
};

// 创建模板
const createTemplate = {
  method: 'post',
  url: '/regex_template/',
};

// 更新模板（名称）
const updateTemplateName = {
  method: 'patch',
  url: '/regex_template/:regex_template_id/',
};

// 删除模板
const deleteTemplate = {
  method: 'delete',
  url: '/regex_template/:regex_template_id/',
};

// 日志聚类-告警策略开关
const updatePatternStrategy = {
  method: 'post',
  url: '/pattern/:index_set_id/pattern_strategy/',
};
export {
  getConfig,
  getDefaultConfig,
  debug,
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
  ruleTemplate,
  createTemplate,
  updateTemplateName,
  deleteTemplate,
  updatePatternStrategy,
};
