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

/** 我有权限的业务ID */
export const MY_AUTH_BIZ_ID = -1;
/** 我有告警的业务ID */
export const MY_ALARM_BIZ_ID = -2;
/** 内容滚动元素类名 */
export const CONTENT_SCROLL_ELEMENT_CLASS_NAME = 'alarm-center-content';
