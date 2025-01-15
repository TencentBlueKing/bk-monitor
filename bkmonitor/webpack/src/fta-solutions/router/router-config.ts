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
export const allRouteConfig = [
  {
    id: 'home',
    name: '首页',
    route: 'home',
  },
  {
    id: 'event-center',
    name: '告警事件',
    route: 'event-center',
  },
  {
    id: 'intergrations',
    name: '集成',
    route: 'intergrations',
  },
  {
    id: 'manager',
    name: '管理',
    route: 'set-meal',
    children: [
      {
        name: '告警处理',
        shortName: '告警配置',
        id: 'alarm-handling',
        children: [
          {
            name: '处理套餐',
            icon: 'icon-monitor icon-chulitaocan menu-icon',
            id: 'set-meal',
            path: '/set-meal',
            href: '#/set-meal',
          },
        ],
      },
      {
        name: '监控',
        shortName: '监控',
        id: 'monitor',
        children: [
          {
            name: '告警策略',
            icon: 'icon-monitor icon-mc-strategy menu-icon',
            id: 'strategy-config',
            path: '/strategy-config',
            href: '#/strategy-config',
          },
          {
            name: '告警分派',
            icon: 'icon-monitor icon-fenpai menu-icon',
            id: 'alarm-dispatch',
            path: '/alarm-dispatch',
            href: '#/alarm-dispatch',
          },
          {
            name: '告警屏蔽',
            icon: 'icon-monitor icon-menu-shield menu-icon',
            id: 'alarm-shield',
            path: '/trace/alarm-shield',
            href: '#/trace/alarm-shield',
          },
          {
            name: '告警组',
            icon: 'icon-monitor icon-menu-group menu-icon',
            id: 'alarm-group',
            path: '/alarm-group',
            href: '#/alarm-group',
          },
        ],
      },
    ],
  },
];

export const createRouteConfig = () => allRouteConfig;
