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

import { applyGuidePage } from '../../common';
import * as collectConfigAuth from '../../pages/collector-config/authority-map';

import type { RouteConfig } from 'vue-router';

const CollectorConfig = () =>
  import(/* webpackChunkName: 'CollectorConfig' */ '@page/collector-config/collector-config.vue');
// const CollectorConfigView = () => import(/* webpackChunkName: 'CollectorConfigView' */'@page/collector-config/collector-view/collector-view.vue')
const CollectorConfigViewNew = () =>
  import(
    /* webpackChunkName: 'CollectorConfigViewNew' */ '../../pages/collector-config/collector-view-detail/collector-view'
  );
const CollectorConfigAdd = () =>
  import(/* webpackChunkName: 'CollectorConfigAdd' */ '@page/collector-config/collector-add/collector-add.vue');
const CollectorConfigNode = () =>
  import(/* webpackChunkName: 'CollectorConfigNode' */ '@page/collector-config/collector-target-add-del/add-del.vue');
const CollectorConfigUpdate = () =>
  import(
    /* webpackChunkName: 'CollectorConfigUpdate' */ '@page/collector-config/collector-stop-start/stop-start-view.vue'
  );
const CollectorConfigOperateDetail = () =>
  import(
    /* webpackChunkName: 'CollectorConfigOperateDetail' */ '../../pages/collector-config/collector-host-detail/collector-operate-detail'
  );
// import(
//   /* webpackChunkName: 'CollectorConfigOperateDetail' */ '../../pages/collector-config/collector-host-detail/collector-host-detail.vue'
// );
const CollectorDetail = () =>
  import(/* webpackChunkName: 'CollectorDetail' */ '../../pages/collector-config/collector-detail/collector-detail');
export default applyGuidePage(
  [
    {
      path: '/collect-config',
      name: 'collect-config',
      component: CollectorConfig,
      meta: {
        title: '数据采集',
        navId: 'collect-config',
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.VIEW_AUTH],
        },
        route: {
          parent: 'integrated',
        },
        noNavBar: true,
      },
    },
    {
      path: '/collect-config/view/:id',
      name: 'collect-config-view',
      components: {
        noCache: CollectorConfigViewNew,
      },
      props: {
        noCache: true,
      },
      meta: {
        title: '可视化',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.VIEW_AUTH],
        },
        customContent: true,
        noNavBar: true,
        route: {
          parent: 'collect-config',
        },
      },
    },
    {
      path: '/collect-config/add',
      name: 'collect-config-add',
      props: true,
      components: {
        noCache: CollectorConfigAdd,
      },
      beforeEnter(to, from, next) {
        to.meta.title = to.params.title || '新建配置';
        next();
      },
      meta: {
        title: '新建配置',
        navId: 'collect-config',
        needBack: true,
        noSpaceCheck: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.MANAGE_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
      },
    },
    {
      path: '/collect-config/clone/:id/:pluginId',
      name: 'collect-config-clone',
      props: true,
      components: {
        noCache: CollectorConfigAdd,
      },
      beforeEnter(to, from, next) {
        to.meta.title = to.params.title || '新建配置';
        next();
      },
      meta: {
        title: '新建配置',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.MANAGE_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
      },
    },
    {
      path: '/collect-config/edit/:id/:pluginId',
      name: 'collect-config-edit',
      props: true,
      components: {
        noCache: CollectorConfigAdd,
      },
      beforeEnter(to, from, next) {
        to.meta.title = to.params.title || '编辑配置';
        next();
      },
      meta: {
        title: '编辑配置',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.MANAGE_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
        needCopyLink: false,
        // noNavBar: true
      },
    },
    {
      path: '/collect-config/node/:id',
      name: 'collect-config-node',
      props: true,
      components: {
        noCache: CollectorConfigNode,
      },
      meta: {
        title: '增删目标',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.MANAGE_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
        needCopyLink: false,
        // noNavBar: true
      },
    },
    {
      path: '/collect-config/update',
      name: 'collect-config-update',
      props: true,
      components: {
        noCache: CollectorConfigUpdate,
      },
      beforeEnter(to, from, next) {
        if (!to.params.data) {
          next({ path: '/collect-config' });
        } else {
          next();
        }
      },
      meta: {
        title: '启用采集配置',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.MANAGE_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
        noNavBar: true,
      },
    },
    {
      path: '/collect-config/operate-detail/:id',
      name: 'collect-config-operate-detail',
      props: true,
      components: {
        noCache: CollectorConfigOperateDetail,
      },
      beforeEnter(to, from, next) {
        if (!to.params.id) {
          next({ path: '/collect-config' });
        } else {
          to.meta.title = to.params.title || '执行详情';
          next();
        }
        next();
      },
      meta: {
        title: '执行详情',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.VIEW_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
        // needCopyLink: true
      },
    },
    {
      path: '/collect-config/detail/:id',
      name: 'collect-config-detail',
      props: true,
      components: {
        noCache: CollectorDetail,
      },
      beforeEnter(to, from, next) {
        if (!to.params.id) {
          next({ path: '/collect-config' });
        } else {
          to.meta.title = to.params.title || '采集详情';
          next();
        }
        next();
      },
      meta: {
        title: '采集详情',
        navId: 'collect-config',
        needBack: true,
        authority: {
          map: collectConfigAuth,
          page: [collectConfigAuth.VIEW_AUTH],
        },
        route: {
          parent: 'collect-config',
        },
        // needCopyLink: true
      },
    },
  ] as RouteConfig[],
  ['collect-config-add', 'collect-config-edit']
);
