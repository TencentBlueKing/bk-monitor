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

/** 告警场景中数据所有可操作的事件枚举 */
export enum AlertAllActionEnum {
  /** 取消选择 */
  CANCEL = 'cancel',
  /** 一键拉群 */
  CHAT = 'chat',
  /** 批量确认 */
  CONFIRM = 'confirm',
  /** 批量分派 */
  DISPATCH = 'dispatch',
  /** 手动处理 */
  MANUAL_HANDLING = 'manual_handling',
  /** 批量屏蔽 */
  SHIELD = 'shield',
}

/** 进入页面后需要能自动打开展示dialog的事件 */
export const CAN_AUTO_SHOW_ALERT_DIALOG_ACTIONS = [AlertAllActionEnum.CONFIRM, AlertAllActionEnum.SHIELD];

/** 告警级别枚举 */
export enum AlertLevelEnum {
  /** 致命 */
  FATAL = 1,
  /** 提醒 */
  REMIND = 3,
  /** 预警 */
  WARNING = 2,
}

/** 告警详情-容器tab图表特殊辅助线series颜色映射 */
export const SpecialSeriesColorMap = {
  request: {
    color: '#FEA56B',
    labelColor: '#E38B02',
    itemColor: '#FDEED8',
  },
  limit: {
    color: '#FF5656',
    labelColor: '#E71818',
    itemColor: '#FFEBEB',
  },
  capacity: {
    color: '#4DA6FF', // 明亮的蓝色
    labelColor: '#0073E6', // 稍深的蓝色，用于标签
    itemColor: '#E6F2FF', // 非常浅的蓝色，用于背景
  },
};

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

/** 告警状态icon */
export const AlarmStatusIconMap = {
  ABNORMAL: {
    icon: 'icon-mind-fill',
    iconColor: '#F59789',
    name: window.i18n.t('未恢复'),
  },
  NOT_SHIELDED_ABNORMAL: {
    icon: 'icon-mind-fill',
    iconColor: '#F59789',
    name: window.i18n.t('未恢复（未屏蔽）'),
  },
  SHIELDED_ABNORMAL: {
    icon: 'icon-menu-shield',
    iconColor: '#F8B64F',
    name: window.i18n.t('未恢复（已屏蔽）'),
  },
  RECOVERED: {
    icon: 'icon-mc-check-fill',
    iconColor: '#6FC5BF',
    name: window.i18n.t('已恢复'),
  },
  CLOSED: {
    icon: 'icon-mc-close-fill',
    iconColor: '#DCDEE5',
    name: window.i18n.t('已失效'),
  },
};

/** 处理记录icon */
export const ActionIconMap = {
  success: {
    icon: 'icon-mc-check-fill',
    iconColor: '#6FC5BF',
  },
  failure: {
    icon: 'icon-mc-close-fill',
    iconColor: '#F59789',
  },
};

/** 故障icon */
export const IncidentIconMap = {
  MY_ASSIGNEE_INCIDENT: {
    icon: 'icon-gaojingfenpai',
    iconColor: '',
  },
  MY_HANDLER_INCIDENT: {
    icon: 'icon-chulitaocan1',
    iconColor: '',
  },
  abnormal: {
    icon: 'icon-mind-fill',
    iconColor: '#F59789',
  },
  closed: {
    icon: 'icon-mc-solved',
    iconColor: '#8E9BB3',
  },
  recovering: {
    icon: 'icon-mc-visual-fill',
    iconColor: '#F8B64F',
  },
  recovered: {
    icon: 'icon-mc-check-fill',
    iconColor: '#6FC5BF',
  },
  merged: {
    icon: 'icon-yihebing',
    iconColor: '#e24d42',
  },
};

export const AlarmLevelIconMap = {
  [AlertLevelEnum.FATAL]: {
    icon: 'rect',
    iconColor: '#E71818',
    text: window.i18n.t('致命'),
    textColor: '#E71818',
  },
  [AlertLevelEnum.WARNING]: {
    icon: 'rect',
    iconColor: '#E38B02',
    text: window.i18n.t('预警'),
    textColor: '#E38B02',
  },
  [AlertLevelEnum.REMIND]: {
    icon: 'rect',
    iconColor: '#3A84FF',
    text: window.i18n.t('提醒'),
    textColor: '#3A84FF',
  },
  ERROR: {
    icon: 'rect',
    iconColor: '#E71818',
    text: window.i18n.t('致命'),
    textColor: '#E71818',
  },
  WARN: {
    icon: 'rect',
    iconColor: '#E38B02',
    text: window.i18n.t('预警'),
    textColor: '#E38B02',
  },
  INFO: {
    icon: 'rect',
    iconColor: '#3A84FF',
    text: window.i18n.t('提醒'),
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
    alias: window.i18n.t('已恢复'),
  },
  CLOSED: {
    prefixIcon: 'alert-status-icon icon-monitor icon-shixiao',
    alias: window.i18n.t('已失效'),
  },
};

export const AlertDataTypeMap = {
  time_series: {
    prefixIcon: 'alert-description-icon icon-monitor icon-zhibiaojiansuo',
    alias: window.i18n.t('时序数据'),
  },
  event: {
    prefixIcon: 'alert-description-icon icon-monitor icon-shijianjiansuo',
    alias: window.i18n.t('事件'),
  },
  log: {
    prefixIcon: 'alert-description-icon icon-monitor icon-a-logrizhi',
    alias: window.i18n.t('日志'),
  },
};

export const AlertTargetTypeMap = {
  HOST: {
    prefixIcon: 'alert-target-icon icon-monitor icon-zhuji',
    alias: window.i18n.t('主机'),
  },
  SERVICE: {
    prefixIcon: 'alert-target-icon icon-monitor icon-fuwumokuai',
    alias: window.i18n.t('服务'),
  },
  'K8S-POD': {
    prefixIcon: 'alert-target-icon icon-monitor icon-mc-pod',
    alias: window.i18n.t('K8S-POD'),
  },
  'K8S-NODE': {
    prefixIcon: 'alert-target-icon icon-monitor icon-mc-bcs-node',
    alias: window.i18n.t('K8S-NODE'),
  },
  'K8S-SERVICE': {
    prefixIcon: 'alert-target-icon icon-monitor icon-mc-bcs-service',
    alias: window.i18n.t('K8S-SERVICE'),
  },
  'K8S-WORKLOAD': {
    prefixIcon: 'alert-target-icon icon-monitor icon-mc-bcs-workload',
    alias: window.i18n.t('K8S-WORKLOAD'),
  },
  'APM-SERVICE': {
    prefixIcon: 'alert-target-icon icon-monitor icon-APM',
    alias: window.i18n.t('APM服务'),
  },
};

export const ActionLevelIconMap = {
  running: {
    icon: 'rect',
    iconColor: '#A3C4FD',
  },
  success: {
    icon: 'rect',
    iconColor: '#8DD3B5',
  },
  failure: {
    icon: 'rect',
    iconColor: '#F59E9E',
  },
  skipped: {
    icon: 'rect',
    iconColor: '#FED694',
  },
  shield: {
    icon: 'rect',
    iconColor: '#CBCDD2',
  },
};

export const ActionStatusIconMap = {
  success: {
    prefixIcon: 'action-status-icon icon-monitor icon-mc-check-fill',
    alias: window.i18n.t('成功'),
  },
  running: {
    // TODO 待确认icon
    prefixIcon: 'action-status-icon icon-monitor',
    alias: window.i18n.t('执行中'),
  },
  failure: {
    prefixIcon: 'action-status-icon icon-monitor icon-mc-close-fill',
    alias: window.i18n.t('失败'),
  },
};

export const ActionFailureTypeMap = {
  shield: window.i18n.t('已屏蔽'),
  skipped: window.i18n.t('被收敛'),
  framework_code_failure: window.i18n.t('系统异常'),
  timeout: window.i18n.t('执行超时'),
  execute_failure: window.i18n.t('执行失败'),
  unknown: window.i18n.t('失败'),
};

export const IncidentLevelIconMap = {
  WARN: {
    icon: 'rect',
    iconColor: '#E38B02',
  },
  ERROR: {
    icon: 'rect',
    iconColor: '#E71818',
  },
  INFO: {
    icon: 'rect',
    iconColor: '#3A84FF',
  },
};

export const IncidentStatusIconMap = {
  abnormal: {
    alias: window.i18n.t('未恢复'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mind-fill',
  },
  recovering: {
    alias: window.i18n.t('观察中'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mc-visual-fill',
  },
  recovered: {
    alias: window.i18n.t('已恢复'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mc-check-fill',
  },
  closed: {
    alias: window.i18n.t('已解决'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mc-solved',
  },
  ABNORMAL: {
    alias: window.i18n.t('未恢复'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mind-fill',
  },
  RECOVERED: {
    alias: window.i18n.t('已恢复'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mc-check-fill',
  },
  CLOSED: {
    alias: window.i18n.t('已失效'),
    prefixIcon: 'incident-status-icon icon-monitor icon-mc-solved',
  },
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
/** common-table 表格检测是否内容溢出弹出 tip 功能类名 */
export const COMMON_TABLE_ELLIPSIS_CLASS_NAME = 'common-table-ellipsis';
