import Vue from 'vue';
import VueRouter from 'vue-router';

// 检索相关页面的异步组件声明（用于路由懒加载）
const Retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');
const ExternalAuth = () => import(/* webpackChunkName: 'externalAuth' */ '@/views/authorization/authorization-list');
const Playground = () => import('@/views/playground');
const ShareLink = () => import(/* webpackChunkName: 'share-link' */ '@/views/share/index.tsx');
const DataIdUrl = () => import(/* webpackChunkName: 'data-id-url' */ '@/views/data-id-url/index.tsx');

const getDefRouteName = () => {
  if (window.IS_EXTERNAL === true || window.IS_EXTERNAL === 'true') {
    if (externalMenu?.includes('retrieve')) {
      return 'retrieve';
    }
    return 'manage';
  }
  return 'retrieve';
};
// 检索模块路由配置生成函数
const getRetrieveRoutes = (spaceId, bkBizId, externalMenu) => [
  // 当用户访问根路径/时，根据当前环境和参数，自动跳转到检索页or管理页
  {
    path: '',
    redirect: () => ({
      name: getDefRouteName(),
      query: {
        spaceUid: spaceId,
        bizId: bkBizId,
      },
    }),
    meta: {
      title: '检索',
      navId: 'retrieve',
    },
  },
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
  // Playground
  {
    path: '/playground',
    name: 'playground',
    component: Playground,
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
