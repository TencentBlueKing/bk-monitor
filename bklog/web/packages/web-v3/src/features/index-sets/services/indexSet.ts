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

import { defineEndpoint } from '@/platform/services/runtime/service-client';

/**
 * 索引集相关接口
 */

// 索引集列表
const list = defineEndpoint({
  url: '/index_set/',
  method: 'get',
});

// 索引集详情
const info = defineEndpoint({
  url: '/index_set/:index_set_id/',
  method: 'get',
});

// 创建索引集
const create = defineEndpoint({
  url: '/index_set/',
  method: 'post',
});

// 更新索引集
const update = defineEndpoint({
  url: '/index_set/:index_set_id/',
  method: 'put',
});

// 删除索引集
const remove = defineEndpoint({
  url: '/index_set/:index_set_id/',
  method: 'delete',
});

// 索引列表
const index = defineEndpoint({
  url: '/index_set/:index_set_id/index/',
  method: 'get',
});

// 采集索引列表
const indexes = defineEndpoint({
  url: '/index_set/:index_set_id/indices/',
  method: 'get',
});

/**
 * 获取索引集的空间
 */
const getSpaceByIndexId = defineEndpoint({
  url: '/index_set/:index_set_id/space/',
  method: 'get',
});

// 创建索引
const createIndex = defineEndpoint({
  url: '/index_set/:index_set_id/index/',
  method: 'get',
});

// 删除索引
const removeIndex = defineEndpoint({
  url: '/index_set/:index_set_id/index/:index_id/',
  method: 'post',
});

// 标记索引集为收藏索引集
const mark = defineEndpoint({
  url: '/index_set/:index_set_id/mark_favorite/',
  method: 'post',
});

// 取消标记为收藏索引集
const cancelMark = defineEndpoint({
  url: '/index_set/:index_set_id/cancel_favorite/',
  method: 'post',
});

// 使用次数趋势
const getIndexTimes = defineEndpoint({
  url: '/admin/index_set/:index_set_id/history/date_histogram/',
  method: 'get',
});

// 用户使用频次
const getIndexFrequency = defineEndpoint({
  url: '/admin/index_set/:index_set_id/history/user_terms/',
  method: 'get',
});

// 检索耗时统计
const getIndexSpent = defineEndpoint({
  url: '/admin/index_set/:index_set_id/history/duration_terms/',
  method: 'get',
});

// 检索记录（表格）
const getIndexHistory = defineEndpoint({
  url: '/admin/index_set/:index_set_id/history/',
  method: 'get',
});

// 操作记录
const getOperationRecord = defineEndpoint({
  url: '/admin/audit/record/',
});

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
  getSpaceByIndexId,
};
