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

// 嵌套路由视图组件声明（用于实现多层嵌套路由结构时，多级 children 路由的占位）
const LogCollectionView = { name: 'LogCollection', template: '<router-view></router-view>' };
// 管理模块路由配置生成函数
const getManageRoutes = () => [
  {
    path: '/manage',
    name: 'manage',
    component: LogCollectionView,
    // 根据当前环境（外部版/内部版）自动重定向到管理页默认子页面
    redirect: (to) => {
      // 外部版:跳转到“日志提取任务”
      if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL)) {
        return {
          path: '/manage/log-extract-task',
          query: {
            spaceUid: to.query.spaceUid,
            bizId: to.query.bizId,
          },
        };
      }
      // 内部版:跳转到“采集项列表”
      return {
        path: '/manage/log-collection/collection-item',
        query: {
          spaceUid: to.query.spaceUid,
          bizId: to.query.bizId,
        },
      };
    },
    children: [
      // 日志接入-日志采集
      {
        path: 'log-collection',
        name: 'log-collection',
        component: LogCollectionView,
        redirect: '/manage/log-collection/collection-item',
        children: [
          // 采集项
          {
            path: 'collection-item',
            name: 'collection-item',
            component: LogCollectionView,
            redirect: '/manage/log-collection/collection-item/list',
            children: [
              // 采集项列表
              {
                path: 'list',
                name: 'collection-item-list',
                meta: {
                  title: '日志采集',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 查看采集项
              {
                path: 'manage/:collectorId',
                name: 'manage-collection',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 新建采集项
              {
                path: 'add',
                name: 'collectAdd',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 编辑采集项
              {
                path: 'edit/:collectorId',
                name: 'collectEdit',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 字段清洗
              {
                path: 'field/:collectorId',
                name: 'collectField',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 存储配置
              {
                path: 'storage/:collectorId',
                name: 'collectStorage',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 脱敏配置
              {
                path: 'masking/:collectorId',
                name: 'collectMasking',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 启用采集项
              {
                path: 'start/:collectorId',
                name: 'collectStart',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 停用采集项
              {
                path: 'stop/:collectorId',
                name: 'collectStop',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'collection-item',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
            ],
          },
          // 索引集
          {
            path: 'log-index-set',
            name: 'log-index-set',
            component: LogCollectionView,
            redirect: '/manage/log-collection/log-index-set/list',
            children: [
              // 索引集列表
              {
                path: 'list',
                name: 'log-index-set-list',
                meta: {
                  title: '日志采集',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 索引集详情
              {
                path: 'manage/:indexSetId',
                name: 'log-index-set-manage',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'log-index-set-list',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 新建索引集
              {
                path: 'create',
                name: 'log-index-set-create',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'log-index-set-list',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 编辑索引集
              {
                path: 'edit/:indexSetId',
                name: 'log-index-set-edit',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'log-index-set-list',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
              // 脱敏编辑
              {
                path: 'masking/:indexSetId',
                name: 'log-index-set-masking',
                meta: {
                  title: '日志采集',
                  needBack: true,
                  backName: 'log-index-set-list',
                  navId: 'log-collection',
                },
                component: LogCollectionView,
              },
            ],
          },
        ],
      },
      // 日志接入-计算平台
      {
        path: 'bk-data-collection',
        name: 'bk-data-collection',
        component: LogCollectionView,
        redirect: '/manage/bk-data-collection/list',
        children: [
          // 计算平台列表
          {
            path: 'list',
            name: 'bkdata-index-set-list',
            meta: {
              title: '计算平台',
              navId: 'bk-data-collection',
            },
            component: LogCollectionView,
          },
          // 采集详情
          {
            path: 'manage/:indexSetId',
            name: 'bkdata-index-set-manage',
            meta: {
              title: '计算平台',
              needBack: true,
              backName: 'bkdata-index-set-list',
              navId: 'bk-data-collection',
            },
            component: LogCollectionView,
          },
          // 新建索引集
          {
            path: 'create',
            name: 'bkdata-index-set-create',
            meta: {
              title: '计算平台',
              needBack: true,
              backName: 'bkdata-index-set-list',
              navId: 'bk-data-collection',
            },
            component: LogCollectionView,
          },
          // 编辑索引集
          {
            path: 'edit/:indexSetId',
            name: 'bkdata-index-set-edit',
            meta: {
              title: '计算平台',
              needBack: true,
              backName: 'bkdata-index-set-list',
              navId: 'bk-data-collection',
            },
            component: LogCollectionView,
          },
          // 脱敏编辑
          {
            path: 'masking/:indexSetId',
            name: 'bkdata-index-set-masking',
            meta: {
              title: '计算平台',
              needBack: true,
              backName: 'bkdata-index-set-list',
              navId: 'bk-data-collection',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 日志接入-第三方ES
      {
        path: 'es-collection',
        name: 'es-collection',
        component: LogCollectionView,
        redirect: '/manage/es-collection/list',
        children: [
          // 第三方ES列表
          {
            path: 'list',
            name: 'es-index-set-list',
            meta: {
              title: '第三方ES',
              navId: 'es-collection',
            },
            component: LogCollectionView,
          },
          // 采集详情
          {
            path: 'manage/:indexSetId',
            name: 'es-index-set-manage',
            meta: {
              title: '第三方ES',
              needBack: true,
              backName: 'es-index-set-list',
              navId: 'es-collection',
            },
            component: LogCollectionView,
          },
          // 新建索引集
          {
            path: 'create',
            name: 'es-index-set-create',
            meta: {
              title: '第三方ES',
              needBack: true,
              backName: 'es-index-set-list',
              navId: 'es-collection',
            },
            component: LogCollectionView,
          },
          // 编辑索引集
          {
            path: 'edit/:indexSetId',
            name: 'es-index-set-edit',
            meta: {
              title: '第三方ES',
              needBack: true,
              backName: 'es-index-set-list',
              navId: 'es-collection',
            },
            component: LogCollectionView,
          },
          // 脱敏编辑
          {
            path: 'masking/:indexSetId',
            name: 'es-index-set-masking',
            meta: {
              title: '第三方ES',
              needBack: true,
              backName: 'es-index-set-list',
              navId: 'es-collection',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 日志接入-自定义上报
      {
        path: 'custom-report',
        name: 'custom-report',
        component: LogCollectionView,
        redirect: '/manage/custom-report/list',
        children: [
          // 自定义上报列表
          {
            path: 'list',
            name: 'custom-report-list',
            meta: {
              title: '自定义上报',
              navId: 'custom-report',
            },
            component: LogCollectionView,
          },
          // 新建自定义上报
          {
            path: 'create',
            name: 'custom-report-create',
            meta: {
              title: '自定义上报',
              needBack: true,
              backName: 'custom-report-list',
              navId: 'custom-report',
            },
            component: LogCollectionView,
          },
          // 编辑自定义上报
          {
            path: 'edit/:collectorId',
            name: 'custom-report-edit',
            meta: {
              title: '自定义上报',
              needBack: true,
              backName: 'custom-report-list',
              navId: 'custom-report',
            },
            component: LogCollectionView,
          },
          // 自定义上报采集详情
          {
            path: 'detail/:collectorId',
            name: 'custom-report-detail',
            meta: {
              title: '自定义上报',
              needBack: true,
              backName: 'custom-report-list',
              navId: 'custom-report',
            },
            component: LogCollectionView,
          },
          // 自定义上报脱敏编辑
          {
            path: 'masking/:indexSetId',
            name: 'custom-report-masking',
            meta: {
              title: '自定义上报',
              needBack: true,
              backName: 'custom-report-list',
              navId: 'custom-report',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 日志清洗-清洗列表
      {
        path: 'clean-list',
        name: 'clean-list',
        component: LogCollectionView,
        redirect: '/manage/clean-list/list',
        children: [
          // 清洗列表
          {
            path: 'list',
            name: 'log-clean-list',
            meta: {
              title: '日志清洗',
              navId: 'clean-list',
            },
            component: LogCollectionView,
          },
          // 新增清洗
          {
            path: 'create',
            name: 'clean-create',
            meta: {
              title: '日志清洗',
              needBack: true,
              backName: 'log-clean-list',
              navId: 'clean-list',
            },
            component: LogCollectionView,
          },
          // 编辑清洗
          {
            path: 'edit/:collectorId',
            name: 'clean-edit',
            meta: {
              title: '日志清洗',
              needBack: true,
              backName: 'log-clean-list',
              navId: 'clean-list',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 日志清洗-清洗模板
      {
        path: 'clean-templates',
        name: 'clean-templates',
        component: LogCollectionView,
        redirect: '/manage/clean-templates/list',
        children: [
          // 模板列表
          {
            path: 'list',
            name: 'log-clean-templates',
            meta: {
              title: '日志清洗',
              navId: 'clean-templates',
            },
            component: LogCollectionView,
          },
          // 新建模板
          {
            path: 'create',
            name: 'clean-template-create',
            meta: {
              title: '日志清洗',
              needBack: true,
              backName: 'log-clean-templates',
              navId: 'clean-templates',
            },
            component: LogCollectionView,
          },
          // 编辑模板
          {
            path: 'edit/:templateId',
            name: 'clean-template-edit',
            meta: {
              title: '日志清洗',
              needBack: true,
              backName: 'log-clean-templates',
              navId: 'clean-templates',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 日志清洗-日志脱敏
      {
        path: 'log-desensitize',
        name: 'log-desensitize',
        component: LogCollectionView,
        redirect: '/manage/log-desensitize/list',
        children: [
          // 脱敏列表
          {
            path: 'list',
            name: 'log-desensitize-list',
            component: LogCollectionView,
            meta: {
              title: '日志清洗',
              navId: 'log-desensitize',
            },
          },
        ],
      },
      // 日志归档-归档仓库
      {
        path: 'archive-repository',
        name: 'archive-repository',
        component: LogCollectionView,
        meta: {
          title: '日志归档',
          navId: 'archive-repository',
        },
      },
      // 日志归档-归档列表
      {
        path: 'archive-list',
        name: 'archive-list',
        component: LogCollectionView,
        meta: {
          title: '日志归档',
          navId: 'archive-list',
        },
      },
      // 日志归档-归档回溯
      {
        path: 'archive-restore',
        name: 'archive-restore',
        component: LogCollectionView,
        meta: {
          title: '日志归档',
          navId: 'archive-restore',
        },
      },
      // 日志提取-提取配置
      {
        path: 'manage-log-extract',
        name: 'manage-log-extract',
        component: LogCollectionView,
        meta: {
          title: '日志提取',
          navId: 'manage-log-extract',
        },
      },
      // 日志提取-提取任务
      {
        path: 'log-extract-task',
        name: 'log-extract-task',
        component: LogCollectionView,
        redirect: '/manage/log-extract-task',
        meta: {
          title: '日志提取',
          navId: 'log-extract-task',
        },
        children: [
          // 提取任务列表
          {
            path: '',
            name: 'extract-home',
            component: LogCollectionView,
            meta: {
              title: '日志提取',
              navId: 'log-extract-task',
            },
          },
          // 新建提取任务
          {
            path: 'extract-create',
            name: 'extract-create',
            component: LogCollectionView,
            meta: {
              title: '日志提取',
              needBack: true,
              backName: 'log-extract-task',
              navId: 'log-extract-task',
            },
          },
          // 克隆提取任务
          {
            path: 'extract-clone',
            name: 'extract-clone',
            component: LogCollectionView,
            meta: {
              title: '日志提取',
              needBack: true,
              backName: 'log-extract-task',
              navId: 'log-extract-task',
            },
          },
        ],
      },
      // 日志提取-链路管理
      {
        path: 'extract-link-manage',
        name: 'extract-link-manage',
        component: LogCollectionView,
        redirect: '/manage/extract-link-manage/list',
        children: [
          // 链路管理列表
          {
            path: 'list',
            name: 'extract-link-list',
            component: LogCollectionView,
            meta: {
              title: '日志提取',
              navId: 'extract-link-manage',
            },
          },
          // 编辑链路
          {
            path: 'edit/:linkId',
            name: 'extract-link-edit',
            meta: {
              title: '日志提取',
              needBack: true,
              backName: 'extract-link-list',
              navId: 'extract-link-manage',
            },
            component: LogCollectionView,
          },
          // 新建链路
          {
            path: 'create',
            name: 'extract-link-create',
            meta: {
              title: '日志提取',
              needBack: true,
              backName: 'extract-link-list',
              navId: 'extract-link-manage',
            },
            component: LogCollectionView,
          },
        ],
      },
      // ES集群-集群管理
      {
        path: 'es-cluster-manage',
        name: 'es-cluster-manage',
        component: LogCollectionView,
        meta: {
          title: 'ES集群',
          navId: 'es-cluster-manage',
        },
      },
      // 订阅-订阅管理
      {
        path: 'report-manage',
        name: 'report-manage',
        component: LogCollectionView,
        meta: {
          title: '订阅管理',
          navId: 'report-manage',
        },
      },
      // 全链路追踪-采集接入
      {
        path: 'collection-track',
        name: 'collection-track',
        component: LogCollectionView,
        meta: {
          title: '采集接入',
          navId: 'collection-track',
        },
      },
      // 全链路追踪 - 数据平台接入
      {
        path: 'bk-data-track',
        name: 'bk-data-track',
        component: LogCollectionView,
        redirect: '/manage/bk-data-track/list',
        children: [
          // 数据平台列表
          {
            path: 'list',
            name: 'bkdata-track-list',
            component: LogCollectionView,
            meta: {
              title: '数据平台接入',
              navId: 'bk-data-track',
            },
          },
          // 采集详情
          {
            path: 'manage/:indexSetId',
            name: 'bkdata-track-manage',
            meta: {
              title: '数据平台接入',
              needBack: true,
              backName: 'bkdata-track-list',
              navId: 'bk-data-track',
            },
            component: LogCollectionView,
          },
          // 新建数据平台
          {
            path: 'create',
            name: 'bkdata-track-create',
            meta: {
              title: '数据平台接入',
              needBack: true,
              backName: 'bkdata-track-list',
              navId: 'bk-data-track',
            },
            component: LogCollectionView,
          },
          // 编辑数据平台
          {
            path: 'edit/:indexSetId',
            name: 'bkdata-track-edit',
            meta: {
              title: '数据平台接入',
              needBack: true,
              backName: 'bkdata-track-list',
              navId: 'bk-data-track',
            },
            component: LogCollectionView,
          },
        ],
      },
      // 全链路追踪 - SDK接入
      {
        path: 'sdk-track',
        name: 'sdk-track',
        component: LogCollectionView,
        meta: {
          title: 'SDK接入',
          navId: 'sdk-track',
        },
      },
      // 管理-采集链路管理
      {
        path: 'manage-data-link-conf',
        name: 'manage-data-link-conf',
        component: LogCollectionView,
        meta: {
          title: '设置',
          navId: 'manage-data-link-conf',
        },
      },
      // 兼容旧版管理端路由，访问 /manage/collect 时自动跳转到采集项列表页面
      {
        path: 'collect',
        redirect: '/manage/log-collection/collection-item',
      },
    ],
  },
];

export default getManageRoutes;
