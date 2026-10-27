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

import type { ResourceItem } from '../shared/resource/resource-list-controller';

export interface ModuleCatalog {
  id: string;
  title: string;
  path: string;
  source: string;
  items: ResourceItem[];
}

export const MANAGE_MODULES: ModuleCatalog[] = [
  {
    id: 'manage-collection',
    title: '采集项',
    path: '/manage/collection',
    source: 'src/views/manage-v2/log-collection',
    items: [
      { id: 'col-1', name: 'nginx-access', status: 'running', keyword: 'access' },
      { id: 'col-2', name: 'nginx-error', status: 'failed', keyword: 'error' },
    ],
  },
  {
    id: 'manage-index-set',
    title: '索引集',
    path: '/manage/index-set',
    source: 'src/views/manage/manage-access/components/index-set',
    items: [
      { id: 'idx-1', name: 'nginx-index', status: 'ready', keyword: 'nginx' },
      { id: 'idx-2', name: 'app-index', status: 'running', keyword: 'app' },
    ],
  },
  {
    id: 'manage-clean',
    title: '清洗模板',
    path: '/manage/clean',
    source: 'src/views/manage-v2/log-clean',
    items: [
      { id: 'clean-1', name: 'json-default', status: 'ready', keyword: 'json' },
      { id: 'clean-2', name: 'nginx-grok', status: 'ready', keyword: 'grok' },
    ],
  },
  {
    id: 'manage-extract',
    title: '日志提取',
    path: '/manage/extract',
    source: 'src/views/manage-v2/log-extract',
    items: [
      { id: 'ext-1', name: 'extract-nightly', status: 'running', keyword: 'nightly' },
      { id: 'ext-2', name: 'extract-failed', status: 'failed', keyword: 'fail' },
    ],
  },
  {
    id: 'manage-archive',
    title: '日志归档',
    path: '/manage/archive',
    source: 'src/views/manage-v2/log-archive',
    items: [
      { id: 'arc-1', name: 'hot-to-cold', status: 'ready', keyword: 'cold' },
      { id: 'arc-2', name: 'restore-demo', status: 'running', keyword: 'restore' },
    ],
  },
  {
    id: 'manage-es',
    title: 'ES 集群',
    path: '/manage/es',
    source: 'src/views/manage-v2/es-cluster',
    items: [
      { id: 'es-1', name: 'es-default', status: 'running', keyword: 'default' },
      { id: 'es-2', name: 'es-backup', status: 'stopped', keyword: 'backup' },
    ],
  },
  {
    id: 'manage-grok',
    title: 'Grok 管理',
    path: '/manage/grok',
    source: 'src/views/manage-v2/grok-manage',
    items: [
      { id: 'grok-1', name: 'nginx-combined', status: 'ready', keyword: 'nginx' },
    ],
  },
  {
    id: 'manage-client-log',
    title: '客户端采集',
    path: '/manage/client-log',
    source: 'src/views/manage-v2/client-log',
    items: [
      { id: 'cli-1', name: 'desktop-agent', status: 'running', keyword: 'agent' },
    ],
  },
  {
    id: 'client-log-search',
    title: '客户端检索',
    path: '/client-log-search',
    source: 'src/views/client-log-search',
    items: [
      { id: 'cls-1', name: 'login-task', status: 'ready', keyword: 'login' },
    ],
  },
  {
    id: 'extract',
    title: '提取任务中心',
    path: '/extract',
    source: 'src/views/extract',
    items: [
      { id: 'task-1', name: 'pack-20261026', status: 'running', keyword: 'pack' },
    ],
  },
  {
    id: 'dashboard',
    title: '仪表盘',
    path: '/dashboard',
    source: 'src/views/dashboard',
    items: [
      { id: 'dash-1', name: 'error-overview', status: 'ready', keyword: 'error' },
    ],
  },
  {
    id: 'authorization',
    title: '授权管理',
    path: '/authorization',
    source: 'src/views/authorization',
    items: [
      { id: 'auth-1', name: 'biz-visitor', status: 'ready', keyword: 'visitor' },
    ],
  },
  {
    id: 'share',
    title: '分享链接',
    path: '/share',
    source: 'src/views/share',
    items: [
      { id: 'share-1', name: 'incident-link', status: 'ready', keyword: 'incident' },
    ],
  },
  {
    id: 'retrieve-template',
    title: '检索模板',
    path: '/retrieve/template',
    source: 'src/views/retrieve-v3/search-result/template-manage',
    items: [
      { id: 'tpl-1', name: 'error-template', status: 'ready', keyword: 'error' },
    ],
  },
  {
    id: 'data-id-url',
    title: '数据 ID 链接',
    path: '/data-id-url',
    source: 'src/views/data-id-url',
    items: [
      { id: 'did-1', name: 'dataid-1001', status: 'ready', keyword: '1001' },
    ],
  },
];
