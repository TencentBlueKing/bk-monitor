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

import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';

import { MANAGE_MODULES } from './features/catalog';
import CollectionPage from './features/manage/collection-page.vue';
import ClusteringPage from './features/retrieve/clustering-page.vue';
import ContextPage from './features/retrieve/context-page.vue';
import RealtimePage from './features/retrieve/realtime-page.vue';
import RetrievePage from './features/retrieve/retrieve-page.vue';
import ResourceListPage from './features/resource/resource-list-page.vue';
import NotFoundPage from './features/system/not-found-page.vue';
import UnauthorizedPage from './features/system/unauthorized-page.vue';

const resourceRoutes: RouteRecordRaw[] = MANAGE_MODULES.filter(module => module.id !== 'manage-collection').map(module => ({
  path: module.path,
  name: module.id,
  component: ResourceListPage,
  props: { moduleId: module.id },
  meta: { title: module.title, group: module.id.startsWith('manage-') ? 'manage' : 'other' },
}));

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/retrieve' },
  { path: '/retrieve', name: 'retrieve-search', component: RetrievePage, meta: { title: '日志检索', group: 'retrieve' } },
  { path: '/retrieve/clustering', name: 'retrieve-clustering', component: ClusteringPage, meta: { title: '日志聚类', group: 'retrieve' } },
  { path: '/retrieve/context', name: 'retrieve-context', component: ContextPage, meta: { title: '上下文日志', group: 'retrieve' } },
  { path: '/retrieve/realtime', name: 'retrieve-realtime', component: RealtimePage, meta: { title: '实时日志', group: 'retrieve' } },
  { path: '/manage/collection', name: 'manage-collection', component: CollectionPage, meta: { title: '采集项', group: 'manage' } },
  ...resourceRoutes,
  { path: '/unauthorized', name: 'unauthorized', component: UnauthorizedPage, meta: { title: '未授权', group: 'system' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundPage, meta: { title: '未找到', group: 'system' } },
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
});
