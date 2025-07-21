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

import Vue from 'vue';
import VueRouter from 'vue-router';

import reportLogStore from '@/store/modules/report-log';
import exception from '@/views/404';

import http from '@/api';
import store from '@/store';

Vue.use(VueRouter);

// 解决编程式路由往同一地址跳转时会报错的情况
const originalPush = VueRouter.prototype.push;
const originalReplace = VueRouter.prototype.replace;

// push
VueRouter.prototype.push = function push(location, onResolve, onReject) {
  if (onResolve || onReject) return originalPush.call(this, location, onResolve, onReject);
  return originalPush.call(this, location).catch(err => err);
};

// replace
VueRouter.prototype.replace = function push(location, onResolve, onReject) {
  if (onResolve || onReject) return originalReplace.call(this, location, onResolve, onReject);
  return originalReplace.call(this, location).catch(err => err);
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
const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');
// const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');

const dashboard = () => import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard');
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
      path: '',
      redirect: () => {
        return {
          name: getDefRouteName(),
          query: {
            spaceUid: spaceId,
            bizId: bkBizId,
          },
        };
      },
      meta: {
        title: '检索',
        navId: 'retrieve',
      },
    },
    {
      path: '/retrieve/:indexId?',
      name: 'retrieve',
      component: retrieve,

      meta: {
        title: '检索',
        navId: 'retrieve',
      },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardTempView,
      redirect: '/dashboard/default-dashboard',
      children: [
        {
          path: 'default-dashboard',
          name: 'default-dashboard',
          component: dashboard,
          meta: {
            title: '仪表盘',
            navId: 'dashboard',
          },
        },
        {
          path: 'create-dashboard',
          name: 'create-dashboard',
          meta: {
            title: '仪表盘',
            needBack: true,
            backName: 'default-dashboard',
            navId: 'dashboard',
          },
          component: dashboard,
        },
        {
          path: 'import-dashboard',
          name: 'import-dashboard',
          meta: {
            title: '仪表盘',
            needBack: true,
            backName: 'default-dashboard',
            navId: 'dashboard',
          },
          component: dashboard,
        },
        {
          path: 'create-folder',
          name: 'create-folder',
          meta: {
            title: '仪表盘',
            needBack: true,
            backName: 'default-dashboard',
            navId: 'dashboard',
          },
          component: dashboard,
        },
      ],
    },
    {
      path: '/manage',
      name: 'manage',
      component: Manage,
      redirect: to => {
        if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL)) {
          return {
            path: '/manage/log-extract-task',
            query: {
              spaceUid: to.query.spaceUid,
              bizId: to.query.bizId,
            },
          };
        }
        return {
          path: '/manage/log-collection/collection-item',
          query: {
            spaceUid: to.query.spaceUid,
            bizId: to.query.bizId,
          },
        };
      },
      children: [
        {
          path: 'collect', // 日志采集 支持监控跳转兼容旧版本管理端
          redirect: '/manage/log-collection/collection-item',
        },
        {
          path: 'log-collection',
          name: 'log-collection', // 日志接入 - 日志采集
          component: LogCollectionView,
          redirect: '/manage/log-collection/collection-item',
          children: [
            {
              path: 'collection-item',
              name: 'collection-item', // 采集项列表
              component: CollectionItem,
              meta: {
                title: '日志采集',
                navId: 'log-collection',
              },
            },
            {
              path: 'collection-item/manage/:collectorId',
              name: 'manage-collection', // 管理(查看)采集项
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: ManageCollection,
            },
            {
              // =================== 采集项新建、编辑等操作，尽量复用旧代码
              path: 'collection-item/add',
              name: 'collectAdd',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/edit/:collectorId',
              name: 'collectEdit',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/field/:collectorId',
              name: 'collectField',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/storage/:collectorId',
              name: 'collectStorage',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/masking/:collectorId',
              name: 'collectMasking', // 脱敏
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/start/:collectorId',
              name: 'collectStart',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              path: 'collection-item/stop/:collectorId',
              name: 'collectStop',
              meta: {
                title: '日志采集',
                needBack: true,
                backName: 'collection-item',
                navId: 'log-collection',
              },
              component: AccessSteps,
            },
            {
              // ===================
              path: 'log-index-set', // 索引集
              name: 'log-index-set',
              component: IndexSetView,
              redirect: '/manage/log-collection/log-index-set/list',
              children: [
                {
                  path: 'list',
                  name: 'log-index-set-list',
                  component: IndexList,
                  meta: {
                    title: '日志采集',
                    navId: 'log-collection',
                  },
                },
                {
                  path: 'manage/:indexSetId',
                  name: 'log-index-set-manage',
                  meta: {
                    title: '日志采集',
                    needBack: true,
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                  },
                  component: ManageIndex,
                },
                {
                  path: 'create',
                  name: 'log-index-set-create',
                  meta: {
                    title: '日志采集',
                    needBack: true,
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                  },
                  component: CreateIndex,
                },
                {
                  path: 'edit/:indexSetId',
                  name: 'log-index-set-edit',
                  meta: {
                    title: '日志采集',
                    needBack: true,
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                  },
                  component: CreateIndex,
                },
                {
                  path: 'masking/:indexSetId',
                  name: 'log-index-set-masking',
                  meta: {
                    title: '日志采集',
                    needBack: true,
                    backName: 'log-index-set-list',
                    navId: 'log-collection',
                  },
                  component: MaskingEdit,
                },
              ],
            },
          ],
        },
        {
          path: 'bk-data-collection', // 日志接入 - 数据平台
          name: 'bk-data-collection',
          component: IndexSetView,
          redirect: '/manage/bk-data-collection/list',
          children: [
            {
              path: 'list',
              name: 'bkdata-index-set-list',
              component: IndexList,
              meta: {
                title: '计算平台',
                navId: 'bk-data-collection',
              },
            },
            {
              path: 'manage/:indexSetId',
              name: 'bkdata-index-set-manage',
              meta: {
                title: '计算平台',
                needBack: true,
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
              },
              component: ManageIndex,
            },
            {
              path: 'create',
              name: 'bkdata-index-set-create',
              meta: {
                title: '计算平台',
                needBack: true,
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
              },
              component: CreateIndex,
            },
            {
              path: 'edit/:indexSetId',
              name: 'bkdata-index-set-edit',
              meta: {
                title: '计算平台',
                needBack: true,
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
              },
              component: CreateIndex,
            },
            {
              path: 'masking/:indexSetId',
              name: 'bkdata-index-set-masking',
              meta: {
                title: '计算平台',
                needBack: true,
                backName: 'bkdata-index-set-list',
                navId: 'bk-data-collection',
              },
              component: MaskingEdit,
            },
          ],
        },
        {
          path: 'es-collection', // 日志接入 - 第三方ES接入
          name: 'es-collection',
          component: IndexSetView,
          redirect: '/manage/es-collection/list',
          children: [
            {
              path: 'list',
              name: 'es-index-set-list',
              component: IndexList,
              meta: {
                title: '第三方ES',
                navId: 'es-collection',
              },
            },
            {
              path: 'manage/:indexSetId',
              name: 'es-index-set-manage',
              meta: {
                title: '第三方ES',
                needBack: true,
                backName: 'es-index-set-list',
                navId: 'es-collection',
              },
              component: ManageIndex,
            },
            {
              path: 'create',
              name: 'es-index-set-create',
              meta: {
                title: '第三方ES',
                needBack: true,
                backName: 'es-index-set-list',
                navId: 'es-collection',
              },
              component: CreateIndex,
            },
            {
              path: 'edit/:indexSetId',
              name: 'es-index-set-edit',
              meta: {
                title: '第三方ES',
                needBack: true,
                backName: 'es-index-set-list',
                navId: 'es-collection',
              },
              component: CreateIndex,
            },
            {
              path: 'masking/:indexSetId',
              name: 'es-index-set-masking',
              meta: {
                title: '第三方ES',
                needBack: true,
                backName: 'es-index-set-list',
                navId: 'es-collection',
              },
              component: MaskingEdit,
            },
          ],
        },
        {
          path: 'custom-report',
          name: 'custom-report', // 日志接入 - 自定义上报
          component: CustomReportView,
          redirect: '/manage/custom-report/list',
          children: [
            {
              path: 'list',
              name: 'custom-report-list', // 日志接入 - 自定义上报列表
              component: CustomReportList,
              meta: {
                title: '自定义上报',
                navId: 'custom-report',
              },
            },
            {
              path: 'create',
              name: 'custom-report-create', // 日志接入 - 自定义上报新建
              meta: {
                title: '自定义上报',
                needBack: true,
                backName: 'custom-report-list',
                navId: 'custom-report',
              },
              component: CustomReportCreate,
            },
            {
              path: 'edit/:collectorId',
              name: 'custom-report-edit', // 日志接入 - 自定义上报编辑
              meta: {
                title: '自定义上报',
                needBack: true,
                backName: 'custom-report-list',
                navId: 'custom-report',
              },
              component: CustomReportCreate,
            },
            {
              path: 'detail/:collectorId',
              name: 'custom-report-detail', // 日志接入 - 自定义上报详情
              meta: {
                title: '自定义上报',
                needBack: true,
                backName: 'custom-report-list',
                navId: 'custom-report',
              },
              component: CustomReportDetail,
            },
            {
              path: 'masking/:indexSetId',
              name: 'custom-report-masking', // 日志接入 - 自定义上报详情
              meta: {
                title: '自定义上报',
                needBack: true,
                backName: 'custom-report-list',
                navId: 'custom-report',
              },
              component: MaskingEdit,
            },
          ],
        },
        {
          path: 'collection-track',
          name: 'collection-track', // 全链路追踪 - 采集接入
          component: CollectionTrack,
          meta: {
            title: '采集接入',
            navId: 'collection-track',
          },
        },
        {
          path: 'bk-data-track', // 全链路追踪 - 数据平台接入
          name: 'bk-data-track',
          component: IndexSetView,
          redirect: '/manage/bk-data-track/list',
          children: [
            {
              path: 'list',
              name: 'bkdata-track-list',
              component: IndexList,
              meta: {
                title: '数据平台接入',
                navId: 'bk-data-track',
              },
            },
            {
              path: 'manage/:indexSetId',
              name: 'bkdata-track-manage',
              meta: {
                title: '数据平台接入',
                needBack: true,
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
              },
              component: ManageIndex,
            },
            {
              path: 'create',
              name: 'bkdata-track-create',
              meta: {
                title: '数据平台接入',
                needBack: true,
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
              },
              component: CreateIndex,
            },
            {
              path: 'edit/:indexSetId',
              name: 'bkdata-track-edit',
              meta: {
                title: '数据平台接入',
                needBack: true,
                backName: 'bkdata-track-list',
                navId: 'bk-data-track',
              },
              component: CreateIndex,
            },
          ],
        },
        {
          path: 'sdk-track',
          name: 'sdk-track', // 全链路追踪 - SDK接入
          component: SdkTrack,
          meta: {
            title: 'SDK接入',
            navId: 'sdk-track',
          },
        },
        {
          path: 'clean-list',
          name: 'clean-list', // 日志清洗
          component: LogCleanView,
          redirect: '/manage/clean-list/list',
          children: [
            {
              path: 'list',
              name: 'log-clean-list', // 日志清洗 - 清洗列表
              component: cleanList,
              meta: {
                title: '日志清洗',
                navId: 'clean-list',
              },
            },
            {
              path: 'create',
              name: 'clean-create', // 日志清洗 - 新建清洗
              meta: {
                title: '日志清洗',
                needBack: true,
                backName: 'log-clean-list',
                navId: 'clean-list',
              },
              component: cleanCreate,
            },
            {
              path: 'edit/:collectorId',
              name: 'clean-edit', // 日志清洗 - 编辑清洗
              meta: {
                title: '日志清洗',
                needBack: true,
                backName: 'log-clean-list',
                navId: 'clean-list',
              },
              component: cleanCreate,
            },
          ],
        },
        {
          path: 'clean-templates',
          name: 'clean-templates', // 日志清洗模板
          component: LogCleanTempView,
          redirect: '/manage/clean-templates/list',
          children: [
            {
              path: 'list',
              name: 'log-clean-templates', // 日志清洗 - 清洗模板
              component: cleanTemplate,
              meta: {
                title: '日志清洗',
                navId: 'clean-templates',
              },
            },
            {
              path: 'create',
              name: 'clean-template-create', // 日志清洗 - 新增模板
              meta: {
                title: '日志清洗',
                needBack: true,
                backName: 'log-clean-templates',
                navId: 'clean-templates',
              },
              component: cleanTempCreate,
            },
            {
              path: 'edit/:templateId',
              name: 'clean-template-edit', // 日志清洗 - 编辑模板
              meta: {
                title: '日志清洗',
                needBack: true,
                backName: 'log-clean-templates',
                navId: 'clean-templates',
              },
              component: cleanTempCreate,
            },
          ],
        },
        {
          path: 'log-desensitize',
          name: 'log-desensitize', // 日志脱敏
          component: LogDesensitizeView,
          redirect: '/manage/log-desensitize/list',
          children: [
            {
              path: 'list',
              name: 'log-desensitize-list',
              component: MaskingList,
              meta: {
                title: '日志清洗',
                navId: 'log-desensitize',
              },
            },
          ],
        },
        {
          path: 'archive-repository',
          name: 'archive-repository', // 日志归档 - 归档仓库
          component: ArchiveRepository,
          meta: {
            title: '日志归档',
            navId: 'archive-repository',
          },
        },
        {
          path: 'archive-list',
          name: 'archive-list', // 日志归档 - 归档列表
          component: ArchiveList,
          meta: {
            title: '日志归档',
            navId: 'archive-list',
          },
        },
        {
          path: 'archive-restore',
          name: 'archive-restore', // 日志归档 - 归档回溯
          component: ArchiveRestore,
          meta: {
            title: '日志归档',
            navId: 'archive-restore',
          },
        },
        {
          path: 'manage-log-extract',
          name: 'manage-log-extract', // 日志提取 - 提取配置
          component: ExtractPermission,
          meta: {
            title: '日志提取',
            navId: 'manage-log-extract',
          },
        },
        {
          path: 'log-extract-task',
          name: 'log-extract-task', // 日志提取 - 提取任务
          component: extract,
          redirect: '/manage/log-extract-task',
          meta: {
            title: '日志提取',
            navId: 'log-extract-task',
          },
          children: [
            {
              path: '',
              name: 'extract-home', // 日志提取 - 提取任务
              component: extractHome,
              meta: {
                title: '日志提取',
                navId: 'log-extract-task',
              },
            },
            {
              path: 'extract-create',
              name: 'extract-create', // 日志提取 - 新建提取任务
              meta: {
                title: '日志提取',
                needBack: true,
                backName: 'log-extract-task',
                navId: 'log-extract-task',
              },
              component: extractCreate,
            },
            {
              path: 'extract-clone',
              name: 'extract-clone', // 日志提取 - 克隆提取任务
              meta: {
                title: '日志提取',
                needBack: true,
                backName: 'log-extract-task',
                navId: 'log-extract-task',
              },
              component: extractCreate,
            },
          ],
        },
        {
          path: 'extract-link-manage',
          name: 'extract-link-manage', // 日志提取 - 链路管理
          component: ExtractLinkView,
          redirect: '/manage/extract-link-manage/list',
          children: [
            {
              path: 'list',
              name: 'extract-link-list',
              component: ExtractLinkList,
              meta: {
                title: '日志提取',
                navId: 'extract-link-manage',
              },
            },
            {
              path: 'edit/:linkId',
              name: 'extract-link-edit',
              meta: {
                title: '日志提取',
                needBack: true,
                backName: 'extract-link-list',
                navId: 'extract-link-manage',
              },
              component: ExtractLinkCreate,
            },
            {
              path: 'create',
              name: 'extract-link-create',
              meta: {
                title: '日志提取',
                needBack: true,
                backName: 'extract-link-list',
                navId: 'extract-link-manage',
              },
              component: ExtractLinkCreate,
            },
          ],
        },
        {
          path: 'es-cluster-manage',
          name: 'es-cluster-manage', // ES集群 - 集群信息
          component: ClusterMess,
          meta: {
            title: 'ES集群',
            navId: 'es-cluster-manage',
          },
        },
        {
          path: 'manage-data-link-conf',
          name: 'manage-data-link-conf', // 管理 - 采集链路管理
          component: DataLinkConf,
          meta: {
            title: '设置',
            navId: 'manage-data-link-conf',
          },
        },
        {
          path: 'report-manage',
          name: 'report-manage', // 订阅 - 订阅管理
          component: ReportManage,
          meta: {
            title: '订阅管理',
            navId: 'report-manage',
          },
        },
      ],
    },
    {
      path: '/external-auth/:activeNav?',
      name: 'externalAuth',
      component: externalAuth,
      meta: {
        title: '授权列表',
        navId: 'external-auth',
      },
    },
    {
      path: '/playground',
      name: 'playground',
      component: playground,
    },
    {
      path: '/share/:linkId?',
      name: 'share',
      component: ShareLink,
      meta: {
        title: '分享链接',
        navId: 'share',
      },
    },
    {
      path: '/data_id/:id?',
      name: 'data_id',
      component: DataIdUrl,
      meta: {
        title: '根据 bk_data_id 获取采集项和索引集信息',
        navId: 'data_id',
      },
    },
    // #if MONITOR_APP === 'apm'
    {
      path: '/monitor-apm-log/:indexId?',
      name: 'monitor-apm-log',
      component: MonitorApmLog,
      meta: {
        title: 'APM检索-日志',
        navId: 'monitor-apm-log',
      },
    },
    // #endif
    // #if MONITOR_APP === 'trace'
    {
      path: '/monitor-trace-log/:indexId?',
      name: 'monitor-trace-log',
      component: MonitorTraceLog,
      meta: {
        title: 'Trace检索-日志',
        navId: 'monitor-trace-log',
      },
    },
    // #endif
    {
      path: '*',
      name: 'exception',
      component: exception,
      meta: {
        navId: 'exception',
        title: '无权限页面',
      },
    },
  ];
};

/**
 * @param id 路由id
 * @returns 路由配置
 */
export function getRouteConfigById(id, space_uid, bk_biz_id, externalMenu) {
  const flatConfig = getRoutes(space_uid, bk_biz_id, externalMenu).flatMap(config => {
    if (config.children?.length) {
      return config.children.flatMap(set => {
        if (set.children?.length) {
          return set.children;
        }
        return set;
      });
    }
    return config;
  });

  return flatConfig.find(item => item.meta?.navId === id);
}

export default (spaceId, bkBizId, externalMenu) => {
  const routes = getRoutes(spaceId, bkBizId, externalMenu);
  const router = new VueRouter({
    routes,
  });

  const cancelRequest = async () => {
    const allRequest = http.queue.get();
    const requestQueue = allRequest.filter(request => request.cancelWhenRouteChange);
    await http.cancel(requestQueue.map(request => request.requestId));
  };

  router.beforeEach(async (to, from, next) => {
    await cancelRequest();
    if (to.name === 'retrieve') {
      window.parent.postMessage(
        {
          _MONITOR_URL_PARAMS_: to.params,
          _MONITOR_URL_QUERY_: to.query,
          _LOG_TO_MONITOR_: true,
          _MONITOR_URL_: window.MONITOR_URL,
        },
        '*'
        // window.MONITOR_URL,
      );
    }
    if (
      window.IS_EXTERNAL &&
      JSON.parse(window.IS_EXTERNAL) &&
      !['retrieve', 'extract-home', 'extract-create', 'extract-clone'].includes(to.name)
    ) {
      // 非外部版路由重定向
      const routeName = store.state.externalMenu.includes('retrieve') ? 'retrieve' : 'manage';
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

  router.afterEach(to => {
    if (to.name === 'exception') return;
    reportLogStore.reportRouteLog({
      route_id: to.name,
      nav_id: to.meta.navId,
      nav_name: to.meta?.title ?? undefined,
      external_menu: stringifyExternalMenu,
    });
  });

  return router;
};
