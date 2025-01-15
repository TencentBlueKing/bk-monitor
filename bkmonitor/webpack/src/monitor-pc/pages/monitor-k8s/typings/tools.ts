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
import type { SceneType } from '../components/common-page';
import type { TranslateResult } from 'vue-i18n';

export interface ITabItem {
  id: number | string;
  name: string;
  show_panel_count?: boolean;
  panel_count?: number;
  type?: SceneType;
  queryType?: string[];
  params?: Record<string, string> /** 额外的参数 */;
  selector_panel?: any;
}

// nav 导航栏设置数据item
export interface INavItem {
  id: string;
  name: TranslateResult | string;
  subName?: string;
  query?: Record<string, any>;
}

// nav 导航栏设置数据item
export interface IRouteBackItem {
  id?: string;
  name?: string;
  query?: Record<string, any>;
  isBack?: boolean;
}
/** 更多菜单id */
export type IMenuId = 'edit-dashboard' | 'edit-tab' | 'edit-variate' | 'view-demo';

export const COMMON_TAB_LIST: ITabItem[] = [
  {
    id: 'dashboard',
    name: window.i18n.tc('概览'),
  },
  {
    id: 'list',
    name: window.i18n.tc('主机列表'),
  },
];
export interface IMenuItem extends ITabItem {
  disable?: boolean;
  show?: boolean;
  id: IMenuId | string;
}
export const COMMON_SETTINGS_LIST: IMenuItem[] = [
  {
    id: 'edit-tab',
    name: window.i18n.tc('编辑页签'),
  },
  {
    id: 'edit-variate',
    name: window.i18n.tc('编辑变量'),
  },
  {
    id: 'edit-dashboard',
    name: window.i18n.tc('编辑视图'),
  },
  {
    id: 'view-demo',
    name: window.i18n.tc('DEMO'),
  },
];

export interface IUptimeCheckType {
  task: 'uptime-check-task';
  node: 'uptime-check-node';
}
export const UPTIME_CHECK_TYPE: IUptimeCheckType = {
  task: 'uptime-check-task',
  node: 'uptime-check-node',
};

export const UPTIME_CHECK_LIST: ITabItem[] = [
  {
    name: window.i18n.tc('拨测任务'),
    id: UPTIME_CHECK_TYPE.task,
  },
  {
    name: window.i18n.tc('拨测节点'),
    id: UPTIME_CHECK_TYPE.node,
  },
];

export type CommonTabType = 'dashboard' | 'list' | IUptimeCheckType['node'] | IUptimeCheckType['task'] | string;

// 平铺模式下 dashboard panel 列数的localstorage key值
export const DASHBOARD_PANEL_COLUMN_KEY = '__chart_view_type__';
