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
export const dashboardTreeData = [
  {
    id: 1,
    title: 'General',
    type: 'folder',
    dashboards: [
      {
        id: 101,
        uid: 'general-1',
        title: '系统概览',
        type: 'dashboard',
      },
      {
        id: 102,
        uid: 'general-2',
        title: '性能监控',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 2,
    title: 'bcs',
    type: 'folder',
    dashboards: [
      {
        id: 201,
        uid: 'bcs-1',
        title: '容器监控',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 3,
    title: 'bcs-cluster',
    type: 'folder',
    dashboards: [
      {
        id: 301,
        uid: 'cluster-1',
        title: '集群状态',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 4,
    title: 'gamesvr',
    type: 'folder',
    dashboards: [
      {
        id: 401,
        uid: 'gamesvr-1',
        title: '游戏服务器',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 5,
    title: 'sapiagent',
    type: 'folder',
    dashboards: [
      {
        id: 501,
        uid: 'sapiagent-1',
        title: '代理服务',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 6,
    title: '大盘监控',
    type: 'folder',
    dashboards: [
      {
        id: 601,
        uid: 'bigboard-1',
        title: '主控面板',
        type: 'dashboard',
      },
    ],
  },
  {
    id: 7,
    title: '数据组',
    type: 'folder',
    dashboards: [
      {
        id: 701,
        uid: 'data-group-1',
        title: 'tRPC 主调监控',
        type: 'dashboard',
      },
      {
        id: 702,
        uid: 'data-group-2',
        title: 'tRPC 服务监控',
        type: 'dashboard',
      },
      {
        id: 703,
        uid: 'data-group-3',
        title: 'tRPC 被调监控',
        type: 'dashboard',
      },
    ],
  },
];
