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

const getTaskList = {
  method: 'get',
  url: '/log_extract/tasks/',
};

const getTaskDetail = {
  method: 'get',
  url: '/log_extract/tasks/:id/',
};

const getTopoIpList = {
  method: 'get',
  url: '/log_extract/explorer/topo/',
};

// 文件浏览策略，返回某用户在某业务-某IP 中可访问的目录的文件类型
const getAvailableExplorerPath = {
  method: 'post',
  url: '/log_extract/explorer/strategies/',
};

// 预览用户在业务机器中的可下载的文件
const getExplorerList = {
  method: 'post',
  url: '/log_extract/explorer/list_file/',
};

// 点击开始下载后创建下载任务
const createDownloadTask = {
  method: 'post',
  url: '/log_extract/tasks/',
};

// 点击重新下载
const reDownloadFile = {
  method: 'post',
  url: '/log_extract/tasks/recreate/',
};

// 轮询任务状态
const pollingTaskStatus = {
  method: 'get',
  url: '/log_extract/tasks/polling/',
};

// 轮询任务状态
const getDownloadUrl = {
  method: 'get',
  url: '/log_extract/tasks/download/',
};

// 提取链路接口
const getExtractLinkList = {
  method: 'get',
  url: '/log_extract/tasks/link_list/',
};

// 获取下载目标主机数量的拓扑树
const trees = {
  method: 'post',
  url: '/log_extract/explorer/trees/',
};

// 根据多个拓扑节点与搜索条件批量分页查询所包含的主机信息
const queryHosts = {
  method: 'post',
  url: '/log_extract/explorer/query_hosts/',
};

// 根据多个拓扑节点与搜索条件批量分页查询所包含的主机ID信息
const queryHostIdInfos = {
  method: 'post',
  url: '/log_extract/explorer/query_host_id_infos/',
};

const getIpListDisplayName = {
  method: 'post',
  url: '/bizs/:bk_biz_id/get_display_name/',
};

export {
  getTaskList,
  getTaskDetail,
  getTopoIpList,
  getAvailableExplorerPath,
  getExplorerList,
  createDownloadTask,
  reDownloadFile,
  pollingTaskStatus,
  getDownloadUrl,
  getExtractLinkList,
  trees,
  queryHosts,
  queryHostIdInfos,
  getIpListDisplayName,
};
