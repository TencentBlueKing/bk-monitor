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

import { TranslateResult } from 'vue-i18n';
import { random } from 'monitor-common/utils';

import {
  conditionFindReplace,
  conditionsDeduplication,
  conditionsInclues,
  mergeConditions,
  topNDataStrTransform
} from './condition';

export type ActionType = 'copy' | 'add' | 'delete' | 'reset' | 'batchDelete' | 'batchReset';
export type TContionType = 'and' | 'or';
export type TMthodType = 'eq' | 'neq' | 'include' | 'exclude' | 'reg' | 'nreg';
export type RuleStatusType = 'initial' | 'common' | 'change' | 'add' | 'verification';

export const CONDITIONS = [
  { id: 'and', name: 'AND' },
  { id: 'or', name: 'OR' }
];

export const METHODS = [
  { id: 'eq', name: '=' },
  { id: 'neq', name: '!=' },
  { id: 'include', name: 'include' },
  { id: 'exclude', name: 'exclude' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' }
];

export const LEVELLIST: LevelItem[] = [
  {
    value: 0,
    name: window.i18n.t('保持原样')
  },
  {
    value: 1,
    name: window.i18n.t('致命'),
    icon: 'icon-monitor icon-mc-chart-alert',
    color: '#EA3636'
  },
  {
    value: 2,
    name: window.i18n.t('预警'),
    icon: 'icon-monitor icon-mind-fill',
    color: '#FFB848'
  },
  {
    value: 3,
    name: window.i18n.t('提醒'),
    icon: 'icon-monitor icon-mind-fill',
    color: '#3A84FF'
  }
];

// interface IAlarmGroup {
//   name: string;
//   id: string;
// }

export interface ICondtionItem {
  /* 条件 */ field: string;
  value: string[];
  method: TMthodType;
  condition: TContionType;
}

interface IRuleDataItem {
  // 规则组每条规则的数据
  alarmGroups: number[]; // 告警组
  conditions: ICondtionItem[]; // 匹配规则
  notice: {
    // 通知
    isUpdate: boolean;
    time: number;
    group: string[];
  };
  actionConfig: string; // 流程(处理套餐)
  level: string; // 等级调整
}

interface IActionTtem {
  actionType: 'notice' | 'itsm';
  upgradeConfig?: {
    isEnabled: boolean;
    userGroups: number[];
    upgradeInterval: number;
  };
  isEnabled?: boolean;
  actionId?: number;
}

export interface IRuleGroup {
  isExpan: boolean;
  id: number;
  name: string;
  priority: number; // 优先级
  ruleData: IRuleDataItem[];
}

export interface LevelItem {
  value: Number;
  name: string | TranslateResult;
  icon?: string;
  color?: string;
}

export enum EColumn {
  select = 'select',
  userGroups = 'userGroups',
  conditions = 'conditions',
  // notice = 'notice',
  upgradeConfig = 'upgradeConfig',
  actionId = 'actionId',
  alertSeverity = 'alertSeverity',
  additionalTags = 'additionalTags',
  isEnabled = 'isEnabled',
  operate = 'operate',
  noticeProgress = 'noticeProgress',
  levelTag = 'levelTag'
}

export class RuleGroupData {
  isExpan = true;
  id = 0; // 规则组ID
  name = ''; // 规则名
  priority = 0;
  ruleData = [];
  settings = {};
  editAllowed = false;
  constructor(data: IRuleGroup) {
    const TEMP_THIS = JSON.parse(JSON.stringify(this));
    Object.keys(TEMP_THIS).forEach(key => {
      if (data?.[key]) {
        this[key] = data[key];
      }
    });
  }
  setExpan(v: boolean) {
    this.isExpan = v;
  }
  setRuleData(list) {
    this.ruleData = list.map(item => ({
      ...item,
      conditions: item.conditions.map(c => ({
        ...c,
        value: c.value.map(v => topNDataStrTransform(String(v)))
      }))
    }));
  }
}

export class RuleData {
  key = random(8);
  id = 0;
  isCheck = false; // 是否选中
  userGroups = []; // 告警组
  conditions = []; // 匹配规则
  conditionsRenderKey = random(8); // 主动刷新匹配规则
  actions: IActionTtem[] = [
    {
      actionType: 'notice',
      isEnabled: true,
      upgradeConfig: {
        isEnabled: false,
        userGroups: [],
        upgradeInterval: 0
      }
    }
  ];
  upgradeConfig = {
    // 通知
    noticeIsEnabled: true, // 关闭通知开关
    isEnabled: false, // 通知升级开关
    userGroups: [], // 通知升级告警组
    upgradeInterval: undefined // 时长
  };
  actionId = undefined; // 套餐id
  alertSeverity = 0; // 等级调整
  additionalTags = []; // 追加标签
  tag = [];
  isEnabled = false; // 开启
  tooltipsDisabled = false; // 操作栏Tooltips是否禁用
  addId = null;
  copyId = null;
  config = {
    userGroups: false,
    isEnabled: false,
    upgradeConfig: false,
    conditions: false,
    actionId: false,
    additionalTags: false,
    alertSeverity: false
  };
  verificatory = {
    userGroups: false,
    isEnabled: false,
    upgradeConfig: false,
    conditions: false,
    actionId: false,
    additionalTags: false,
    alertSeverity: false
  };
  validateTips = {
    userGroups: '',
    additionalTags: ''
  };
  conditionsRepeat = false; // 条件是否重复
  replaceData = [];

  constructor(data: any) {
    const TEMP_THIS = JSON.parse(JSON.stringify(this));
    Object.keys(TEMP_THIS).forEach(key => {
      if (data?.[key]) {
        if (key === 'actions') {
          data[key].forEach(action => {
            if (action.actionType === 'notice') {
              this.upgradeConfig = { ...action.upgradeConfig, noticeIsEnabled: action.isEnabled };
            } else if (action.actionType === 'itsm') {
              this.actionId = action.actionId;
            }
          });
        } else if (key === 'additionalTags') {
          this.tag = data[key].map(item => `${item.key}:${item.value}`);
        }
        if (key === 'conditions') {
          this.conditions = data[key].map(c =>
            // if (c.field === 'alert.strategy_id') {
            //   return {
            //     ...c,
            //     value: c.value.map(v => topNDataStrTransform(String(v)))
            //   };
            // }
            ({
              ...c,
              value: c.value.map(v => topNDataStrTransform(String(v)))
            })
          );
        } else {
          this[key] = data[key];
        }
      }
    });
  }

  /* 是否为初始状态 */
  get isInitData() {
    return !(
      this.config.userGroups ||
      this.config.isEnabled ||
      this.config.upgradeConfig ||
      this.config.conditions ||
      this.config.actionId ||
      this.config.additionalTags ||
      this.config.alertSeverity
    );
  }

  /* 是否为空状态 */
  get isNullData() {
    return (
      !this.userGroups.length &&
      !this.conditions.length &&
      !this.upgradeConfig.isEnabled &&
      this.upgradeConfig.noticeIsEnabled &&
      !this.actionId &&
      !this.alertSeverity &&
      !this.additionalTags.length &&
      this.isEnabled
    );
  }

  /* 是否通过检验 */
  get isVerifySuccess() {
    return !(this.verificatory.userGroups || this.verificatory.conditions || this.verificatory.additionalTags);
  }

  setCheck(value: boolean) {
    this.isCheck = value;
  }
  setActions(value, actionType: 'notice' | 'itsm') {
    if (actionType === 'notice') {
      const index = this.actions.findIndex(item => item.actionType === 'notice');
      index > -1
        ? (this.actions[index] = {
            actionType: 'notice',
            upgradeConfig: {
              isEnabled: value.isEnabled,
              userGroups: value.userGroups,
              upgradeInterval: value.upgradeInterval
            },
            isEnabled: value.noticeIsEnabled
          })
        : this.actions.push({
            actionType: 'notice',
            isEnabled: value.noticeIsEnabled,
            upgradeConfig: {
              isEnabled: value.isEnabled,
              userGroups: value.userGroups,
              upgradeInterval: value.upgradeInterval
            }
          });
      this.upgradeConfig = value;
    }

    if (actionType === 'itsm') {
      const index = this.actions.findIndex(item => item.actionType === 'itsm');
      index > -1
        ? (this.actions[index] = { actionType: 'itsm', actionId: value })
        : this.actions.push({
            actionType: 'itsm',
            actionId: value
          });
    }
  }

  setAdditionalTags(list: string[]) {
    // 兼容key:value 和key=value两种模式
    this.additionalTags = list.map(item => {
      if (item.indexOf('=') > -1) {
        return {
          key: item.split('=')[0],
          value: item.split('=')[1]
        };
      }
      return {
        key: item.split(':')[0],
        value: item.split(':')[1]
      };
    });
  }

  setConditions(v) {
    this.conditions = v;
  }
  /* 传给后台的参数  */
  getSubmitParams(params = {}) {
    return {
      ...params,
      id: this.id || undefined,
      user_groups: this.userGroups,
      conditions: this.conditions,
      actions: this.actions
        .map(a => {
          if (a.actionType === 'notice') {
            return {
              action_type: a.actionType,
              is_enabled: a.isEnabled,
              upgrade_config: {
                is_enabled: !!a.upgradeConfig?.isEnabled,
                user_groups: a.upgradeConfig?.userGroups || [],
                upgrade_interval: +(a.upgradeConfig?.upgradeInterval || 0)
              }
            };
          }
          return {
            action_type: a.actionType,
            action_id: a.actionId
          };
        })
        .filter(item => !(item.action_type === 'itsm' && !item.action_id)),
      alert_severity: this.alertSeverity,
      additional_tags: this.additionalTags.map(item => ({ key: item.key, value: item.value })),
      is_enabled: this.isEnabled
    };
  }
  /* 匹配规则查找替换 */
  setFindReplace(findData: ICondtionItem[], replaceData: ICondtionItem[], isUnshift = false) {
    if (findData.length) {
      this.conditions = conditionFindReplace(this.conditions, findData, replaceData, isUnshift);
      if (isUnshift) {
        this.conditions = mergeConditions(this.conditions);
      } else {
        this.conditions = conditionsDeduplication(this.conditions);
        this.replaceData = [...replaceData];
      }

      this.conditionsRenderKey = random(8);
      this.verificatory.conditions = !replaceData?.length;
    } else {
      this.replaceData = [];
    }
  }
  setUnifiedSettings(findData: ICondtionItem[], replaceData: ICondtionItem[], curConditions: ICondtionItem[]) {
    if (findData.length) {
      // 判断finddata 是否完整无差异包含在this.condition
      if (findData.every(item => conditionsInclues(item, curConditions))) {
        // eslint-disable-next-line max-len
        this.conditions = conditionsDeduplication(
          mergeConditions(conditionFindReplace(this.conditions, findData, replaceData, true))
        );
      } else {
        // 如果有差异就执行合并处理
        this.conditions = mergeConditions([...curConditions, ...replaceData]);
      }
      // this.conditions = mergeConditions(this.conditions);
      this.conditionsRenderKey = random(8);
      this.verificatory.conditions = !replaceData?.length;
    } else {
      this.replaceData = [];
    }
  }
  /* 统一设置时没有重复条件需往前添加新的条件 */
  unshiftConditions(conditions) {
    this.conditions.unshift(...conditions);
    this.conditions = conditionsDeduplication(this.conditions);
    this.conditions = mergeConditions(this.conditions);
    this.conditionsRenderKey = random(8);
  }
  /* 刷新条件 */
  conditionsRefresh() {
    this.conditionsRenderKey = random(8);
  }
  /** 设置复制规则id */
  setCopyID() {
    this.copyId = random(8);
  }
  setConfig(field: string, v: boolean) {
    this.config[field] = v;
  }

  setVerificatory(field: string, v: boolean, tips?: string | TranslateResult) {
    this.verificatory[field] = v;
    this.validateTips[field] = tips ? tips : '';
  }

  setConditionsRepeat(v: boolean) {
    this.conditionsRepeat = v;
  }

  setTooltipsDisabled(v: boolean) {
    this.tooltipsDisabled = v;
  }
  /* 调试前校验一次（告警组与匹配规则） */
  debugVerificatory() {
    if (!this.isNullData) {
      this.verificatory.userGroups = !this.userGroups.length;
      this.verificatory.conditions = !this.conditions.length;
      return this.verificatory.userGroups || this.verificatory.conditions;
    }
    return false;
  }

  setIsEnabled(v: boolean) {
    this.isEnabled = v;
  }
}

/**
 * @description 深度比较数据值是否相同
 * @param a 数据a
 * @param b 数据b
 * @returns 比较结果
 */
export function deepCompare(a: any, b: any) {
  // 基本数据类型判断
  if (a === null || typeof a !== 'object' || b === null || typeof b !== 'object') {
    return a === b;
  }
  // a,b 类型不一致
  if (Object.prototype.toString.call(a) !== Object.prototype.toString.call(b)) {
    return false;
  }

  // 判断是否是数组
  const isArray = Array.isArray(a);
  const propsALength = isArray ? a.length : Object.keys(Object.getOwnPropertyDescriptors(a)).length;
  const propsBLength = isArray ? b.length : Object.keys(Object.getOwnPropertyDescriptors(b)).length;
  // 判断a,b属性个数是否一致
  if (propsALength !== propsBLength) {
    return false;
  }

  // 遍历数组每一项是否相同
  if (isArray) {
    return a.every((item, index) => deepCompare(item, b[index]));
  }

  // 遍历对象属性是否相同
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  return Object.keys(a).every(key => deepCompare(a[key], b[key]));
}
