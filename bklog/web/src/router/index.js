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
 * @file router 配置
 * @author  <>
 */

import http from '@/api';
import store from '@/store';
import reportLogStore from '@/store/modules/report-log';
import exception from '@/views/404';
import Vue from 'vue';
import VueRouter from 'vue-router';

Vue.use(VueRouter);

// 解决编程式路由往同一地址跳转时会报错的情况
const originalPush = VueRouter.prototype.push;
const originalReplace = VueRouter.prototype.replace;

// push
VueRouter.prototype.push = function push(location, onResolve, onReject) {
  if (onResolve || onReject)
    return originalPush.call(this, location, onResolve, onReject);
  return originalPush.call(this, location).catch((err) => err);
};

// replace
VueRouter.prototype.replace = function push(location, onResolve, onReject) {
  if (onResolve || onReject)
    return originalReplace.call(this, location, onResolve, onReject);
  return originalReplace.call(this, location).catch((err) => err);
};

const LogCollectionView = {
  name: 'LogCollection',
  template: '<router-view></router-view>',
};
const IndexSetView = {
  name: 'IndexSet',
  template: '<router-view :key="Date.now()"></router-view>',
};
const CustomReportView = {
  name: 'CustomReportView',
  template: '<router-view></router-view>',
};
const ExtractLinkView = {
  name: 'ExtractLinkView',
  template: '<router-view></router-view>',
};
const LogCleanView = {
  name: 'LogCleanView',
  template: '<router-view></router-view>',
};
const LogCleanTempView = {
  name: 'LogCleanTempView',
  template: '<router-view></router-view>',
};
const LogDesensitizeView = {
  name: 'LogDesensitizeView',
  template: '<router-view></router-view>',
};
const DashboardTempView = {
  name: 'DashboardTempView',
  template: '<router-view></router-view>',
};
const retrieve = () =>
  import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');
// const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');

const dashboard = () =>
  import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard');
const playground = () => import('@/views/playground');

// 管理端
const Manage = () => import(/* webpackChunkName: 'manage' */ '@/views/manage');
// ---- 日志接入 ---- 日志采集（采集项）
const CollectionItem = () =>
  import(
    /* webpackChunkName: 'collection-item' */
    '@/views/manage/manage-access/log-collection/collection-item'
  );
// ---- 日志接入 ---- 日志采集（采集项）---- 管理(查看)采集项
const ManageCollection = () =>
  import(
    /* webpackChunkName: 'manage-collection' */
    '@/views/manage/manage-access/log-collection/collection-item/manage-collection'
  );
// ---- 日志接入 ---- 日志采集（采集项）---- 新建、编辑、停用、启用、字段提取
const AccessSteps = () =>
  import(
    /* webpackChunkName: 'access-steps' */
    // '@/views/manage/manage-access/log-collection/collection-item/access-steps'
    '@/components/collection-access'
  );
// ---- 日志接入 ---- 日志采集索引集、数据平台、第三方ES接入 ---- 索引集列表
const IndexList = () =>
  import(
    /* webpackChunkName: 'index-set' */
    '@/views/manage/manage-access/components/index-set/list'
  );
// ---- 日志接入 ---- 日志采集索引集、数据平台、第三方ES接入---- 管理索引集
const ManageIndex = () =>
  import(
    /* webpackChunkName: 'mange-index' */
    '@/views/manage/manage-access/components/index-set/manage'
  );
// ---- 日志接入 ---- 日志采集索引集、数据平台、第三方ES接入 ---- 新建索引集
const CreateIndex = () =>
  import(
    /* webpackChunkName: 'create-index' */
    '@/views/manage/manage-access/components/index-set/create'
  );
// ---- 日志接入 ---- 自定义上报 ---- 自定义上报列表
const CustomReportList = () =>
  import(
    /* webpackChunkName: 'create-index' */
    '@/views/manage/manage-access/custom-report/list'
  );
// ---- 日志接入 ---- 自定义上报 ---- 自定义上报新建/编辑
const CustomReportCreate = () =>
  import(
    /* webpackChunkName: 'create-index' */
    '@/views/manage/manage-access/custom-report/create'
  );
// ---- 日志接入 ---- 自定义上报 ---- 自定义上报详情
const CustomReportDetail = () =>
  import(
    /* webpackChunkName: 'create-index' */
    '@/views/manage/manage-access/custom-report/detail'
  );
// ---- 全链路跟踪 ---- 采集跟踪
const CollectionTrack = () =>
  import(
    /* webpackChunkName: 'collection-track' */
    '@/views/manage/trace-track/collection-track'
  );
// ---- 全链路跟踪 ---- SDK跟踪
const SdkTrack = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/trace-track/sdk-track'
  );
// ---- 日志清洗 ---- 清洗列表
const cleanList = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-clean/clean-manage/list'
  );
// ---- 日志清洗 ---- 新增/编辑 清洗
const cleanCreate = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-clean/clean-manage/create'
  );
// ---- 日志清洗 ---- 新增/编辑 清洗
const cleanTempCreate = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-clean/clean-template/create'
  );
// ---- 模板清洗 ---- 清洗模版
const cleanTemplate = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-clean/clean-template/list'
  );
// ---- 日志归档 ---- 归档仓库
const ArchiveRepository = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-archive/archive-repository/list'
  );
// ---- 日志归档 ---- 归档列表
const ArchiveList = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-archive/archive-list/list'
  );
// ---- 日志归档 ---- 归档回溯
const ArchiveRestore = () =>
  import(
    /* webpackChunkName: 'sdk-track' */
    '@/views/manage/log-archive/archive-restore/list'
  );
// ---- 日志归档 ---- 订阅管理
const ReportManage = () =>
  import(
    /* webpackChunkName: 'report-manage' */
    '@/views/manage/report-management'
  );
// ---- 日志提取 ---- 提取配置
const ExtractPermission = () =>
  import(
    /* webpackChunkName: 'manage-extract-permission' */
    '@/views/manage/manage-extract/manage-extract-permission'
  );
// ---- 日志提取 ---- 提取任务
const extract = () =>
  import(
    /* webpackChunkName: 'logExtract' */
    '@/views/extract/index'
  );
// ---- 日志提取 ---- 提取任务列表
const extractHome = () =>
  import(
    /* webpackChunkName: 'extract-home' */
    '@/views/extract/home'
  );
// ---- 日志提取 ---- 新建/克隆提取任务
const extractCreate = () =>
  import(
    /* webpackChunkName: 'extract-create' */
    '@/views/extract/create'
  );
// ---- 日志提取 ---- 链路管理列表
const ExtractLinkList = () =>
  import(
    /* webpackChunkName: 'extract-link-manage' */
    '@/views/manage/manage-extract/extract-link-manage/extract-link-list'
  );
// ---- 日志提取 ---- 链路管理创建/编辑
const ExtractLinkCreate = () =>
  import(
    /* webpackChunkName: 'extract-link-manage' */
    '@/views/manage/manage-extract/extract-link-manage/extract-link-create'
  );
// ---- ES集群 ---- 集群信息
const ClusterMess = () =>
  import(
    /* webpackChunkName: 'es-cluster-mess' */
    '@/views/manage/es-cluster-status/es-cluster-mess'
  );
// ---- 管理 ---- 采集链路管理
const DataLinkConf = () =>
  import(
    /* webpackChunkName: 'manage-data-link-conf' */
    '@/views/manage/manage-data-link/manage-data-link-conf'
  );
// 外部版授权列表
const externalAuth = () =>
  import(
    /* webpackChunkName: 'externalAuth' */
    '@/views/authorization/authorization-list'
  );
// ---- 脱敏 ---- 脱敏编辑
const MaskingEdit = () =>
  import(
    /* webpackChunkName: 'field-masking-separate' */
    '@/views/manage/field-masking-separate'
  );
// ---- 脱敏 ---- 业务下的脱敏列表
const MaskingList = () =>
  import(
    /* webpackChunkName: 'manage-data-link-conf' */
    '@/views/manage/log-clean/clean-masking/list'
  );

// #if MONITOR_APP === 'apm'
const MonitorApmLog = () =>
  import(
    /* webpackChunkName: 'monitor-apm-log' */
    '@/views/retrieve-v3/monitor/monitor.tsx'
  );
// #endif
// #if MONITOR_APP === 'trace'
const MonitorTraceLog = () =>
  import(
    /* webpackChunkName: 'monitor-trace-log' */
    '@/views/retrieve-v3/monitor/monitor.tsx'
  );
// #endif

const ShareLink = () =>
  import(
    /* webpackChunkName: 'share-link' */
    '@/views/share/index.tsx'
  );

const DataIdUrl = () =>
  import(
    /* webpackChunkName: 'data-id-url' */
    '@/views/data-id-url/index.tsx'
  );

const getRoutes = (spaceId, bkBizId, externalMenu) => {
  const getDefRouteName = () => {
    if (window.IS_EXTERNAL === true || window.IS_EXTERNAL === 'true') {
      if (externalMenu?.includes('retrieve')) {
        return 'retrieve';
      }

      return 'manage';
    }

    return 'retrieve';
  };

  return [
    {
      meta: {
        navId: 'retrieve',
        title: '检索',
      },
      path: '',
      redirect: () => {
        return {
          name: getDefRouteName(),
          query: {
            bizId: bkBizId,
            spaceUid: spaceId,
          },
        };
      },
    },
    {
      component: retrieve,
      meta: {
        navId: 'retrieve',
        title: '检索',
      },
      name: 'retrieve',

      path: '/retrieve/:indexId?',
    },
    {
      children: [
        {
          component: dashboard,
          meta: {
            navId: 'dashboard',
            title: '仪表盘',
          },
          name: 'default-dashboard',
          path: 'default-dashboard',
        },
        {
          component: dashboard,
          meta: {
            backName: 'default-dashboard',
            navId: 'dashboard',
            needBack: true,
            title: '仪表盘',
          },
          name: 'create-dashboard',
          path: 'create-dashboard',
        },
        {
          component: dashboard,
          meta: {
            backName: 'default-dashboard',
            navId: 'dashboard',
            needBack: true,
            title: '仪表盘',
          },
          name: 'import-dashboard',
          path: 'import-dashboard',
        },
        {
          component: dashboard,
          meta: {
            backName: 'default-dashboard',
            navId: 'dashboard',
            needBack: true,
            title: '仪表盘',
          },
          name: 'create-folder',
          path: 'create-folder',
        },
      ],
      component: DashboardTempView,
      name: 'dashboard',
      path: '/dashboard',
      redirect: '/dashboard/default-dashboard',
    },
    {
      children: [
        {
          path: 'collect', // 日志采集 支持监控跳转兼容旧版本管理端
          redirect: '/manage/log-collection/collection-item',
        },
        {
          children: [
            {
              component: CollectionItem,
              meta: {
                navId: 'log-collection',
                title: '日志采集',
              },
              name: 'collection-item', // 采集项列表
              path: 'collection-item',
            },
            {
              component: ManageCollection,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'manage-collection', // 管理(查看)采集项
              path: 'collection-item/manage/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectAdd',
              // =================== 采集项新建、编辑等操作，尽量复用旧代码
              path: 'collection-item/add',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectEdit',
              path: 'collection-item/edit/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectField',
              path: 'collection-item/field/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectStorage',
              path: 'collection-item/storage/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectMasking', // 脱敏
              path: 'collection-item/masking/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectStart',
              path: 'collection-item/start/:collectorId',
            },
            {
              component: AccessSteps,
              meta: {
                backName: 'collection-item',
                navId: 'log-collection',
                needBack: true,
                title: '日志采集',
              },
              name: 'collectStop',
              path: 'collection-item/stop/:collectorId',
            },
            {
              children: [
                {
                  component: IndexList,
                  meta: {
                    navId: 'log-collection',
                    title: '日志采集',
                  },
                  name: 'log-index-set-list',
                  path: 'list',
                },
                {
                  component: ManageIndex,
                  meta: {
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                    needBack: true,
                    title: '日志采集',
                  },
                  name: 'log-index-set-manage',
                  path: 'manage/:indexSetId',
                },
                {
                  component: CreateIndex,
                  meta: {
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                    needBack: true,
                    title: '日志采集',
                  },
                  name: 'log-index-set-create',
                  path: 'create',
                },
                {
                  component: CreateIndex,
                  meta: {
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                    needBack: true,
                    title: '日志采集',
                  },
                  name: 'log-index-set-edit',
                  path: 'edit/:indexSetId',
                },
                {
                  component: MaskingEdit,
                  meta: {
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                    needBack: true,
                    title: '日志采集',
                  },
                  name: 'log-index-set-masking',
                  path: 'masking/:indexSetId',
                },
              ],
              component: IndexSetView,
              name: 'log-index-set',
              // ===================
              path: 'log-index-set', // 索引集
              redirect: '/manage/log-collection/log-index-set/list',
            },
          ],
          component: LogCollectionView,
          name: 'log-collection', // 日志接入 - 日志采集
          path: 'log-collection',
          redirect: '/manage/log-collection/collection-item',
        },
        {
          children: [
            {
              component: IndexList,
              meta: {
                navId: 'bk-data-collection',
                title: '计算平台',
              },
              name: 'bkdata-index-set-list',
              path: 'list',
            },
            {
              component: ManageIndex,
              meta: {
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
                needBack: true,
                title: '计算平台',
              },
              name: 'bkdata-index-set-manage',
              path: 'manage/:indexSetId',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
                needBack: true,
                title: '计算平台',
              },
              name: 'bkdata-index-set-create',
              path: 'create',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
                needBack: true,
                title: '计算平台',
              },
              name: 'bkdata-index-set-edit',
              path: 'edit/:indexSetId',
            },
            {
              component: MaskingEdit,
              meta: {
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
                needBack: true,
                title: '计算平台',
              },
              name: 'bkdata-index-set-masking',
              path: 'masking/:indexSetId',
            },
          ],
          component: IndexSetView,
          name: 'bk-data-collection',
          path: 'bk-data-collection', // 日志接入 - 数据平台
          redirect: '/manage/bk-data-collection/list',
        },
        {
          children: [
            {
              component: IndexList,
              meta: {
                navId: 'es-collection',
                title: '第三方ES',
              },
              name: 'es-index-set-list',
              path: 'list',
            },
            {
              component: ManageIndex,
              meta: {
                backName: 'es-index-set-list',
                navId: 'es-collection',
                needBack: true,
                title: '第三方ES',
              },
              name: 'es-index-set-manage',
              path: 'manage/:indexSetId',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'es-index-set-list',
                navId: 'es-collection',
                needBack: true,
                title: '第三方ES',
              },
              name: 'es-index-set-create',
              path: 'create',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'es-index-set-list',
                navId: 'es-collection',
                needBack: true,
                title: '第三方ES',
              },
              name: 'es-index-set-edit',
              path: 'edit/:indexSetId',
            },
            {
              component: MaskingEdit,
              meta: {
                backName: 'es-index-set-list',
                navId: 'es-collection',
                needBack: true,
                title: '第三方ES',
              },
              name: 'es-index-set-masking',
              path: 'masking/:indexSetId',
            },
          ],
          component: IndexSetView,
          name: 'es-collection',
          path: 'es-collection', // 日志接入 - 第三方ES接入
          redirect: '/manage/es-collection/list',
        },
        {
          children: [
            {
              component: CustomReportList,
              meta: {
                navId: 'custom-report',
                title: '自定义上报',
              },
              name: 'custom-report-list', // 日志接入 - 自定义上报列表
              path: 'list',
            },
            {
              component: CustomReportCreate,
              meta: {
                backName: 'custom-report-list',
                navId: 'custom-report',
                needBack: true,
                title: '自定义上报',
              },
              name: 'custom-report-create', // 日志接入 - 自定义上报新建
              path: 'create',
            },
            {
              component: CustomReportCreate,
              meta: {
                backName: 'custom-report-list',
                navId: 'custom-report',
                needBack: true,
                title: '自定义上报',
              },
              name: 'custom-report-edit', // 日志接入 - 自定义上报编辑
              path: 'edit/:collectorId',
            },
            {
              component: CustomReportDetail,
              meta: {
                backName: 'custom-report-list',
                navId: 'custom-report',
                needBack: true,
                title: '自定义上报',
              },
              name: 'custom-report-detail', // 日志接入 - 自定义上报详情
              path: 'detail/:collectorId',
            },
            {
              component: MaskingEdit,
              meta: {
                backName: 'custom-report-list',
                navId: 'custom-report',
                needBack: true,
                title: '自定义上报',
              },
              name: 'custom-report-masking', // 日志接入 - 自定义上报详情
              path: 'masking/:indexSetId',
            },
          ],
          component: CustomReportView,
          name: 'custom-report', // 日志接入 - 自定义上报
          path: 'custom-report',
          redirect: '/manage/custom-report/list',
        },
        {
          component: CollectionTrack,
          meta: {
            navId: 'collection-track',
            title: '采集接入',
          },
          name: 'collection-track', // 全链路追踪 - 采集接入
          path: 'collection-track',
        },
        {
          children: [
            {
              component: IndexList,
              meta: {
                navId: 'bk-data-track',
                title: '数据平台接入',
              },
              name: 'bkdata-track-list',
              path: 'list',
            },
            {
              component: ManageIndex,
              meta: {
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
                needBack: true,
                title: '数据平台接入',
              },
              name: 'bkdata-track-manage',
              path: 'manage/:indexSetId',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
                needBack: true,
                title: '数据平台接入',
              },
              name: 'bkdata-track-create',
              path: 'create',
            },
            {
              component: CreateIndex,
              meta: {
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
                needBack: true,
                title: '数据平台接入',
              },
              name: 'bkdata-track-edit',
              path: 'edit/:indexSetId',
            },
          ],
          component: IndexSetView,
          name: 'bk-data-track',
          path: 'bk-data-track', // 全链路追踪 - 数据平台接入
          redirect: '/manage/bk-data-track/list',
        },
        {
          component: SdkTrack,
          meta: {
            navId: 'sdk-track',
            title: 'SDK接入',
          },
          name: 'sdk-track', // 全链路追踪 - SDK接入
          path: 'sdk-track',
        },
        {
          children: [
            {
              component: cleanList,
              meta: {
                navId: 'clean-list',
                title: '日志清洗',
              },
              name: 'log-clean-list', // 日志清洗 - 清洗列表
              path: 'list',
            },
            {
              component: cleanCreate,
              meta: {
                backName: 'log-clean-list',
                navId: 'clean-list',
                needBack: true,
                title: '日志清洗',
              },
              name: 'clean-create', // 日志清洗 - 新建清洗
              path: 'create',
            },
            {
              component: cleanCreate,
              meta: {
                backName: 'log-clean-list',
                navId: 'clean-list',
                needBack: true,
                title: '日志清洗',
              },
              name: 'clean-edit', // 日志清洗 - 编辑清洗
              path: 'edit/:collectorId',
            },
          ],
          component: LogCleanView,
          name: 'clean-list', // 日志清洗
          path: 'clean-list',
          redirect: '/manage/clean-list/list',
        },
        {
          children: [
            {
              component: cleanTemplate,
              meta: {
                navId: 'clean-templates',
                title: '日志清洗',
              },
              name: 'log-clean-templates', // 日志清洗 - 清洗模板
              path: 'list',
            },
            {
              component: cleanTempCreate,
              meta: {
                backName: 'log-clean-templates',
                navId: 'clean-templates',
                needBack: true,
                title: '日志清洗',
              },
              name: 'clean-template-create', // 日志清洗 - 新增模板
              path: 'create',
            },
            {
              component: cleanTempCreate,
              meta: {
                backName: 'log-clean-templates',
                navId: 'clean-templates',
                needBack: true,
                title: '日志清洗',
              },
              name: 'clean-template-edit', // 日志清洗 - 编辑模板
              path: 'edit/:templateId',
            },
          ],
          component: LogCleanTempView,
          name: 'clean-templates', // 日志清洗模板
          path: 'clean-templates',
          redirect: '/manage/clean-templates/list',
        },
        {
          children: [
            {
              component: MaskingList,
              meta: {
                navId: 'log-desensitize',
                title: '日志清洗',
              },
              name: 'log-desensitize-list',
              path: 'list',
            },
          ],
          component: LogDesensitizeView,
          name: 'log-desensitize', // 日志脱敏
          path: 'log-desensitize',
          redirect: '/manage/log-desensitize/list',
        },
        {
          component: ArchiveRepository,
          meta: {
            navId: 'archive-repository',
            title: '日志归档',
          },
          name: 'archive-repository', // 日志归档 - 归档仓库
          path: 'archive-repository',
        },
        {
          component: ArchiveList,
          meta: {
            navId: 'archive-list',
            title: '日志归档',
          },
          name: 'archive-list', // 日志归档 - 归档列表
          path: 'archive-list',
        },
        {
          component: ArchiveRestore,
          meta: {
            navId: 'archive-restore',
            title: '日志归档',
          },
          name: 'archive-restore', // 日志归档 - 归档回溯
          path: 'archive-restore',
        },
        {
          component: ExtractPermission,
          meta: {
            navId: 'manage-log-extract',
            title: '日志提取',
          },
          name: 'manage-log-extract', // 日志提取 - 提取配置
          path: 'manage-log-extract',
        },
        {
          children: [
            {
              component: extractHome,
              meta: {
                navId: 'log-extract-task',
                title: '日志提取',
              },
              name: 'extract-home', // 日志提取 - 提取任务
              path: '',
            },
            {
              component: extractCreate,
              meta: {
                backName: 'log-extract-task',
                navId: 'log-extract-task',
                needBack: true,
                title: '日志提取',
              },
              name: 'extract-create', // 日志提取 - 新建提取任务
              path: 'extract-create',
            },
            {
              component: extractCreate,
              meta: {
                backName: 'log-extract-task',
                navId: 'log-extract-task',
                needBack: true,
                title: '日志提取',
              },
              name: 'extract-clone', // 日志提取 - 克隆提取任务
              path: 'extract-clone',
            },
          ],
          component: extract,
          meta: {
            navId: 'log-extract-task',
            title: '日志提取',
          },
          name: 'log-extract-task', // 日志提取 - 提取任务
          path: 'log-extract-task',
          redirect: '/manage/log-extract-task',
        },
        {
          children: [
            {
              component: ExtractLinkList,
              meta: {
                navId: 'extract-link-manage',
                title: '日志提取',
              },
              name: 'extract-link-list',
              path: 'list',
            },
            {
              component: ExtractLinkCreate,
              meta: {
                backName: 'extract-link-list',
                navId: 'extract-link-manage',
                needBack: true,
                title: '日志提取',
              },
              name: 'extract-link-edit',
              path: 'edit/:linkId',
            },
            {
              component: ExtractLinkCreate,
              meta: {
                backName: 'extract-link-list',
                navId: 'extract-link-manage',
                needBack: true,
                title: '日志提取',
              },
              name: 'extract-link-create',
              path: 'create',
            },
          ],
          component: ExtractLinkView,
          name: 'extract-link-manage', // 日志提取 - 链路管理
          path: 'extract-link-manage',
          redirect: '/manage/extract-link-manage/list',
        },
        {
          component: ClusterMess,
          meta: {
            navId: 'es-cluster-manage',
            title: 'ES集群',
          },
          name: 'es-cluster-manage', // ES集群 - 集群信息
          path: 'es-cluster-manage',
        },
        {
          component: DataLinkConf,
          meta: {
            navId: 'manage-data-link-conf',
            title: '设置',
          },
          name: 'manage-data-link-conf', // 管理 - 采集链路管理
          path: 'manage-data-link-conf',
        },
        {
          component: ReportManage,
          meta: {
            navId: 'report-manage',
            title: '订阅管理',
          },
          name: 'report-manage', // 订阅 - 订阅管理
          path: 'report-manage',
        },
      ],
      component: Manage,
      name: 'manage',
      path: '/manage',
      redirect: (to) => {
        if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL)) {
          return {
            path: '/manage/log-extract-task',
            query: {
              bizId: to.query.bizId,
              spaceUid: to.query.spaceUid,
            },
          };
        }
        return {
          path: '/manage/log-collection/collection-item',
          query: {
            bizId: to.query.bizId,
            spaceUid: to.query.spaceUid,
          },
        };
      },
    },
    {
      component: externalAuth,
      meta: {
        navId: 'external-auth',
        title: '授权列表',
      },
      name: 'externalAuth',
      path: '/external-auth/:activeNav?',
    },
    {
      component: playground,
      name: 'playground',
      path: '/playground',
    },
    {
      component: ShareLink,
      meta: {
        navId: 'share',
        title: '分享链接',
      },
      name: 'share',
      path: '/share/:linkId?',
    },
    {
      component: DataIdUrl,
      meta: {
        navId: 'data_id',
        title: '根据 bk_data_id 获取采集项和索引集信息',
      },
      name: 'data_id',
      path: '/data_id/:id?',
    },
    // #if MONITOR_APP === 'apm'
    {
      component: MonitorApmLog,
      meta: {
        navId: 'monitor-apm-log',
        title: 'APM检索-日志',
      },
      name: 'monitor-apm-log',
      path: '/monitor-apm-log/:indexId?',
    },
    // #endif
    // #if MONITOR_APP === 'trace'
    {
      component: MonitorTraceLog,
      meta: {
        navId: 'monitor-trace-log',
        title: 'Trace检索-日志',
      },
      name: 'monitor-trace-log',
      path: '/monitor-trace-log/:indexId?',
    },
    // #endif
    {
      component: exception,
      meta: {
        navId: 'exception',
        title: '无权限页面',
      },
      name: 'exception',
      path: '*',
    },
  ];
};

/**
 * @param id 路由id
 * @returns 路由配置
 */
export function getRouteConfigById(id, space_uid, bk_biz_id, externalMenu) {
  const flatConfig = getRoutes(space_uid, bk_biz_id, externalMenu).flatMap(
    (config) => {
      if (config.children?.length) {
        return config.children.flatMap((set) => {
          if (set.children?.length) {
            return set.children;
          }
          return set;
        });
      }
      return config;
    }
  );

  return flatConfig.find((item) => item.meta?.navId === id);
}

export default (spaceId, bkBizId, externalMenu) => {
  const routes = getRoutes(spaceId, bkBizId, externalMenu);
  const router = new VueRouter({
    routes,
  });

  const cancelRequest = async () => {
    const allRequest = http.queue.get();
    const requestQueue = allRequest.filter(
      (request) => request.cancelWhenRouteChange
    );
    await http.cancel(requestQueue.map((request) => request.requestId));
  };

  router.beforeEach(async (to, from, next) => {
    await cancelRequest();
    if (to.name === 'retrieve') {
      window.parent.postMessage(
        {
          _LOG_TO_MONITOR_: true,
          _MONITOR_URL_: window.MONITOR_URL,
          _MONITOR_URL_PARAMS_: to.params,
          _MONITOR_URL_QUERY_: to.query,
        },
        '*'
        // window.MONITOR_URL,
      );
    }
    if (
      window.IS_EXTERNAL &&
      JSON.parse(window.IS_EXTERNAL) &&
      !['retrieve', 'extract-home', 'extract-create', 'extract-clone'].includes(
        to.name
      )
    ) {
      // 非外部版路由重定向
      const routeName = store.state.externalMenu.includes('retrieve')
        ? 'retrieve'
        : 'manage';
      next({ name: routeName });
    } else {
      next();
    }
  });

  let stringifyExternalMenu = '[]';
  try {
    stringifyExternalMenu = JSON.stringify(externalMenu);
  } catch (e) {
    console.warn('externalMenu JSON.stringify error', e);
  }

  router.afterEach((to) => {
    if (to.name === 'exception') return;
    reportLogStore.reportRouteLog({
      external_menu: stringifyExternalMenu,
      nav_id: to.meta.navId,
      nav_name: to.meta?.title ?? undefined,
      route_id: to.name,
    });
  });

  return router;
};
