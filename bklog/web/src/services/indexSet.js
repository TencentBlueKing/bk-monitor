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
 * 索引集相关接口
 */

// 索引集列表
const list = {
  method: 'get',
  url: '/index_set/',
};

// 索引集详情
const info = {
  method: 'get',
  url: '/index_set/:index_set_id/',
};

// 创建索引集
const create = {
  method: 'post',
  url: '/index_set/',
};

// 更新索引集
const update = {
  method: 'put',
  url: '/index_set/:index_set_id/',
};

// 删除索引集
const remove = {
  method: 'delete',
  url: '/index_set/:index_set_id/',
};

// 索引列表
const index = {
  method: 'get',
  url: '/index_set/:index_set_id/index/',
};

// 采集索引列表
const indexes = {
  method: 'get',
  url: '/index_set/:index_set_id/indices/',
};

// 创建索引
const createIndex = {
  method: 'get',
  url: '/index_set/:index_set_id/index/',
};

// 删除索引
const removeIndex = {
  method: 'post',
  url: '/index_set/:index_set_id/index/:index_id/',
};

// 标记索引集为收藏索引集
const mark = {
  method: 'post',
  url: '/index_set/:index_set_id/mark_favorite/',
};

// 取消标记为收藏索引集
const cancelMark = {
  method: 'post',
  url: '/index_set/:index_set_id/cancel_favorite/',
};

// 使用次数趋势
const getIndexTimes = {
  method: 'get',
  url: '/admin/index_set/:index_set_id/history/date_histogram/',
};

// 用户使用频次
const getIndexFrequency = {
  method: 'get',
  url: '/admin/index_set/:index_set_id/history/user_terms/',
};

// 检索耗时统计
const getIndexSpent = {
  method: 'get',
  url: '/admin/index_set/:index_set_id/history/duration_terms/',
};

// 检索记录（表格）
const getIndexHistory = {
  method: 'get',
  url: '/admin/index_set/:index_set_id/history/',
};

// 操作记录
const getOperationRecord = {
  url: '/admin/audit/record/',
};

export {
  list,
  info,
  create,
  update,
  remove,
  index,
  indexes,
  removeIndex,
  createIndex,
  mark,
  cancelMark,
  getIndexTimes,
  getIndexFrequency,
  getIndexSpent,
  getIndexHistory,
  getOperationRecord,
};
