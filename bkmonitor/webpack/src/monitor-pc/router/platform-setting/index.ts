/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import * as platformSettingAuth from '../../pages/platform-setting/authority-map';
import {
  buildRedisManagementForbiddenQuery,
  resolveRedisManagementAccess,
} from '../../pages/redis-management/route-model';
import authorityStore from '../../store/modules/authority';

import type { RouteConfig } from 'vue-router';

const PlatformSetting = () =>
  import(/* webpackChunkName: 'PlatformSettings' */ '../../pages/platform-setting/platform-setting');
const RedisManagement = () =>
  import(/* webpackChunkName: 'RedisManagement' */ '../../pages/redis-management/redis-management');
export default [
  {
    path: '/platform-setting',
    name: 'platform-setting',
    components: {
      noCache: PlatformSetting,
    },
    meta: {
      title: '平台设置',
      navId: 'platform-setting',
      pageCls: 'platform-setting',
      noNavBar: true,
      authority: {
        page: platformSettingAuth.MANAGE_GLOBAL_SETTING,
      },
    },
  },
  {
    path: '/redis-management',
    name: 'redis-management',
    components: {
      noCache: RedisManagement,
    },
    async beforeEnter(to, _from, next) {
      const allowed = await resolveRedisManagementAccess(window.is_superuser, () =>
        authorityStore.checkAllowedByActionIds({ action_ids: [platformSettingAuth.MANAGE_GLOBAL_SETTING] })
      );
      if (allowed) {
        next();
        return;
      }
      next({
        name: 'error-exception',
        params: { type: '403' },
        query: buildRedisManagementForbiddenQuery(
          window.is_superuser,
          platformSettingAuth.MANAGE_GLOBAL_SETTING,
          to.fullPath
        ),
      });
    },
    meta: {
      title: 'Redis 节点管理',
      navId: 'redis-management',
      navName: 'Redis 节点管理',
      noNavBar: true,
      pageCls: 'redis-management-page',
      authority: {
        page: platformSettingAuth.MANAGE_GLOBAL_SETTING,
      },
    },
  },
] as RouteConfig[];
