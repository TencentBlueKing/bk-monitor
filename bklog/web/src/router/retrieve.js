import Vue from 'vue';
import VueRouter from 'vue-router';

// 检索模块各组件异步声明（用于路由懒加载）
const Retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');
const ExternalAuth = () => import(/* webpackChunkName: 'externalAuth' */ '@/views/authorization/authorization-list');
const Playground = () => import('@/views/playground');
const ShareLink = () => import(/* webpackChunkName: 'share-link' */ '@/views/share/index.tsx');
const DataIdUrl = () => import(/* webpackChunkName: 'data-id-url' */ '@/views/data-id-url/index.tsx');

// 检索模块路由配置生成函数
const getRetrieveRoutes = () => [
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
  // Playground
  {
    path: '/playground',
    name: 'playground',
    component: Playground,
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