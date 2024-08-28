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

export enum EAlarmType {
  blue = 3, // 提醒
  gray = 'no_data', // 无数据
  green = 'no_alarm', // 无告警
  red = 1, // 致命
  yellow = 2, // 预警
}
export enum EDataType {
  Alert = 'alert',
  Apdex = 'apdex',
  ErrorRate = 'error_rate',
  ErrorRateCallee = 'error_rate_callee',
  ErrorRateCaller = 'error_rate_caller',
}
export const DATA_TYPE_LIST = [
  {
    id: EDataType.Apdex,
    name: 'Apdex',
  },
  {
    id: EDataType.Alert,
    name: window.i18n.tc('告警事件'),
  },
  {
    id: EDataType.ErrorRateCaller,
    name: `${window.i18n.tc('调用错误率')} - ${window.i18n.tc('主调')}`,
  },
  {
    id: EDataType.ErrorRateCallee,
    name: `${window.i18n.tc('调用错误率')} - ${window.i18n.tc('被调')}`,
  },
  {
    id: EDataType.ErrorRate,
    name: window.i18n.tc('总调用错误率'),
  },
];

export const alarmColorMap = {
  default: {
    [EAlarmType.blue]: '#699DF4',
    [EAlarmType.gray]: '#EAEBF0',
    [EAlarmType.green]: '#2DCB56',
    [EAlarmType.red]: '#FF5656',
    [EAlarmType.yellow]: '#FFB848',
  },
  hover: {
    [EAlarmType.blue]: '#A3C5FD',
    [EAlarmType.gray]: '#EAEBF0',
    [EAlarmType.green]: '#81E09A',
    [EAlarmType.red]: '#F8B4B4',
    [EAlarmType.yellow]: '#FFD695',
  },
  selected: {
    [EAlarmType.blue]: '#3A84FF',
    [EAlarmType.gray]: '#EAEBF0',
    [EAlarmType.green]: '#11B33B',
    [EAlarmType.red]: '#EA3636',
    [EAlarmType.yellow]: '#FF9C01',
  },
};

export interface IAlarmDataItem {
  type: EAlarmType;
  time: number;
  value: number;
}
export const alarmBarChartDataTransform = (dataType: EDataType, series: any[]) => {
  if (dataType === EDataType.Alert) {
    /* 1：致命 2：预警  其他：无告警 */
    return (
      series?.[0]?.datapoints?.[0]?.map(item => {
        const typeValue = item[0][0];
        const value = item[0][1];
        const time = item[1];
        let type = EAlarmType.green;
        if (typeValue === 1) {
          type = EAlarmType.red;
        }
        if (typeValue === 2) {
          type = EAlarmType.yellow;
        }
        return { type, time, value };
      }) || []
    );
  }
  if (dataType === EDataType.Apdex) {
    return (
      series?.[0]?.datapoints?.map(item => {
        /* > 0.75: 满意(绿色)   <= 0.25: 烦躁(红色)  其他：可容忍(黄色)  */
        const typeValue = item[0];
        const time = item[1];
        let type = EAlarmType.yellow;
        if (typeValue > 0.75) {
          type = EAlarmType.green;
        } else if (typeValue <= 0.25) {
          type = EAlarmType.red;
        }
        return { type, time, value: typeValue };
      }) || []
    );
  }
  /* todo 调用错误率
    =0 绿色
    <= 0.1 黄色
    > 0.1 红色
  */
  return (
    series?.[0]?.datapoints?.map(item => {
      const typeValue = item[0];
      const time = item[1];
      let type = EAlarmType.red;
      if (typeValue === 0) {
        type = EAlarmType.green;
      } else if (typeValue <= 0.1) {
        type = EAlarmType.yellow;
      }
      return { type, time, value: typeValue };
    }) || []
  );
};

export const getAlarmItemStatusTips = (dataType: EDataType, item: IAlarmDataItem) => {
  if (dataType === EDataType.Alert) {
    const textMap = {
      [EAlarmType.green]: window.i18n.t('无告警'),
      [EAlarmType.red]: window.i18n.t('致命'),
      [EAlarmType.yellow]: window.i18n.t('预警'),
    };
    return {
      color: alarmColorMap.default[item.type],
      text: textMap[item.type],
    };
  }
  if (dataType === EDataType.Apdex) {
    const textMap = {
      [EAlarmType.yellow]: `${window.i18n.t('可容忍')}：0.25 < Apdex(${item.value}) <= 0.75`,
      [EAlarmType.green]: `${window.i18n.t('满意')}：Apdex(${item.value}) > 0.75`,
      [EAlarmType.red]: `${window.i18n.t('烦躁')}：Apdex(${item.value}) <= 0.25`,
    };
    return {
      color: alarmColorMap.default[item.type],
      text: textMap[item.type],
    };
  }
  const textMap = {
    [EAlarmType.green]: `${window.i18n.tc('错误率')}：0`,
    [EAlarmType.yellow]: `${window.i18n.tc('错误率')}：10%`,
    [EAlarmType.red]: `${window.i18n.tc('错误率')}：10%`,
  };
  return {
    color: alarmColorMap.default[item.type],
    text: textMap[item.type],
  };
};
