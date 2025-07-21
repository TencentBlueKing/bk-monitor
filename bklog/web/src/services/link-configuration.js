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
 * 链路配置相关接口
 */

// 链路列表
const getLinkList = {
  method: 'get',
  url: '/databus/data_link/',
};
// 链路详情
const getLinkDetail = {
  method: 'get',
  url: '/databus/data_link/:data_link_id/',
};
// 创建链路
const createLink = {
  method: 'post',
  url: '/databus/data_link/',
};
// 更新链路
const updateLink = {
  method: 'put',
  url: '/databus/data_link/:data_link_id/',
};
// 删除链路
const deleteLink = {
  method: 'delete',
  url: '/databus/data_link/:data_link_id/',
};

// 集群列表
const getClusterList = {
  method: 'get',
  url: '/databus/data_link/get_cluster_list/',
};
// cmdb补充数据列表
const getSearchObjectAttribute = {
  method: 'get',
  url: '/databus/collectors/search_object_attribute/',
};
export {
  getLinkList,
  getLinkDetail,
  createLink,
  updateLink,
  deleteLink,
  getClusterList,
  getSearchObjectAttribute,
};
