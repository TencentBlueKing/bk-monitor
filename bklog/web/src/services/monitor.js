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
 * 监控策略
 */

// 监控策略列表
const list = {
  method: 'get',
  url: '/monitor/policy/',
};

// 创建监控策略
const create = {
  method: 'post',
  url: '/monitor/policy/',
};

// 删除监控策略
const remove = {
  method: 'delete',
  url: '/monitor/policy/:policy_id/',
};

// 监控策略启动
const start = {
  method: 'post',
  url: '/monitor/policy/:policy_id/start/',
};

// 监控策略停止
const stop = {
  method: 'post',
  url: '/monitor/policy/:policy_id/stop/',
};

// 编辑监控策略
const updata = {
  method: 'put',
  url: '/monitor/policy/:policy_id/',
};

// 监控策略详情
const particulars = {
  method: 'get',
  url: '/monitor/policy/:policy_id/',
};

// 获取监控类型列表
const type = {
  method: 'get',
  url: '/monitor/',
};

// 获取告警等级
const levels = {
  method: 'get',
  url: '/monitor/alarm/levels/',
};

// 获取告警记录
const alarm = {
  method: 'get',
  url: '/monitor/alarm/',
};

// 获取屏蔽策略列表
const shields = {
  method: 'get',
  url: '/monitor/shields/',
};

// 获取屏蔽类型
const shieldsType = {
  method: 'get',
  url: '/monitor/shields/type/',
};

// 新增屏蔽策略
const addShields = {
  method: 'post',
  url: '/monitor/shields/',
};

// 删除屏蔽策略
const removeShields = {
  method: 'delete',
  url: '/monitor/shields/:shield_id/',
};

// 获取屏蔽策略详情
const shieldsInfo = {
  method: 'get',
  url: '/monitor/shields/:shield_id/',
};

// 更新屏蔽策略
const updateShields = {
  method: 'put',
  url: '/monitor/shields/:shield_id/',
};

// 获取索引集
const index = {
  method: 'get',
  url: '/monitor/index_set/',
};

export {
  list,
  create,
  remove,
  start,
  updata,
  stop,
  type,
  particulars,
  levels,
  alarm,
  shields,
  shieldsType,
  addShields,
  removeShields,
  shieldsInfo,
  updateShields,
  index,
};
