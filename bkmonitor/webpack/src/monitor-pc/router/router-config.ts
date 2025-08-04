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
// global feature
export const GLOBAL_FEATURE_LIST = [
  {
    id: 'global-config',
    name: '全局设置',
    icon: 'icon-monitor icon-quanjushezhi',
  },
  {
    id: 'healthz',
    name: '自监控',
    icon: 'icon-monitor icon-zijiankong',
  },
  {
    id: 'migrate-dashboard',
    name: '迁移工具',
    icon: 'icon-monitor icon-qianyigongju',
  },
  {
    id: 'calendar',
    name: '日历服务',
    icon: 'icon-monitor icon-rilifuwu',
  },
  {
    id: 'space-manage',
    name: '空间管理',
    icon: 'icon-monitor icon-kongjianguanli',
  },
  // {
  //   id: 'resource-register',
  //   name: '资源注册',
  //   icon: 'icon-monitor icon-mc-migrate-tool'
  // }
  // {
  //   id: 'data-pipeline',
  //   name: '链路管理',
  //   icon: 'icon-monitor icon-mc-migrate-tool'
  // }
];
// route config
// route item
export interface IRouteConfigItem {
  active?: boolean;
  canStore?: boolean;
  children?: IRouteConfigItem[];
  hidden?: boolean;
  href?: string;
  icon?: string;
  id: string;
  isBeta?: boolean;
  name: string;
  navName?: string;
  noCache?: boolean /** 侧栏导航不缓存到浏览器 */;
  path?: string;
  query?: any;
  route?: string;
  shortName?: string;
  usePath?: boolean;
}
// route config
// nav list
export const getRouteConfig = () => {
  const routeConfig: IRouteConfigItem[] = [
    {
      id: 'home',
      name: '首页',
      route: 'home',
    },
    {
      id: 'dashboard',
      name: '仪表盘',
      route: 'grafana',
    },
    {
      id: 'data',
      name: '数据探索',
      route: 'data-retrieval',
      children: [
        {
          name: '指标检索',
          icon: 'icon-monitor icon-zhibiaojiansuo menu-icon',
          navName: '指标检索',
          id: 'data-retrieval',
          path: '/data-retrieval',
          href: '#/data-retrieval',
          canStore: true,
        },
        {
          name: '日志检索',
          icon: 'icon-monitor icon-rizhijiansuo menu-icon',
          navName: '日志检索',
          id: 'log-retrieval',
          path: '/log-retrieval',
          href: '#/log-retrieval',
          canStore: true,
        },
        {
          name: '事件检索',
          icon: 'icon-monitor icon-shijianjiansuo menu-icon',
          navName: '事件检索',
          id: 'event-retrieval',
          path: '/event-retrieval',
          href: '#/event-retrieval',
          canStore: true,
        },
        {
          name: '事件检索',
          icon: 'icon-monitor icon-shijianjiansuo menu-icon',
          navName: '事件检索',
          id: 'event-explore',
          path: '/event-explore',
          href: '#/event-explore',
          canStore: true,
        },
        {
          name: 'Tracing 检索',
          icon: 'icon-monitor menu-icon icon-Tracing',
          navName: 'Tracing 检索',
          id: 'trace-retrieval',
          path: '/trace/home',
          href: '#/trace/home',
          usePath: true,
          // isBeta: window.platform?.te === false,
          canStore: true,
        },
        {
          name: 'Profiling 检索',
          icon: 'icon-monitor icon-Profiling menu-icon',
          navName: 'Profiling 检索',
          id: 'profiling',
          path: '/trace/profiling',
          href: '#/trace/profiling',
          usePath: true,
          // isBeta: window.platform?.te === false,
          canStore: true,
        },
      ],
    },
    {
      id: 'event',
      name: '告警事件',
      route: 'event-center',
      canStore: true,
    },
    {
      id: 'scenes',
      name: '观测场景',
      route: 'performance',
      children: [
        {
          name: '用户体验',
          shortName: '体验',
          id: 'monitor-experience',
          children: [
            {
              name: '综合拨测',
              icon: 'icon-monitor icon-boce menu-icon',
              navName: '综合拨测',
              id: 'uptime-check',
              path: '/uptime-check',
              href: '#/uptime-check',
              canStore: true,
            },
            {
              name: 'APM',
              icon: 'icon-monitor icon-APM menu-icon',
              navName: 'APM',
              id: 'apm-home',
              path: '/apm/home',
              href: '#/apm/home',
              hidden: !window.enable_apm,
              // isBeta: window.platform?.te === false,
              canStore: true,
            },
          ],
        },
        {
          name: '主机&云平台',
          shortName: '主机',
          id: 'monitor-serivice',
          children: [
            {
              name: '容器监控',
              icon: 'icon-monitor icon-rongqi menu-icon',
              id: 'k8s',
              path: '/k8s',
              href: '#/k8s',
              canStore: true,
            },
            {
              name: '容器监控',
              icon: 'icon-monitor icon-rongqi menu-icon',
              id: 'k8s-new',
              path: '/k8s-new',
              href: '#/k8s-new',
              canStore: true,
            },
            {
              name: '主机监控',
              icon: 'icon-monitor icon-zhuji menu-icon',
              id: 'performance',
              path: '/performance',
              href: '#/performance',
              canStore: true,
            },
          ],
        },
        {
          name: '其他',
          shortName: '其他',
          id: 'other',
          children: [
            {
              name: '自定义场景',
              icon: 'icon-monitor icon-zidingyichangjing menu-icon',
              id: 'custom-scenes',
              path: '/custom-scenes',
              href: '#/custom-scenes',
              canStore: true,
            },
          ],
        },
      ],
    },
    {
      id: 'manager',
      name: '配置',
      route: 'strategy-config',
      children: [
        {
          name: '告警配置',
          shortName: '告警配置',
          id: 'monitor',
          children: [
            {
              name: '告警策略',
              icon: 'icon-monitor icon-gaojingcelve menu-icon',
              id: 'strategy-config',
              path: '/strategy-config',
              href: '#/strategy-config',
              canStore: true,
            },
            {
              name: '告警分派',
              icon: 'icon-monitor icon-gaojingfenpai menu-icon',
              id: 'alarm-dispatch',
              path: '/alarm-dispatch',
              href: '#/alarm-dispatch',
              canStore: true,
            },
            {
              name: '告警组',
              icon: 'icon-monitor icon-gaojingzu menu-icon',
              id: 'alarm-group',
              path: '/alarm-group',
              canStore: true,
              href: '#/alarm-group',
            },
            {
              name: '轮值',
              icon: 'icon-monitor icon-lunzhi menu-icon',
              id: 'rotation',
              path: '/trace/rotation',
              canStore: true,
              href: '#/trace/rotation',
            },
            {
              name: '指标管理',
              icon: 'icon-monitor icon-zhibiaoguanli menu-icon',
              id: 'metrics-manager',
              path: '/metrics-manager',
              href: '#/metrics-manager',
              canStore: true,
              hidden: true,
            },
          ],
        },
        {
          name: '告警处理',
          shortName: '处理',
          id: 'alert-set',
          children: [
            {
              name: '告警屏蔽',
              icon: 'icon-monitor icon-gaojingpingbi menu-icon',
              id: 'alarm-shield',
              path: '/trace/alarm-shield',
              href: '#/trace/alarm-shield',
              canStore: true,
            },
            {
              name: '处理套餐',
              icon: 'icon-monitor icon-chulitaocan1 menu-icon',
              id: 'set-meal',
              path: '/set-meal',
              href: '#/set-meal',
              canStore: true,
            },
          ],
        },
        // {
        //   name: '订阅管理',
        //   shortName: '管理',
        //   id: 'report-management',
        //   children: [
        //     {
        //       name: '订阅配置',
        //       icon: 'icon-monitor icon-mc-youjian menu-icon',
        //       id: 'report',
        //       path: '/trace/report',
        //       href: '#/trace/report',
        //       canStore: true
        //     }
        //   ]
        // },
        window.enable_aiops
          ? {
              name: '智能设置',
              shortName: '智能',
              id: 'ai',
              children: [
                {
                  name: 'AI设置',
                  icon: 'icon-monitor icon-AI menu-icon',
                  id: 'ai-settings',
                  path: '/ai-settings',
                  href: '#/ai-settings',
                  canStore: true,
                },
              ],
            }
          : undefined,
      ].filter(Boolean),
    },
    {
      id: 'integrated',
      name: '集成',
      route: 'plugin-manager',
      children: [
        {
          name: '插件',
          shortName: '插件',
          id: 'intergrations',
          children: [
            {
              name: '指标插件',
              icon: 'icon-monitor icon-chajian menu-icon',
              id: 'plugin-manager',
              path: '/plugin-manager',
              href: '#/plugin-manager',
              canStore: true,
            },
            {
              name: '告警源',
              icon: 'icon-monitor icon-gaojingyuan menu-icon',
              id: 'fta-integrated',
              path: '/fta/intergrations',
              href: '#/fta/intergrations',
              usePath: true,
              canStore: true,
            },
          ],
        },
        {
          name: '数据采集',
          shortName: '采集',
          id: 'monitor-collect',
          children: [
            {
              name: '数据采集',
              icon: 'icon-monitor icon-shujucaiji menu-icon',
              id: 'collect-config',
              path: '/collect-config',
              href: '#/collect-config',
              canStore: true,
            },
            {
              name: '自定义指标',
              icon: 'icon-monitor icon-zidingyizhibiao menu-icon',
              id: 'custom-metric',
              path: '/custom-metric',
              href: '#/custom-metric',
              hidden: false,
              canStore: true,
            },
            {
              name: '自定义事件',
              icon: 'icon-monitor icon-zidingyishijian menu-icon',
              id: 'custom-event',
              path: '/custom-event',
              href: '#/custom-event',
              canStore: true,
            },
          ],
        },
        {
          name: '共享',
          shortName: '共享',
          id: 'share',
          children: [
            {
              name: '导入导出',
              icon: 'icon-monitor icon-daorudaochu menu-icon',
              id: 'export-import',
              path: '/export-import',
              href: '#/export-import',
              canStore: true,
            },
          ],
        },
      ],
    },
  ].filter(item => (process.env.APP === 'external' ? item.id === 'dashboard' : true));
  return routeConfig;
};
/**
 * @description: set page route show
 * @param {*} routeId
 * @param {*} isShow
 * @return {*}
 */
export const handleSetPageShow = (routeId: string, isShow: boolean) => {
  const globalConfigParentRoute = getRouteConfig().find(item => item.children?.some(set => set.id === routeId));
  if (globalConfigParentRoute) {
    const globalConfigRoute = globalConfigParentRoute.children.find(item => item.id === routeId);
    globalConfigRoute.hidden = !isShow;
  } else if (globalConfigParentRoute?.children?.length) {
    if (globalConfigParentRoute.children.find(item => item.children?.some(set => set.id === routeId))) {
      const globalConfigRoute = globalConfigParentRoute.children.find(item => item.id === routeId);
      globalConfigRoute.hidden = !isShow;
    }
  }
};
// 用户常用路由列表存储key
export const COMMON_ROUTE_STORE_KEY = 'monitor_store_route_key'.toLocaleUpperCase();
// 用户常用路由列表 访问过的本地存储key
export const LOCAL_COMMON_ROUTE_STORE_KEY = 'local_monitor_store_route_key'.toLocaleUpperCase();
// 默认常用路由列表
export const DEFAULT_ROUTE_LIST = ['strategy-config', 'collect-config', 'performance'];
// 常用路由列表
export const COMMON_ROUTE_LIST = getRouteConfig()
  .filter(item => item.id !== 'home')
  .map(item => {
    if (item.id === 'event') {
      return {
        ...item,
        children: [
          {
            ...item,
            id: 'event-center',
            path: '/event-center',
            icon: 'icon-monitor icon-gaojing3',
            name: '所有告警',
          },
          {
            id: 'event-action',
            path: '/event-center',
            icon: 'icon-monitor icon-chulijilu',
            query: {
              searchType: 'action',
              activeFilterId: 'action',
            },
            name: '处理记录',
          },
        ],
      };
    }
    if (item.id === 'dashboard') {
      return {
        ...item,
        children: [
          {
            name: '默认仪表盘',
            icon: 'icon-monitor icon-yibiaopan menu-icon',
            id: 'grafana-home',
            path: '/grafana',
            href: '#/grafana',
            canStore: true,
          },
          {
            name: '数据源管理',
            icon: 'icon-monitor icon-shujuyuanguanli menu-icon',
            id: 'grafana-admin',
            path: '/grafana/admin',
            href: '#/grafana/admin',
            canStore: true,
          },
          {
            name: '邮件订阅',
            icon: 'icon-monitor icon-youjian menu-icon',
            id: 'email-subscriptions',
            path: '/email-subscriptions',
            href: '#/email-subscriptions',
            hidden: false,
            canStore: true,
          },
          {
            name: '发送历史',
            icon: 'icon-monitor icon-fasonglishi menu-icon',
            id: 'email-subscriptions-history',
            path: '/email-subscriptions/history',
            href: '#/email-subscriptions/history',
            hidden: false,
            canStore: true,
          },
        ],
      };
    }
    if (item.children?.length) {
      return {
        ...item,
        children: item.children.reduce(
          // biome-ignore lint/performance/noAccumulatingSpread: <explanation>
          (pre, cur) => (cur.children?.length ? [...pre, ...cur.children.filter(set => set.canStore)] : [...pre, cur]),
          []
        ),
      };
    }
    return item;
  });
COMMON_ROUTE_LIST.push({
  id: 'global-feature',
  name: '平台设置',
  children: [...GLOBAL_FEATURE_LIST],
});

// 获取本地存储的访问常用路由列表
export function getLocalStoreRoute() {
  const str = localStorage.getItem(LOCAL_COMMON_ROUTE_STORE_KEY);
  if (!str?.length) return undefined;
  try {
    return JSON.parse(str);
  } catch {}
  return undefined;
}
/**
 * @param id 路由id
 * @returns 路由配置
 */
export function getRouteConfigById(id: string) {
  const flatConfig = getRouteConfig().flatMap(config => {
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
  return flatConfig.find(item => item.id === id) || getRouteConfig().find(item => item.route === id);
}
// 路由id是否存在于常用路由列表
export function isInCommonRoute(id: string) {
  return COMMON_ROUTE_LIST.some(item => item?.children?.some(set => set.id === id));
}
// 设置本地存储的访问常用路由列表
export function setLocalStoreRoute(id: string) {
  const list = new Set(getLocalStoreRoute() || []);
  list.has(id) && list.delete(id);
  list.add(id);
  localStorage.setItem(LOCAL_COMMON_ROUTE_STORE_KEY, JSON.stringify(Array.from(list)));
}
