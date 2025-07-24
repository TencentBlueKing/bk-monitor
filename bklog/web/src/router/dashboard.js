// 嵌套路由视图组件声明（用于实现多层嵌套路由结构时，多级 children 路由的占位）
const DashboardTempView = { name: 'DashboardTempView', template: '<router-view></router-view>' };

// 仪表盘模块各组件异步声明（用于路由懒加载）
const dashboard = () => import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard');

// 仪表盘模块路由配置生成函数
const getDashboardRoutes = () => [
  {
    path: '/dashboard',
    name: 'dashboard',
    component: DashboardTempView,
    redirect: '/dashboard/default-dashboard',
    children: [
      // 默认仪表盘
      {
        path: 'default-dashboard',
        name: 'default-dashboard',
        component: dashboard,
        meta: {
          title: '仪表盘',
          navId: 'dashboard',
        },
      },
      // 新建仪表盘
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
      // 新建目录
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
      // 导入仪表盘
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
    ],
  },
];

export default getDashboardRoutes;
