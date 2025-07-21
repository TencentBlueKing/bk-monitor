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

// 获取集群快照仓库列表
const getRepositoryList = {
  method: 'get',
  url: '/databus/storage/list_repository/',
};

// 新增归档仓库
const createRepository = {
  method: 'post',
  url: '/meta/esb/create_es_snapshot_repository/',
};

// 删除归档仓库
const deleteRepository = {
  method: 'post',
  url: '/meta/esb/delete_es_snapshot_repository/',
};

// 归档列表
const getArchiveList = {
  method: 'get',
  url: '/databus/archive/',
};

// 新建归档
const createArchive = {
  method: 'post',
  url: '/databus/archive/',
};

// 编辑归档
const editArchive = {
  method: 'put',
  url: '/databus/archive/:archive_config_id',
};

// 删除归档
const deleteArchive = {
  method: 'delete',
  url: '/databus/archive/:archive_config_id/',
};

// 归档配置详情
const archiveConfig = {
  method: 'get',
  url: '/databus/archive/:archive_config_id/',
};

// 回溯列表
const restoreList = {
  method: 'get',
  url: '/databus/restore/',
};

// 全量获取归档列表
const getAllArchives = {
  method: 'get',
  url: '/databus/archive/list_archive/',
};

// 新建回溯
const createRestore = {
  method: 'post',
  url: '/databus/restore/',
};

// 编辑回溯
const editRestore = {
  method: 'put',
  url: '/databus/restore/:restore_config_id/',
};

// 删除回溯
const deleteRestore = {
  method: 'delete',
  url: '/databus/restore/:restore_config_id/',
};

// 异步获取回溯状态
const getRestoreStatus = {
  method: 'post',
  url: '/databus/restore/batch_get_state/',
};

export {
  getRepositoryList,
  createRepository,
  deleteRepository,
  getArchiveList,
  createArchive,
  deleteArchive,
  archiveConfig,
  restoreList,
  getAllArchives,
  editArchive,
  createRestore,
  deleteRestore,
  getRestoreStatus,
  editRestore,
};
