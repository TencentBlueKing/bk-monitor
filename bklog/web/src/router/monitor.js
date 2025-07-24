import exception from '@/views/404';

// #if MONITOR_APP === 'apm'
const MonitorApmLog = () => import(/* webpackChunkName: 'monitor-apm-log' */ '@/views/retrieve-v3/monitor/monitor.tsx');
// #endif
// #if MONITOR_APP === 'trace'
const MonitorTraceLog = () => import(/* webpackChunkName: 'monitor-trace-log' */ '@/views/retrieve-v3/monitor/monitor.tsx');
// #endif

// 监控模块路由配置生成函数
const getMonitorRoutes = () => [
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

export default getMonitorRoutes;
