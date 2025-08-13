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
const { i18n } = window;

export enum EStatusMap {
  AVAILABLE = 'notInstalled', // 未安装
  DISABLED = 'terminated', // 已停用
  ENABLED = 'installed', // 已安装
  NO_DATA = 'noData', // 无数据
  REMOVE_SOON = 'willBeRemoved', // 将下架
  REMOVED = 'removed', // 已下架
  UPDATABLE = 'update', // 有更新
}

export type MapType<T extends string> = { [key in T]?: any };

// 已启用 ENABLED
// 有更新 UPDATABLE
// 无数据 NO_DATA
// 将下架 REMOVE_SOON
// 已下架 REMOVED
// 已停用 DISABLED
// 未安装 AVAILABLE
export type StatusType = 'AVAILABLE' | 'DISABLED' | 'ENABLED' | 'NO_DATA' | 'REMOVE_SOON' | 'REMOVED' | 'UPDATABLE';
export const bgColorMap: MapType<string> = {
  notInstalled: '', // 未安装
  installed: '#679EF3', // 已安装
  update: '#14A568', // 有更新
  noData: '#FF5656', // 无数据
  terminated: '#979BA4', // 已停用
  willBeRemoved: '#FF9C04', // 将下架
  removed: '#DCDEE6', // 已下架
};

export const fontColorMap: MapType<string> = {
  notInstalled: '', // 未安装
  installed: '#6A9CF4', // 已安装
  update: '#14A568', // 有更新
  noData: '#FF5656', // 无数据
  terminated: '#989AA5', // 已停用
  willBeRemoved: '#FF9C00', // 将下架
  removed: '#969BA5', // 已下架
};

export const textMap: MapType<string> = {
  notInstalled: i18n.t('未安装'),
  installed: i18n.t('已安装'),
  update: i18n.t('有更新'),
  noData: i18n.t('无数据'),
  terminated: i18n.t('已停用'),
  willBeRemoved: i18n.t('将下架'),
  removed: i18n.t('已下架'),
};

export enum EPluginType {
  email = 'email_pull',
  pull = 'http_pull',
  push = 'http_push',
}

export interface IAlertConfigTable {
  name: string;
  rules: IConditionRules[];
}
export interface IBaseInfo {
  categoryDisplay: string;
  createUser: string;
  isInstalled?: boolean;
  label: string[];
  logo: string;
  name: string;
  pluginId: string;
  pluginType: TPluginType;
  pluginTypeDisplay: string;
  popularity: number;
  scenario: IScenario;
  sourceCode: string;
  updateTime: string;
  updateUser: string;
  version: string;
}

export interface IConditionRules {
  condition?: string;
  key: string;
  method: string;
  value: string[];
}

export interface INormalizationTable {
  description: string;
  displayName: string;
  expr: string;
  field: string;
  type: string;
}

export interface IPushConfigData {
  ingesterHost: string;
  pluginId: string;
  pushUrl?: string;
  sourceFormat: string;
}

export type IScenario = 'EMAIL' | 'MONITOR' | 'REST_API';

export interface ITabListItem {
  id: number;
  name: string;
  warning?: boolean;
}

export type TPluginType = 'email_pull' | 'http_pull' | 'http_push';

export type TPluginTypeObj = { [key in TPluginType]?: string };

export type TScenaris = { [key in IScenario]?: string };
