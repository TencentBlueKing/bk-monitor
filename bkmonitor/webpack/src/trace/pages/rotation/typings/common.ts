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

/**
 * 轮值下拉框类型
 */
export enum RotationSelectTypeEnum {
  /** 自定义 */
  Custom = 'custom',
  /** 每天 */
  Daily = 'daily',
  /** 指定时间 */
  DateRange = 'date_range',
  /** 每月 */
  Monthly = 'monthly',
  /** 周末 */
  Weekend = 'weekend',
  /** 每周 */
  Weekly = 'weekly',
  /** 工作日 */
  WorkDay = 'work_day',
}

/**
 * 轮值tab类型
 */
export enum RotationTabTypeEnum {
  /** 交替轮值 */
  HANDOFF = 'handoff',
  /** 固定值班 */
  REGULAR = 'regular',
}

/**
 * 轮值类型文本枚举
 */
export const RotationSelectTextMap = {
  [RotationSelectTypeEnum.WorkDay]: window.i18n.t('每工作日'),
  [RotationSelectTypeEnum.Weekend]: window.i18n.t('每周末'),
  [RotationSelectTypeEnum.Daily]: window.i18n.t('每天'),
  [RotationSelectTypeEnum.Weekly]: window.i18n.t('每周'),
  [RotationSelectTypeEnum.Monthly]: window.i18n.t('每月'),
  [RotationSelectTypeEnum.Custom]: window.i18n.t('自定义'),
  [RotationSelectTypeEnum.DateRange]: window.i18n.t('指定时间'),
};

/**
 * 周名称列表
 */
export const WeekNameList = [
  window.i18n.t('周一'),
  window.i18n.t('周二'),
  window.i18n.t('周三'),
  window.i18n.t('周四'),
  window.i18n.t('周五'),
  window.i18n.t('周六'),
  window.i18n.t('周日'),
];

/**
 * 周数据列表
 */
export const WeekDataList = [
  { id: 1, label: window.i18n.t('周一') },
  { id: 2, label: window.i18n.t('周二') },
  { id: 3, label: window.i18n.t('周三') },
  { id: 4, label: window.i18n.t('周四') },
  { id: 5, label: window.i18n.t('周五') },
  { id: 6, label: window.i18n.t('周六') },
  { id: 7, label: window.i18n.t('周日') },
];

export enum EStatus {
  Deactivated = 'Deactivated', // 已停用
  Effective = 'Effective', // 生效中
  NoEffective = 'NoEffective', // 已失效
  WaitEffective = 'WaitEffective', // 待生效
}

export const statusMap = {
  [EStatus.Effective]: window.i18n.t('生效中'),
  [EStatus.NoEffective]: window.i18n.t('已失效'),
  [EStatus.WaitEffective]: window.i18n.t('待生效'),
  [EStatus.Deactivated]: window.i18n.t('已停用'),
};

export function getEffectiveStatus(timeRange: string[], enabled: boolean) {
  if (!enabled) {
    return EStatus.Deactivated;
  }
  const timeRangeNum = timeRange.map(item =>
    item === 'null' || !item ? Number.POSITIVE_INFINITY : new Date(item).getTime()
  );
  const curTime = new Date().getTime();
  if (curTime < timeRangeNum[0]) {
    return EStatus.WaitEffective;
  }
  if (curTime >= timeRangeNum[0] && curTime <= timeRangeNum[1]) {
    return EStatus.Effective;
  }
  if (curTime > timeRangeNum[1]) {
    return EStatus.NoEffective;
  }
}
