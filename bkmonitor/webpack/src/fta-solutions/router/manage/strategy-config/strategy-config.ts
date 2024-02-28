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
import { RouteConfig } from 'vue-router';
import * as ruleAuth from 'monitor-pc/pages/strategy-config/authority-map';

const StrategyConfig = () =>
  import(/* webpackChunkName: "StrategyConfig" */ '../../../pages/strategy-config/strategy-config');
const StrategyConfigSet = () =>
  import(/* webpackChunkName: "StrategyConfigDetail" */ '../../../pages/strategy-config/strategy-config-set');
const StrategyConfigDetail = () =>
  import(/* webpackChunkName: "StrategyConfigDetail" */ '../../../pages/strategy-config/strategy-config-detail');

export default [
  {
    path: '/strategy-config',
    name: 'strategy-config',
    props: true,
    component: StrategyConfig,
    meta: {
      title: '告警策略',
      navId: 'strategy-config',
      noNavBar: true,
      route: {
        parent: 'manager'
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.VIEW_AUTH
      }
    }
  },
  {
    path: '/strategy-config/edit/:id',
    name: 'strategy-config-edit',
    props: true,
    component: StrategyConfigSet,
    meta: {
      title: '编辑策略配置',
      navId: 'strategy-config',
      route: {
        parent: 'strategy-config'
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_AUTH
      },
      noNavBar: true
    }
  },
  {
    path: '/strategy-config/detail/:id',
    name: 'strategy-config-detail',
    props: {
      noCache: true
    },
    components: {
      noCache: StrategyConfigDetail
    },
    meta: {
      title: '策略配置详情',
      navId: 'strategy-config',
      route: {
        parent: 'strategy-config'
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.VIEW_AUTH
      },
      noNavBar: true
    }
  },
  {
    path: '/strategy-config/add',
    name: 'strategy-config-add',
    component: StrategyConfigSet,
    meta: {
      title: '新建策略配置',
      navId: 'strategy-config',
      route: {
        parent: 'strategy-config'
      },
      noNavBar: true,
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_AUTH
      }
    }
  },
  {
    path: '/strategy-config/clone/:id',
    name: 'strategy-config-clone',
    component: StrategyConfigSet,
    props: true,
    meta: {
      title: '新建策略配置',
      navId: 'strategy-config',
      route: {
        parent: 'strategy-config'
      },
      noNavBar: true,
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_AUTH
      }
    }
  }
] as RouteConfig[];
