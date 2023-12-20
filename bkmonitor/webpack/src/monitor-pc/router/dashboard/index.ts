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
import { RouteConfig } from 'vue-router';

import * as grafanaAuth from '../../pages/grafana/authority-map';

const Grafana = () => import(/* webpackChunkName: 'Grafana' */ '../../pages/grafana/grafana');
export default [
  {
    path: '/grafana',
    name: 'grafana',
    components: {
      noCache: Grafana
    },
    meta: {
      title: '仪表盘',
      navId: 'grafana',
      navName: '仪表盘',
      noNavBar: true,
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.VIEW_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/new',
    name: 'new-dashboard',
    components: {
      noCache: Grafana
    },
    props: {
      noCache: {
        url: 'dashboard/new'
      }
    },
    meta: {
      title: '仪表盘',
      navId: 'new-dashboard',
      navName: '仪表盘',
      noNavBar: true,
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.NEW_DASHBOARD_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/import',
    name: 'import-dashboard',
    components: {
      noCache: Grafana
    },
    props: {
      noCache: {
        url: 'dashboard/import'
      }
    },
    meta: {
      title: '仪表盘',
      noNavBar: true,
      navId: 'import-dashboard',
      navName: '仪表盘',
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.NEW_DASHBOARD_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/folder/new',
    name: 'folder-dashboard',
    components: {
      noCache: Grafana
    },
    props: {
      noCache: {
        url: 'dashboards/folder/new'
      }
    },
    meta: {
      title: '仪表盘',
      navId: 'folder-dashboard',
      navName: '仪表盘',
      noNavBar: true,
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.NEW_DASHBOARD_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/datasource',
    name: 'grafana-datasource',
    components: {
      noCache: Grafana
    },
    props: {
      noCache: {
        url: 'datasources'
      }
    },
    meta: {
      title: '仪表盘',
      navId: 'grafana-datasource',
      navName: '仪表盘',
      noNavBar: true,
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.DATASOURCE_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/home',
    name: 'grafana-home',
    components: {
      noCache: Grafana
    },
    meta: {
      title: '仪表盘',
      navName: '仪表盘',
      noNavBar: true,
      navId: 'grafana',
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.VIEW_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  },
  {
    path: '/grafana/d/:url',
    name: 'favorite-dashboard',
    components: {
      noCache: Grafana
    },
    props: {
      noCache: true
    },
    meta: {
      title: '仪表盘',
      navId: 'grafana',
      navName: '仪表盘',
      noNavBar: true,
      authority: {
        map: grafanaAuth,
        page: grafanaAuth.VIEW_AUTH
      },
      route: {
        parent: 'dashboard'
      },
      pageCls: 'grafana-page'
    }
  }
] as RouteConfig[];
