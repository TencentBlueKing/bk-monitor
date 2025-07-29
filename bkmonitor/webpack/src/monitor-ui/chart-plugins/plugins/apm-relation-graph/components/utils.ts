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
    name: window.i18n.t('告警事件'),
  },
  {
    id: EDataType.ErrorRateCaller,
    name: window.i18n.t('主调错误率'),
  },
  {
    id: EDataType.ErrorRateCallee,
    name: window.i18n.t('被调错误率'),
  },
  {
    id: EDataType.ErrorRate,
    name: window.i18n.t('总调用错误率'),
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
  time: number;
  type: EAlarmType;
  value: number;
}
export const alarmBarChartDataTransform = (dataType: EDataType, series: any[]) => {
  if (dataType === EDataType.Alert) {
    /* 1：致命 2：预警  其他：无告警 */
    return (
      series?.[0]?.datapoints?.map(item => {
        if (item[0]) {
          const typeValue = item[0][0];
          const value = item[0][1];
          const time = item[1];
          let type = EAlarmType.green;
          if (typeValue === 1) {
            type = EAlarmType.red;
          } else if (typeValue === 2) {
            type = EAlarmType.yellow;
          } else if (value === null) {
            type = EAlarmType.gray;
          }
          return { type, time, value };
        }
        return {
          type: EAlarmType.gray,
          time: item[1],
          value: null,
        };
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
        if (typeValue === null) {
          type = EAlarmType.gray;
        } else if (typeValue > 0.75) {
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
      if (typeValue === null) {
        type = EAlarmType.gray;
      } else if (typeValue === 0) {
        type = EAlarmType.green;
      } else if (typeValue <= 0.1) {
        type = EAlarmType.yellow;
      }
      return { type, time, value: typeValue };
    }) || []
  );
};

function toFixedSixDecimalPlaces(num: number) {
  const result = num * 100;
  if (result < 1 && result > 0) {
    return `${Number.parseFloat(result.toFixed(4))}%`;
  }
  return `${result.toFixed(2)}%`;
}

export const getAlarmItemStatusTips = (dataType: EDataType, item: IAlarmDataItem) => {
  if (dataType === EDataType.Alert) {
    const textMap = {
      [EAlarmType.green]: window.i18n.t('无告警'),
      [EAlarmType.red]: window.i18n.t('致命'),
      [EAlarmType.yellow]: window.i18n.t('预警'),
      [EAlarmType.gray]: window.i18n.t('无请求数据'),
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
      [EAlarmType.gray]: window.i18n.t('无请求数据'),
    };
    return {
      color: alarmColorMap.default[item.type],
      text: textMap[item.type],
    };
  }
  const textMap = {
    [EAlarmType.green]: `${window.i18n.t('错误率')}：${toFixedSixDecimalPlaces(item.value)}%`,
    [EAlarmType.yellow]: `${window.i18n.t('错误率')}：${toFixedSixDecimalPlaces(item.value)}%`,
    [EAlarmType.red]: `${window.i18n.t('错误率')}：${toFixedSixDecimalPlaces(item.value)}%`,
    [EAlarmType.gray]: window.i18n.t('无请求数据'),
  };
  return {
    color: alarmColorMap.default[item.type],
    text: textMap[item.type],
  };
};

// 节点类型枚举
export enum CategoryEnum {
  ALL = 'all',
  ASYNC_BACKEND = 'async_backend',
  DB = 'db',
  HTTP = 'http',
  MESSAGING = 'messaging',
  OTHER = 'other',
  RPC = 'rpc',
}

// 规则是边缘样式 + 填充样式结合在一起返回
// solid_normal 比如这个就是 实线 + 正常
export enum NodeDisplayType {
  //  节点边缘样式: 虚线 DASHED / 实线 SOLID
  DASHED = 'dashed',
  // 节点填充样式 正常 normal / 残影 void
  NORMAL = 'normal',

  SOLID = 'solid',
  VOID = 'void',
}

export enum NodeDisplayTypeMap {
  DASHED_NORMAL = 'dashed_normal',
  DASHED_Void = 'dashed_void',
  SOLID_NORMAL = 'solid_normal',
  SOLID_VOID = 'solid_void',
}

export const nodeIconMap = {
  [CategoryEnum.HTTP]: '\ue6ff',
  [CategoryEnum.RPC]: '\ue707',
  [CategoryEnum.DB]: '\ue6fd',
  [CategoryEnum.MESSAGING]: '\ue702',
  [CategoryEnum.ASYNC_BACKEND]: '\ue703',
  [CategoryEnum.OTHER]: '\ue7a8',
};

export const nodeIconClass = {
  [CategoryEnum.HTTP]: 'icon-wangye',
  [CategoryEnum.RPC]: 'icon-yuanchengfuwu',
  [CategoryEnum.DB]: 'icon-shujuku',
  [CategoryEnum.MESSAGING]: 'icon-xiaoxizhongjianjian',
  [CategoryEnum.ASYNC_BACKEND]: 'icon-renwu',
  [CategoryEnum.OTHER]: 'icon-mc-service-unknown',
};

export const nodeLanguageMap = {
  webjs:
    'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGRhdGEtbmFtZT0iTGF5ZXIgMSIgdmlld0JveD0iMCAwIDI0IDI0Ij48cGF0aCBkPSJNMTQuNDc4IDE0Ljg4M2E0LjA2MSA0LjA2MSAwIDAgMS0yLjE4Ny0uMzk4IDEuNDM5IDEuNDM5IDAgMCAxLS41MzYtMS4wMS4yMjIuMjIyIDAgMCAwLS4yMjYtLjIyIDQ2LjgyNiA0Ni44MjYgMCAwIDAtLjk1IDAgLjIxMS4yMTEgMCAwIDAtLjIzMS4xODYgMi4zMzkgMi4zMzkgMCAwIDAgLjc1MyAxLjg0NCAzLjk5MSAzLjk5MSAwIDAgMCAyLjIyOC44MzkgOC4wNjIgOC4wNjIgMCAwIDAgMi41MzMtLjEwOCAzLjEyNiAzLjEyNiAwIDAgMCAxLjY3OC0uOTA0IDIuMzM4IDIuMzM4IDAgMCAwIC4zOTYtMi4yMzEgMS44NjkgMS44NjkgMCAwIDAtMS4yMy0xLjA5NWMtMS4yOC0uNDUtMi42NjQtLjQxNS0zLjk3LS43NTctLjIyNy0uMDctLjUwNC0uMTQ4LS42MDUtLjM4OGEuODU1Ljg1NSAwIDAgMSAuMjg0LS45NTUgMi41NTggMi41NTggMCAwIDEgMS4zNS0uMzM2IDQuMDcgNC4wNyAwIDAgMSAxLjg4My4yNyAxLjQzNiAxLjQzNiAwIDAgMSAuNjg3Ljk5Mi4yNDMuMjQzIDAgMCAwIC4yMjguMjM2Yy4zMTQuMDA2LjYyOC4wMDEuOTQzLjAwMmEuMjI4LjIyOCAwIDAgMCAuMjQ3LS4xNjggMi40MzQgMi40MzQgMCAwIDAtMS4xODctMi4xMDYgNS44OCA1Ljg4IDAgMCAwLTMuMjE4LS40OTMgMy41MDUgMy41MDUgMCAwIDAtMi4xNzYuODc1IDIuMTc1IDIuMTc1IDAgMCAwLS40MzQgMi4yNjIgMS45MyAxLjkzIDAgMCAwIDEuMjE4IDEuMDYyYzEuMjc3LjQ2MSAyLjY3Ni4zMTMgMy45NjQuNzIxLjI1Mi4wODUuNTQ0LjIxNi42MjEuNDk1YS45OS45OSAwIDAgMS0uMjcuOTQ2IDIuOTcgMi45NyAwIDAgMS0xLjc5My40Mzl6bTUuODE5LTguNDQ1cS0zLjczOC0yLjExNC03LjQ3OS00LjIyNWExLjY3NyAxLjY3NyAwIDAgMC0xLjYzNyAwTDMuNzMgNi40MjFhMS41NDIgMS41NDIgMCAwIDAtLjgwNSAxLjM0MnY4LjQ3NWExLjU1MyAxLjU1MyAwIDAgMCAuODM2IDEuMzU1Yy43MTMuMzg4IDEuNDA2LjgxNiAyLjEzMyAxLjE3OWEzLjA2NCAzLjA2NCAwIDAgMCAyLjczOC4wNzUgMi4xMjcgMi4xMjcgMCAwIDAgLjk5NS0xLjkyMWMuMDA1LTIuNzk3IDAtNS41OTQuMDAyLTguMzlhLjIyLjIyIDAgMCAwLS4yMDctLjI1NSA0MS41NTUgNDEuNTU1IDAgMCAwLS45NTMgMCAuMjEuMjEgMCAwIDAtLjIyOC4yMTNjLS4wMDQgMi43NzkuMDAxIDUuNTU4LS4wMDIgOC4zMzhhLjk0Ljk0IDAgMCAxLS42MS44ODMgMS41MzIgMS41MzIgMCAwIDEtMS4yNC0uMTY2bC0xLjk4Mi0xLjEyYS4yMzcuMjM3IDAgMCAxLS4xMzUtLjIzNVY3LjgwN2EuMjU5LjI1OSAwIDAgMSAuMTU3LS4yNnEzLjcxMy0yLjA5MiA3LjQyNS00LjE4N2EuMjU4LjI1OCAwIDAgMSAuMjkyIDBsNy40MjYgNC4xODZhLjI2Mi4yNjIgMCAwIDEgLjE1Ni4yNnY4LjM4OGEuMjQyLjI0MiAwIDAgMS0uMTM0LjIzOHEtMy42NTYgMi4wNjgtNy4zMTcgNC4xM2MtLjExNi4wNjQtLjI1NC4xNjktLjM5LjA5LS42NC0uMzYyLTEuMjctLjczOC0xLjkwOC0xLjEwM2EuMjA2LjIwNiAwIDAgMC0uMjMtLjAxNCA1LjIxOCA1LjIxOCAwIDAgMS0uODgyLjQxMmMtLjEzOC4wNTYtLjMwOC4wNzItLjQwMy4yYTEuMzE2IDEuMzE2IDAgMCAwIC40MzIuMzFsMi4yMzYgMS4yOTNhMS42MyAxLjYzIDAgMCAwIDEuNjU1LjA0NnEzLjcyNi0yLjEgNy40NTItNC4yMDRhMS41NTYgMS41NTYgMCAwIDAgLjgzNi0xLjM1NFY3Ljc2M2ExLjU0IDEuNTQgMCAwIDAtLjc3OC0xLjMyNXoiLz48L3N2Zz4=',
  cpp: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTQ0OCA2ODEuMzg3bDE3LjQ5MyAxMDQuMTA2Yy0xMS4wOTMgNS45NzQtMjkuMDEzIDExLjUyLTUyLjkwNiAxNi42NC0yNC4zMiA1LjU0Ny01Mi45MDcgOC41MzQtODUuNzYgOC41MzQtOTQuMjk0LTEuNzA3LTE2NS4xMi0yOS44NjctMjEyLjQ4LTgzLjYyNy00Ny43ODctNTQuMTg3LTcxLjY4LTEyMi44OC03MS42OC0yMDYuMDhDNDQuOCA0MjIuNCA3My4zODcgMzQ2Ljg4IDEyOCAyOTMuOTczYzU2LjMyLTUzLjMzMyAxMjYuMjkzLTgwLjY0IDIxMC43NzMtODAuNjQgMzIgMCA1OS43MzQgMi45ODcgODIuNzc0IDguMTA3czQwLjEwNiAxMC42NjcgNTEuMiAxNy4wNjdMNDQ4IDM0NC43NDdsLTQ1LjIyNy0xNC41MDdjLTE3LjA2Ni00LjI2Ny0zNi42OTMtNi40LTU5LjMwNi02LjQtNDkuNDk0LS40MjctOTAuNDU0IDE1LjM2LTEyMi40NTQgNDYuOTMzLTMyLjQyNiAzMS4xNDctNDkuMDY2IDc4LjkzNC01MC4zNDYgMTQyLjUwNyAwIDU4LjAyNyAxNS43ODYgMTAzLjI1MyA0Ni4wOCAxMzYuNTMzIDMwLjI5MyAzMi44NTQgNzIuOTYgNDkuOTIgMTI3LjU3MyA1MC4zNDdsNTYuNzQ3LTUuMTJjMTguMzQ2LTMuNDEzIDMzLjcwNi04LjEwNyA0Ni45MzMtMTMuNjUzbTIxLjMzMy0yMTIuMDU0aDg1LjMzNFYzODRINjQwdjg1LjMzM2g4NS4zMzN2ODUuMzM0SDY0MFY2NDBoLTg1LjMzM3YtODUuMzMzaC04NS4zMzR2LTg1LjMzNG0yOTguNjY3IDBoODUuMzMzVjM4NGg4NS4zMzR2ODUuMzMzSDEwMjR2ODUuMzM0aC04NS4zMzNWNjQwaC04NS4zMzR2LTg1LjMzM0g3Njh2LTg1LjMzNHoiIGZpbGw9IiM2MzY1NkUiLz48L3N2Zz4=',
  java: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTM3Ny41OTcgNzkxLjk5cy0zOS4yIDIyLjggMjcuOCAzMC40YzgxLjE5OCA5LjE5OSAxMjIuNTk4IDcuOTk5IDIxMS45OTctOSAwIDAgMjMuNiAxNC43OTkgNTYuMzk5IDI3LjU5OS0yMDAuMzk3IDg1Ljc5OS00NTMuNTk0LTUtMjk2LjE5Ni00OW0tMjQuNC0xMTIuMTk4cy00My44IDMyLjQgMjMuMiAzOS40Yzg2LjU5OSA5IDE1NS4xOTggOS42IDI3My41OTYtMTMuMiAwIDAgMTYuNCAxNi42IDQyLjIgMjUuNi0yNDIuNTk3IDcwLjk5OC01MTIuNTk0IDUuOC0zMzguOTk2LTUxLjhtMjA2LjM5Ny0xOTAuMTk3YzQ5LjQgNTYuNzk5LTEzIDEwNy45OTgtMTMgMTA3Ljk5OHMxMjUuMzk5LTY0LjggNjcuOC0xNDUuNzk4Yy01My44LTc1LjYtOTUtMTEzLjE5OCAxMjguMTk4LTI0Mi41OTcuMiAwLTM1MC4zOTUgODcuNi0xODIuOTk4IDI4MC4zOTdtMjY1LjE5NyAzODUuMTk0czI5IDIzLjgtMzEuOCA0Mi40Yy0xMTUuNzk4IDM1LTQ4MS41OTMgNDUuNi01ODMuMTkyIDEuNC0zNi42LTE1LjggMzItMzggNTMuNi00Mi42IDIyLjQtNC44IDM1LjQtNCAzNS40LTQtNDAuNi0yOC42LTI2Mi41OTggNTYuMi0xMTIuOCA4MC40IDQwOC4zOTUgNjYuMzk4IDc0NC43OS0yOS44IDYzOC43OTItNzcuNk0zOTYuMzk3IDU2My41OTNzLTE4Ni4xOTggNDQuMTk5LTY2IDYwLjE5OWM1MC44IDYuOCAxNTEuOTk4IDUuMiAyNDYuMTk3LTIuNiA3Ny02LjQgMTU0LjM5OC0yMC40IDE1NC4zOTgtMjAuNHMtMjcuMiAxMS42LTQ2LjggMjVjLTE4OC45OTcgNDkuOC01NTMuOTkyIDI2LjYtNDQ4Ljk5My0yNC4yIDg4Ljk5OC00Mi44IDE2MS4xOTgtMzggMTYxLjE5OC0zOE03MzAuMzkyIDc1MC4xOWMxOTIuMTk4LTk5LjggMTAzLjE5OS0xOTUuNzk3IDQxLjItMTgyLjc5OC0xNS4yIDMuMi0yMiA2LTIyIDZzNS42LTguOCAxNi40LTEyLjZjMTIyLjU5OC00My4yIDIxNi45OTcgMTI3LjE5OS0zOS42IDE5NC41OTggMC0uMiAzLTIuOCA0LTUuMk02MTQuMzk0IDBzMTA2LjM5OCAxMDYuMzk5LTEwMC45OTkgMjY5Ljk5NmMtMTY2LjE5OCAxMzEuMTk5LTM4IDIwNi4xOTggMCAyOTEuNTk3LTk2Ljk5OS04Ny42LTE2OC4xOTgtMTY0LjU5OC0xMjAuMzk4LTIzNi4zOTdDNDYzLjE5NiAyMjAuMTk2IDY1Ny4zOTMgMTY4Ljk5OCA2MTQuMzk0IDBNNDE1LjM5NiAxMDIwLjc4NmMxODQuMzk4IDExLjggNDY3LjU5NC02LjYgNDc0LjE5NC05My44IDAgMC0xMi44IDMzLTE1Mi4zOTggNTkuNC0xNTcuMzk4IDI5LjYtMzUxLjU5NSAyNi4yLTQ2Ni41OTQgNy4yIDAtLjIgMjMuNiAxOS40IDE0NC43OTggMjcuMiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
  dotnet:
    'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTEzNS4xMjggMzIyLjgxNnYzNzMuMjQ4aDQzLjY0OFY0MjYuMjRhMzgzLjEwNCAzODMuMTA0IDAgMCAwLTIuMDktNTEuMmgxLjY2M2ExMjQuMDc1IDEyNC4wNzUgMCAwIDAgMTEuODYyIDIzLjMzOWwxOTEuODcyIDI5Ny42ODVoNTMuNjMyVjMyMi44MTZoLTQzLjYwNnYyNjIuNDg1YTM5NC45NjUgMzk0Ljk2NSAwIDAgMCAyLjY0NiA1NC44N2gtLjk0YTM4NS40MDggMzg1LjQwOCAwIDAgMC0xNS4xNDYtMjQuOTZMMTkxLjgzMiAzMjIuODE2em0zOTcuNDQgMHYzNzMuMjQ4aDE5OC40bC4yMTMtNDAuOTZINTc3LjE5N1Y1MjUuNzM5SDcxMS45NFY0ODYuNEg1NzcuMTk3VjM2Mi4zMjVoMTQ0LjU5OHYtMzkuNTA5em0yMzIuMDIxIDB2MzkuNTFoMTA3LjI2NHYzMzMuNzM4aDQzLjYwNlYzNjIuMzY4aDEwOC41NDR2LTM5LjUxek0yNy44NjQgNjQyLjg1OWEyNy40MzUgMjcuNDM1IDAgMCAwLTE5LjQ1NiA4Ljc4OSAyOC42NzIgMjguNjcyIDAgMCAwLTguNDA1IDIwLjQ4IDI4LjI0NSAyOC4yNDUgMCAwIDAgOC40MDUgMjAuNDggMjcuNjQ4IDI3LjY0OCAwIDAgMCAyMC40OCA4LjU3NiAyOC4yNDUgMjguMjQ1IDAgMCAwIDIwLjQ4LTguNTc2IDI4LjAzMiAyOC4wMzIgMCAwIDAgOC41NzYtMjAuNDggMjguNDU5IDI4LjQ1OSAwIDAgMC04LjU3Ni0yMC40OCAyOC4wMzIgMjguMDMyIDAgMCAwLTIwLjQ4LTguNzkgMjcuNDM1IDI3LjQzNSAwIDAgMC0xLjAyNCAweiIgZmlsbD0iIzYzNjU2RSIvPjwvc3ZnPg==',
  go: 'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTc3LjI3IDQ1Ny4xNzNjLTIuMDA2IDAtMi40NzUtLjk4MS0xLjQ5NC0yLjUxN2wxMC40OTYtMTMuNDRjLjk4MS0xLjQ5MyAzLjQ1Ni0yLjQ3NSA1LjQ2MS0yLjQ3NUgyNjkuNzRjMS45NjIgMCAyLjQ3NCAxLjQ5NCAxLjQ5MyAyLjk4N2wtOC40OSAxMi45MjhjLS45ODIgMS41MzYtMy41IDIuOTg3LTQuOTkzIDIuOTg3bC0xODAuNDgtLjQ3ek0yLjAwNCA1MDMuMDRjLTIuMDA1IDAtMi41MTctLjk4MS0xLjQ5My0yLjQ3NWwxMC40NTMtMTMuNDgyYy45ODItMS40OTQgMy40OTktMi40NzUgNS41MDQtMi40NzVoMjI3LjMyOGMyLjAwNiAwIDIuOTg3IDEuNDkzIDIuNDc1IDIuOTg3bC0zLjk2OCAxMS45NDZjLS41MTIgMi4wMDYtMi40NzUgMi45ODctNC40OCAyLjk4N2wtMjM1LjgxOS41MTJ6bTEyMC42NjIgNDUuODY3Yy0yLjAwNiAwLTIuNTE4LTEuNDk0LTEuNDk0LTIuOTg3bDYuOTU1LTEyLjQ1OWMuOTgxLTEuNDkzIDIuOTg3LTIuOTg2IDQuOTkyLTIuOTg2aDk5LjcxMmMyLjAwNSAwIDIuOTg3IDEuNDkzIDIuOTg3IDMuNDk4bC0uOTgyIDExLjk0N2MwIDIuMDA1LTIuMDA1IDMuNDk5LTMuNDk4IDMuNDk5bC0xMDguNjcyLS41MTJ6TTY0MC4xNyA0NDguMjEzYy0zMS40MDMgNy45NzktNTIuODY0IDEzLjk1Mi04My43NTUgMjEuOTMxLTcuNTEgMS45NjMtNy45NzkgMi40NzUtMTQuNTA3LTQuOTkyLTcuNDI0LTguNDktMTIuOTI4LTEzLjk1Mi0yMy4zODEtMTguOTQ0LTMxLjQ0NS0xNS40NDUtNjEuODY3LTEwLjk2NS05MC4yNCA3LjQ2Ny0zMy45MiAyMS45My01MS4zNyA1NC4zNTctNTAuODU5IDk0LjcyLjQ3IDM5Ljg5MyAyNy45MDQgNzIuNzg5IDY3LjI4NiA3OC4yOTMgMzMuOTIgNC40OCA2Mi4yOTMtNy40NjcgODQuNzc4LTMyLjg5NiA0LjQ4LTUuNTA0IDguNDQ4LTExLjQ3NyAxMy40NC0xOC40NzVINDQ2LjcyYy0xMC40NTMgMC0xMi45Ny02LjQ4NS05LjQ3Mi0xNC45MzMgNi40ODUtMTUuNDQ1IDE4LjQzMi00MS4zODcgMjUuNDMtNTQuMzU3YTEzLjQ0IDEzLjQ0IDAgMCAxIDEyLjQ1OC03Ljk3OWgxODEuNDYxYy0uOTgxIDEzLjQ4My0uOTgxIDI2LjkyMy0yLjk4NiA0MC40MDVhMjEyLjYwOCAyMTIuNjA4IDAgMCAxLTQwLjg3NSA5Ny43MDdjLTM1Ljg4MyA0Ny4zNi04Mi43NzMgNzYuOC0xNDIuMDggODQuNzM2LTQ4Ljg1MyA2LjQ4NS05NC4yNS0yLjk4Ny0xMzQuMTAxLTMyLjg1My0zNi45MDctMjcuOTQ3LTU3Ljg1Ni02NC44NTQtNjMuMzE4LTExMC43Mi02LjQ4NS01NC4zNTggOS40NzItMTAzLjIxMSA0Mi4zNjgtMTQ2LjA5MSAzNS40MTQtNDYuMzM2IDgyLjI2Mi03NS43NzYgMTM5LjYwNi04Ni4yMyA0Ni44NDgtOC40OSA5MS43MzMtMi45ODYgMTMyLjA5NiAyNC40MDYgMjYuNDUzIDE3LjQ5MyA0NS4zNTQgNDEuMzg3IDU3Ljg1NiA3MC4zMTUgMi45ODYgNC40OC45ODEgNi45OTctNC45OTIgOC40OW0xNjUuMDM0IDI3NS43MTJjLTQ1LjM5Ny0xLjAyNC04Ni43ODQtMTMuOTk0LTEyMS42ODUtNDMuOTA0YTE1Ni4zNzMgMTU2LjM3MyAwIDAgMS01My44NDUtOTYuMjEzYy04Ljk2LTU2LjMyIDYuNDg1LTEwNi4xOTcgNDAuNDA1LTE1MC41NyAzNi4zOTUtNDcuODczIDgwLjI1Ni03Mi43OSAxMzkuNjA1LTgzLjI0MyA1MC44NTktOC45NiA5OC43MzEtNC4wMTEgMTQyLjA4IDI1LjQyOSAzOS4zODIgMjYuODggNjMuODMgNjMuMzE3IDcwLjMxNSAxMTEuMTQ3IDguNDQ4IDY3LjMyOC0xMC45NjUgMTIyLjE1NC01Ny4zNDQgMTY5LjA0NS0zMi44OTYgMzMuNDA4LTczLjMwMSA1NC4zMTUtMTE5LjY4IDYzLjc4Ny0xMy40NCAyLjUxNy0yNi44OCAyLjk4Ni0zOS44NSA0LjUyMnpNOTIzLjgyIDUyMi40OTZjLS40Ny02LjQ4NS0uNDctMTEuNDc3LTEuNDUxLTE2LjQ3LTguOTYtNDkuMzY1LTU0LjM1Ny03Ny4yNjktMTAxLjcxNy02Ni4zMDMtNDYuMzc5IDEwLjQ1My03Ni4yODggMzkuODkzLTg3LjI1NCA4Ni43NDEtOC45NiAzOC45MTIgOS45ODQgNzguMjkzIDQ1Ljg2NyA5NC4yNSAyNy40MzUgMTEuOTQ3IDU0LjgyNyAxMC40NTQgODEuMjgtMi45ODYgMzkuMzgxLTIwLjQ4IDYwLjgtNTIuMzUyIDYzLjMxNy05NS4yMzJ6IiBmaWxsPSIjNjM2NTZFIi8+PC9zdmc+',
  python:
    'data:image/svg+xml;base64,PHN2ZyBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCI+PHBhdGggZD0iTTEwMDIuMjEzIDM4NC42MDdjLTE3LjU1NS03MC4yMTktNTEuMDY4LTEyMi44ODMtMTIxLjI4Ny0xMjIuODgzaC05MC45NjV2MTA4LjUyYzAgODQuNTgyLTcxLjgxNSAxNTQuOC0xNTEuNjA5IDE1NC44aC0yNDQuMTdjLTY3LjAyNyAwLTEyMS4yODYgNTcuNDUyLTEyMS4yODYgMTI0LjQ4djIzMS40MDJjMCA2NS40MzEgNTcuNDUxIDEwNS4zMjggMTIxLjI4NiAxMjQuNDc5IDc2LjYwMyAyMi4zNDIgMTUxLjYxIDI3LjEzIDI0NC4xNyAwIDYwLjY0NC0xNy41NTUgMTIxLjI4Ny01NC4yNiAxMjEuMjg3LTEyNC40Nzl2LTkyLjU2MUg1MTUuNDd2LTMwLjMyMmgzNjUuNDU3YzcwLjIxOSAwIDk3LjM0OS00OS40NzIgMTIxLjI4Ny0xMjIuODgzIDI1LjUzNC03OS43OTQgMjUuNTM0LTE1My4yMDQgMC0yNTAuNTUzek02NTIuNzE1IDg0Ny40MTJjMjUuNTM0IDAgNDYuMjggMjAuNzQ3IDQ2LjI4IDQ2LjI4MXMtMjAuNzQ2IDQ2LjI4LTQ2LjI4IDQ2LjI4Yy0yNS41MzQgMS41OTYtNDYuMjgtMjAuNzQ2LTQ2LjI4LTQ2LjI4IDAtMjUuNTM0IDIwLjc0Ni00Ni4yOCA0Ni4yOC00Ni4yOHpNMzgzLjAxMSA0OTMuMTI3aDI0NC4xN2M2Ny4wMjcgMCAxMjEuMjg3LTU1Ljg1NiAxMjEuMjg3LTEyNC40NzlWMTM3LjI0NmMwLTY1LjQzMS01NS44NTYtMTE0LjkwNC0xMjEuMjg3LTEyNi4wNzUtODEuMzktMTIuNzY3LTE3MC43Ni0xMi43NjctMjQ0LjE3IDBDMjc5LjI4IDI4LjcyNiAyNjEuNzI0IDY3LjAyNyAyNjEuNzI0IDEzNy4yNDZ2OTIuNTZoMjQ0LjE3djMwLjMyM0gxNzAuNzZjLTcwLjIxOSAwLTEzMi40NTggNDMuMDg4LTE1MS42MDggMTIyLjg4Mi0yMi4zNDMgOTIuNTYxLTIzLjkzOSAxNTAuMDEzIDAgMjQ3LjM2MiAxNy41NTQgNzEuODE0IDU5LjA0NyAxMjIuODgzIDEyOS4yNjYgMTIyLjg4M2g4Mi45ODZWNjQxLjU0NGMtMS41OTYtNzguMTk4IDY4LjYyMy0xNDguNDE3IDE1MS42MDgtMTQ4LjQxN3ptLTE1Ljk1OS0zMjUuNTZjLTI1LjUzNCAwLTQ2LjI4LTIwLjc0Ni00Ni4yOC00Ni4yOCAwLTI1LjUzNCAyMC43NDYtNDYuMjggNDYuMjgtNDYuMjggMjUuNTM1IDAgNDYuMjgxIDIwLjc0NiA0Ni4yODEgNDYuMjhzLTIwLjc0NiA0Ni4yOC00Ni4yOCA0Ni4yOHoiIGZpbGw9IiM2MzY1NkUiLz48L3N2Zz4=',
};

export type EdgeDataType = 'duration_avg' | 'duration_p50' | 'duration_p95' | 'duration_p99' | 'request_count';
