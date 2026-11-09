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

import { defineAsyncComponent, defineComponent, h, nextTick, onBeforeUnmount, ref, Suspense } from 'vue';
import type { RouteRecordRaw } from 'vue-router';

import {
  bindRetrieveShellSettle,
  releaseBootstrapShell,
  unbindRetrieveShellSettle,
  whenTopMenuSettled,
} from '@/app/bootstrap/shell-gate';
import RetrievePageSkeleton from '@/app/skeleton/retrieve-page-skeleton.vue';
import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
import RetrieveHelper from '@/features/retrieval/retrieve-helper';
import useStore from '@/shared/composables/use-store';

// 检索模块各组件异步声明（用于路由懒加载）
const RetrieveView = defineAsyncComponent({
  loader: () => import(/* webpackChunkName: 'logRetrieve' */ '@/features/retrieval/retrieve-hub'),
  suspensible: true,
});
const Retrieve = defineComponent({
  name: 'RetrieveRoute',
  setup() {
    const shellReady = ref(false);
    let contentReady = false;
    let menuReady = false;
    const revealShell = () => {
      if (shellReady.value || !contentReady || !menuReady) {
        return;
      }
      shellReady.value = true;
      nextTick(() => releaseBootstrapShell());
    };
    const markContentReady = () => {
      contentReady = true;
      revealShell();
    };
    bindRetrieveShellSettle(markContentReady);
    onBeforeUnmount(() => unbindRetrieveShellSettle(markContentReady));
    whenTopMenuSettled(() => {
      menuReady = true;
      revealShell();
    });
    window.setTimeout(() => {
      menuReady = true;
      revealShell();
    }, 8000);
    const store = useStore();
    const fieldSetting = store.state.storage?.[BK_LOG_STORAGE.FIELD_SETTING] ?? {};
    const fieldWidth = fieldSetting.show === false ? 0 : Number(fieldSetting.width) || 200;
    const trendHeight = store.state.storage?.[BK_LOG_STORAGE.TREND_CHART_IS_FOLD] ? 40 : 170;
    const railWidth = RetrieveHelper.isFavoriteShown
      ? RetrieveHelper.favoriteWidth > 0
        ? RetrieveHelper.favoriteWidth
        : 240
      : 0;

    return () =>
      h('div', { class: 'retrieve-route-host' }, [
        h(Suspense, null, {
          default: () => h(RetrieveView),
          fallback: () => null,
        }),
        shellReady.value
          ? null
          : h(RetrievePageSkeleton, {
              cover: true,
              fieldWidth,
              railWidth,
              trendHeight,
            }),
      ]);
  },
});
const ExternalAuth = () => import(/* webpackChunkName: 'externalAuth' */ '@/features/authorization/authorization-list');
const ShareLink = () => import(/* webpackChunkName: 'share-link' */ '@/features/sharing/index.tsx');
const DataIdUrl = () => import(/* webpackChunkName: 'data-id-url' */ '@/features/data-id/index.tsx');
const TemplateManage = () => import('@/features/retrieval/workspace/search-result/template-manage/index.tsx');
const ClientLogSearch = () => import(/* webpackChunkName: 'clientLogSearch' */ '@/features/client-logs/search/index.tsx');

// 检索模块路由配置生成函数
const getRetrieveRoutes = (): RouteRecordRaw[] => [
  // 检索主页面
  {
    path: '/retrieve/:indexId?',
    name: 'retrieve',
    component: Retrieve,
    meta: {
      title: '检索',
      navId: 'retrieve',
    },
  },
  // 客户端日志检索
  {
    path: '/client-log-search',
    name: 'client-log-search',
    component: ClientLogSearch,
    meta: {
      title: '客户端日志',
      navId: 'client-log-search',
    },
  },
  // 模版管理
  {
    path: '/template-manage',
    name: 'templateManage',
    component: TemplateManage,
  },
  // 授权列表
  {
    path: '/external-auth/:activeNav?',
    name: 'externalAuth',
    component: ExternalAuth,
    meta: {
      title: '授权列表',
      navId: 'external-auth',
    },
  },
  // 分享链接
  {
    path: '/share/:linkId?',
    name: 'share',
    component: ShareLink,
    meta: {
      title: '分享链接',
      navId: 'share',
    },
  },

  // 根据 bk_data_id 获取采集项和索引集信息
  {
    path: '/data_id/:id?',
    name: 'data_id',
    component: DataIdUrl,
    meta: {
      title: '根据 bk_data_id 获取采集项和索引集信息',
      navId: 'data_id',
    },
  },
];

export default getRetrieveRoutes;
