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
// 是否中文
export const isZh = () => ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale);
/** 节点icon映射 */
export const TREE_SHOW_ICON_LIST = {
  /** 状态icon列表 */
  status: {
    ABNORMAL: 'mind-fill',
    RECOVERED: 'mc-check-fill',
    CLOSED: 'mc-expired',
  },
  /** 节点层级icon列表 */
  node_level: {
    service: 'default',
    host_platform: 'menu-performance',
    data_center: 'mc-data-center',
  },
  /** 告警名称icon列表 */
  alert_name: {},
  /** 节点名称icon列表 */
  node_name: {},
  /** 节点类型icon列表 */
  node_type: {},
  /** 监控数据项icon列表 */
  metricName: {},
};
export const EVENT_SEVERITY = {
  FATAL: { label: '致命', icon: 'danger', key: 'FATAL' },
  WARNING: { label: '预警', icon: 'mind-fill', key: 'WARNING' },
  REMIND: { label: '提醒', icon: 'tips', key: 'REMIND' },
};
export const dialogConfig = {
  quickShield: {
    show: false,
    details: [
      {
        severity: 1,
        dimension: '',
        trigger: '',
        strategy: {
          id: '',
          name: '',
        },
      },
    ],
    ids: [],
    bizIds: [],
  },
  alarmConfirm: {
    show: false,
    ids: [],
    bizIds: [],
  },
  rootCauseConfirm: {
    show: false,
    ids: [],
    data: {},
    bizIds: [],
  },
  alarmDispatch: {
    show: false,
    bizIds: [],
    alertIds: [],
  },
  manualProcess: {
    show: false,
    alertIds: [],
    bizIds: [],
    debugKey: '',
    actionIds: [],
    mealInfo: null,
  },
};
export const LEVEL_LIST = {
  /** 致命 */
  ERROR: {
    label: '致命',
    key: 'danger',
    name: 'ERROR',
    color: '#EA3636',
  },
  /** 预警 */
  WARN: {
    label: '预警',
    key: 'mind-fill',
    name: 'WARN',
    color: '#FF9C01',
  },
  /** 提醒 */
  INFO: {
    label: '提醒',
    key: 'tips',
    name: 'INFO',
    color: '#3A84FF',
  },
};
