import { defineEndpoint } from '@/platform/services/runtime/service-client';
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

const list = defineEndpoint({
  url: '/databus/storage/',
  method: 'get',
});
const logList = defineEndpoint({
  url: '/databus/storage/log_cluster/',
  method: 'get',
});

const scenario = defineEndpoint({
  url: '/meta/scenario/',
  method: 'get',
});

const create = defineEndpoint({
  url: '/databus/storage/?bk_biz_id=:bk_biz_id',
  method: 'post',
});

const getProperty = defineEndpoint({
  url: '/bizs/get_property/',
  method: 'get',
});

const deleteEs = defineEndpoint({
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
  method: 'delete',
});

const remove = defineEndpoint({
  url: '/source/:source_id/',
  method: 'delete',
});

const update = defineEndpoint({
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
  method: 'put',
});

// 更新 Doris 集群可见范围
const updateVisibleConfig = defineEndpoint({
  url: '/databus/storage/:cluster_id/visible_config/',
  method: 'put',
});

const info = defineEndpoint({
  url: '/databus/storage/:cluster_id/?bk_biz_id=:bk_biz_id',
  method: 'get',
});

const connectivityDetect = defineEndpoint({
  url: '/esb/databus/storage/connectivity_detect/',
  method: 'post',
});

// 连通性测试之后获取集群中各节点属性
const getNodeAttrs = defineEndpoint({
  url: '/databus/storage/node_attrs/',
  method: 'post',
});

const connectionStatus = defineEndpoint({
  url: '/databus/storage/batch_connectivity_detect/',
  method: 'post',
});
// 数据采集相关接口
const getCollectList = defineEndpoint({
  url: '/databus/collectors/',
  method: 'get',
});
/**
 * 轮询-批量获取采集项订阅状态
 */
const getCollectStatus = defineEndpoint({
  url: '/databus/collectors/batch_subscription_status/',
  method: 'get',
});

const createCollection = defineEndpoint({
  url: '/databus/storage/',
  method: 'post',
});
const deleteCollection = defineEndpoint({
  url: '/collectors/:collector_config_id/',
  method: 'delete',
});
const startCollection = defineEndpoint({
  url: '/collectors/:collector_config_id/start/',
  method: 'post',
});
const stopCollection = defineEndpoint({
  url: '/collectors/:collector_config_id/stop/',
  method: 'post',
});
// 采集下发 列表&轮询共用同一接口
const getIssuedClusterList = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/task_status/',
  method: 'get',
});

/**
 * 采集配置相关接口
 */

const detailsList = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/',
  method: 'get',
});

// 物理索引
const getIndexes = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/indices_info/',
  method: 'get',
});

const collectList = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/subscription_status/',
  method: 'get',
});

const retryList = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/retry/',
  method: 'post',
});

const dataList = defineEndpoint({
  url: '/esb/databus/collectors/:collector_config_id/tail/',
  method: 'get',
});

// 采集下发 - 重试
const issuedRetry = defineEndpoint({
  url: '/databus/collectors/:collector_config_id/subscription_run/',
  method: 'post',
});

// es集群
const getEsList = defineEndpoint({
  url: '/databus/storage/cluster_groups',
  method: 'get',
});

export {
  list,
  logList,
  remove,
  create,
  deleteEs,
  update,
  updateVisibleConfig,
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
