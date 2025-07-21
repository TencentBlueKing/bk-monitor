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
 * 数据源相关接口
 */

const list = {
  method: 'get',
  url: '/databus/storage/',
};
const logList = {
  method: 'get',
  url: '/databus/storage/log_cluster/',
};

const scenario = {
  method: 'get',
  url: '/meta/scenario/',
};

const create = {
  method: 'post',
  url: '/databus/storage/?bk_biz_id=:bk_biz_id',
};

const getProperty = {
  method: 'get',
  url: '/bizs/get_property/',
};

const deleteEs = {
  method: 'delete',
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
};

const remove = {
  method: 'delete',
  url: '/source/:source_id/',
};

const update = {
  method: 'put',
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
};

const info = {
  method: 'get',
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
};

const connectivityDetect = {
  method: 'post',
  url: '/esb/databus/storage/connectivity_detect/',
};

// 连通性测试之后获取集群中各节点属性
const getNodeAttrs = {
  method: 'post',
  url: '/databus/storage/node_attrs/',
};

const connectionStatus = {
  method: 'post',
  url: '/databus/storage/batch_connectivity_detect/',
};
// 数据采集相关接口
const getCollectList = {
  method: 'get',
  url: '/databus/collectors/',
};
/**
 * 轮询-批量获取采集项订阅状态
 */
const getCollectStatus = {
  method: 'get',
  url: '/databus/collectors/batch_subscription_status/',
};

const createCollection = {
  method: 'post',
  url: '/databus/storage/',
};
const deleteCollection = {
  method: 'delete',
  url: '/collectors/:collector_config_id/',
};
const startCollection = {
  method: 'post',
  url: '/collectors/:collector_config_id/start/',
};
const stopCollection = {
  method: 'post',
  url: '/collectors/:collector_config_id/stop/',
};
// 采集下发 列表&轮询共用同一接口
const getIssuedClusterList = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/task_status/',
};

/**
 * 采集配置相关接口
 */

const detailsList = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/',
};

// 物理索引
const getIndexes = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/indices_info/',
};

const collectList = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/subscription_status/',
};

const retryList = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/retry/',
};

const dataList = {
  method: 'get',
  url: '/esb/databus/collectors/:collector_config_id/tail/',
};

// 采集下发 - 重试
const issuedRetry = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/subscription_run/',
};

// es集群
const getEsList = {
  method: 'get',
  url: '/databus/storage/cluster_groups',
};

export {
  list,
  logList,
  remove,
  create,
  deleteEs,
  update,
  info,
  connectivityDetect,
  getNodeAttrs,
  connectionStatus,
  getCollectList,
  getCollectStatus,
  createCollection,
  deleteCollection,
  // updataCollection,
  startCollection,
  stopCollection,
  // detailCollection,
  getIssuedClusterList,
  detailsList,
  getIndexes,
  collectList,
  retryList,
  dataList,
  issuedRetry,
  scenario,
  getProperty,
  getEsList,
};
