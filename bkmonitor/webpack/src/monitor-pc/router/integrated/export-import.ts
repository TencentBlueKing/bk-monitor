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

import * as exOrInAuth from '../../pages/export-import/authority-map';

import type { RouteConfig } from 'vue-router';

const ImportExport = () => import(/* webpackChunkName: 'ImportExport' */ '@page/export-import/export-import.vue');
const ExportConfiguration = () =>
  import(
    /* webpackChunkName: 'ExportConfiguration' */ '@page/export-import/export-configuration/export-configuration.vue'
  );
const ImportConfigurationUpload = () =>
  import(
    /* webpackChunkName: 'ImportConfigurationUpload' */ '@page/export-import/import-configuration/import-configuration-upload.vue'
  );
const ImportConfiguration = () =>
  import(
    /* webpackChunkName: 'ImportConfiguration' */ '@page/export-import/import-configuration/import-configuration.vue'
  );
const ImportConfigurationImporting = () =>
  import(
    /* webpackChunkName: 'ImportConfigurationImporting' */ '@page/export-import/import-configuration/import-configuration-importing.vue'
  );
const ImportConfigurationHistory = () =>
  import(
    /* webpackChunkName: 'ImportConfigurationHistory' */ '@page/export-import/import-configuration/import-configuration-history.vue'
  );
const ImportConfigurationTarget = () =>
  import(
    /* webpackChunkName: 'ImportConfigurationTarget' */ '@page/export-import/import-configuration/import-configuration-target.vue'
  );
export default [
  {
    path: '/export-import',
    name: 'export-import',
    components: {
      noCache: ImportExport,
    },
    meta: {
      title: '导入/导出',
      navId: 'export-import',
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.VIEW_AUTH,
      },
      route: {
        parent: 'integrated',
      },
      noNavBar: true,
    },
  },
  {
    path: '/export-import/export-configuration',
    name: 'export-configuration',
    components: {
      noCache: ExportConfiguration,
    },
    meta: {
      title: '导出配置',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_EXPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
  {
    path: '/export-import/import-upload',
    name: 'import-configuration-upload',
    components: {
      noCache: ImportConfigurationUpload,
    },
    meta: {
      title: '导入配置',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_IMPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
  {
    path: '/export-import/import-config',
    name: 'import-configuration',
    props: {
      noCache: true,
    },
    components: {
      noCache: ImportConfiguration,
    },
    meta: {
      title: '导入配置',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_IMPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
  {
    path: '/export-import/import-config-detail/:id',
    name: 'import-configuration-importing',
    props: true,
    component: ImportConfigurationImporting,
    meta: {
      title: '导入配置',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_IMPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
  {
    path: '/export-import/config-history',
    name: 'import-configuration-history',
    components: {
      noCache: ImportConfigurationHistory,
    },
    meta: {
      title: '导入历史',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_IMPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
  {
    path: '/export-import/config-target',
    name: 'import-configuration-target',
    props: {
      noCache: true,
    },
    components: {
      noCache: ImportConfigurationTarget,
    },
    meta: {
      title: '统一添加策略目标',
      navId: 'export-import',
      needBack: true,
      authority: {
        map: exOrInAuth,
        page: exOrInAuth.MANAGE_IMPORT_CONFIG,
      },
      route: {
        parent: 'export-import',
      },
      noNavBar: false,
    },
  },
] as RouteConfig[];
