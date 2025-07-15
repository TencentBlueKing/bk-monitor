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

/** 告警类型 */
export enum AlarmType {
  ACTION = 'action',
  ALERT = 'alert',
  INCIDENT = 'incident',
}

export const alarmTypeMap: { label: string; value: AlarmType }[] = [
  {
    label: window.i18n.t('告警'),
    value: AlarmType.ALERT,
  },
  {
    label: window.i18n.t('故障'),
    value: AlarmType.INCIDENT,
  },
  {
    label: window.i18n.t('处理记录'),
    value: AlarmType.ACTION,
  },
] as const;

export const AlarmStatusIconMap = {
  ABNORMAL: {
    icon: 'icon-mind-fill',
    iconColor: '#F59789',
  },
  NOT_SHIELDED_ABNORMAL: {
    icon: 'icon-mind-fill',
    iconColor: '#F59789',
  },
  SHIELDED_ABNORMAL: {
    icon: 'icon-menu-shield',
    iconColor: '#F8B64F',
  },
  RECOVERED: {
    icon: 'icon-mc-check-fill',
    iconColor: '#6FC5BF',
  },
  CLOSED: {
    icon: '',
    iconColor: '#DCDEE5',
  },
};

export const AlarmLevelIconMap = {
  1: {
    icon: 'rect',
    iconColor: '#E71818',
    textColor: '#E71818',
  },
  2: {
    icon: 'rect',
    iconColor: '#E38B02',
    textColor: '#E38B02',
  },
  3: {
    icon: 'rect',
    iconColor: '#3A84FF',
    textColor: '#3A84FF',
  },
};

export const AlertStatusMap = {
  ABNORMAL: {
    prefixIcon: 'alert-status-icon icon-monitor icon-mind-fill',
    alias: window.i18n.t('未恢复'),
  },
  RECOVERED: {
    prefixIcon: 'alert-status-icon icon-monitor icon-mc-check-fill',
    name: window.i18n.t('已恢复'),
  },
  CLOSED: {
    prefixIcon: 'alert-status-icon icon-monitor icon-shixiao',
    alias: window.i18n.t('已失效'),
  },
};

export const AlertDataTypeMap = {
  time_series: {
    prefixIcon: 'description-icon icon-monitor icon-zhibiaojiansuo',
    alias: window.i18n.t('时序数据'),
  },
  event: {
    prefixIcon: 'description-icon icon-monitor icon-shijianjiansuo',
    alias: window.i18n.t('事件'),
  },
  log: {
    prefixIcon: 'description-icon icon-monitor icon-a-logrizhi',
    alias: window.i18n.t('日志'),
  },
};

export const AlertTargetTypeMap = {
  HOST: {
    prefixIcon: 'target-icon icon-monitor icon-zhuji',
    alias: window.i18n.t('主机'),
  },
  SERVICE: {
    prefixIcon: 'target-icon icon-monitor icon-APM',
    alias: window.i18n.t('服务'),
  },
  // INSTANCE: {
  //   prefixIcon: 'target-icon icon-monitor icon-zidingyizhibiao',
  //   alias: window.i18n.t('自定义指标'),
  // },
};

/** 告警-关联信息不同类型提示信息 */
export const EXTEND_INFO_MAP = {
  log_search: window.i18n.t('查看更多相关的日志'),
  custom_event: window.i18n.t('查看更多相关的事件'),
  bkdata: window.i18n.t('查看更多相关的数据'),
};

/** 我有权限的业务ID */
export const MY_AUTH_BIZ_ID = -1;
/** 我有告警的业务ID */
export const MY_ALARM_BIZ_ID = -2;
/** 内容滚动元素类名 */
export const CONTENT_SCROLL_ELEMENT_CLASS_NAME = 'alarm-center-content';
