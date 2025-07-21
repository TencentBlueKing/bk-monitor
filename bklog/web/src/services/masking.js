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
 * 获取规则详情
 */
const getDesensitize = {
  method: 'get',
  url: 'desensitize/rule/:rule_id/',
};
/**
 * 脱敏规则正则调试
 */
const desensitizeDebug = {
  method: 'post',
  url: '/desensitize/rule/debug/',
};
/**
 * 获取索引集脱敏配置详情
 */
const getMaskingConfig = {
  method: 'get',
  url: '/index_set/:index_set_id/desensitize/config/retrieve/',
};
/**
 * 获取当前日志查询字符串
 */
const getMaskingSearchStr = {
  method: 'post',
  url: '/search/index_set/:index_set_id/search/original/',
};
/**
 * 接口获取脱敏预览
 */
const getConfigPreview = {
  method: 'post',
  url: '/desensitize/rule/preview/',
};
/**
 * 匹配脱敏规则
 */
const matchMaskingRule = {
  method: 'post',
  url: '/desensitize/rule/match/',
};

/**
 * 获取规则列表
 */
const getMaskingRuleList = {
  method: 'get',
  url: '/desensitize/rule/?space_uid=:space_uid&rule_type=:rule_type',
};

/**
 * 删除规则
 */
const deleteRule = {
  method: 'delete',
  url: '/desensitize/rule/:rule_id/',
};
/**
 * 启用规则
 */
const startDesensitize = {
  method: 'post',
  url: '/desensitize/rule/:rule_id/start/',
};
/**
 * 停用规则
 */
const stopDesensitize = {
  method: 'post',
  url: '/desensitize/rule/:rule_id/stop/',
};
/**
 * 更新规则
 */
const updateDesensitize = {
  method: 'put',
  url: '/desensitize/rule/:rule_id/',
};
/**
 * 创建规则
 */
const createDesensitize = {
  method: 'post',
  url: '/desensitize/rule/',
};
/**
 * 创建日志脱敏配置
 */
const createDesensitizeConfig = {
  method: 'post',
  url: '/index_set/:index_set_id/desensitize/config/create/',
};
/**
 * 创建日志脱敏配置
 */
const updateDesensitizeConfig = {
  method: 'put',
  url: '/index_set/:index_set_id/desensitize/config/update/',
};
/**
 * 删除日志脱敏配置
 */
const deleteDesensitizeConfig = {
  method: 'delete',
  url: '/index_set/:index_set_id/desensitize/config/delete/',
};
/**
 * 获取索引集脱敏状态
 */
const getDesensitizeState = {
  method: 'post',
  url: '/index_set/desensitize/config/state/',
};

export {
  getDesensitize,
  desensitizeDebug,
  getMaskingConfig,
  getMaskingSearchStr,
  getConfigPreview,
  matchMaskingRule,
  getMaskingRuleList,
  deleteRule,
  updateDesensitize,
  createDesensitize,
  startDesensitize,
  stopDesensitize,
  createDesensitizeConfig,
  updateDesensitizeConfig,
  deleteDesensitizeConfig,
  getDesensitizeState,
};
