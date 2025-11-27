/* eslint-disable @typescript-eslint/naming-convention */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

export const ALARM_CENTER_PANEL_TAB_MAP = {
  VIEW: 'view',
  LOG: 'log',
  TRACE: 'trace',
  HOST: 'host',
  PROCESS: 'process',
  CONTAINER: 'container',
  EVENT: 'event',
  // METRIC: 'metric',
  ALARM: 'alarm',
} as const;

export const ALARM_CENTER_PANEL_TAB_LABEL_MAP = {
  [ALARM_CENTER_PANEL_TAB_MAP.VIEW]: window.i18n.t('视图'),
  [ALARM_CENTER_PANEL_TAB_MAP.LOG]: window.i18n.t('日志'),
  [ALARM_CENTER_PANEL_TAB_MAP.TRACE]: window.i18n.t('调用链'),
  [ALARM_CENTER_PANEL_TAB_MAP.HOST]: window.i18n.t('主机'),
  [ALARM_CENTER_PANEL_TAB_MAP.PROCESS]: window.i18n.t('进程'),
  [ALARM_CENTER_PANEL_TAB_MAP.CONTAINER]: window.i18n.t('容器'),
  [ALARM_CENTER_PANEL_TAB_MAP.EVENT]: window.i18n.t('关联事件'),
  // [ALARM_CENTER_PANEL_TAB_MAP.METRIC]: window.i18n.t('相关性指标'),
  [ALARM_CENTER_PANEL_TAB_MAP.ALARM]: window.i18n.t('收敛的告警'),
} satisfies Record<AlarmCenterPanelTabType, string>;

export type AlarmCenterPanelTabType = (typeof ALARM_CENTER_PANEL_TAB_MAP)[keyof typeof ALARM_CENTER_PANEL_TAB_MAP];

export const AlarmCenterPanelTabList: { label: string; name: AlarmCenterPanelTabType }[] = Object.values(
  ALARM_CENTER_PANEL_TAB_MAP
).map(name => ({
  label: ALARM_CENTER_PANEL_TAB_LABEL_MAP[name as AlarmCenterPanelTabType],
  name: name as AlarmCenterPanelTabType,
}));

export const ALARM_CENTER_VIEW_TAB_MAP = {
  DIMENSION: 'dimension', // 维度分析
  ALARM_RECORDS: 'alarm_records', // 告警流转记录
} as const;
