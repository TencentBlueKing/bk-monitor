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

import { type MaybeRef, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import { Message } from 'bkui-vue';

import {
  type AlertConfirmDialogEvent,
  type AlertDispatchDialogEvent,
  type AlertOperationDialogEvent,
  type AlertOperationDialogParams,
  type AlertShieldDialogEvent,
  type AlertTableItem,
  AlertAllActionEnum,
} from '../typings';

export type UseAlertDialogsReturnType = ReturnType<typeof useAlertDialogs>;

/**
 * @method useAlertDialogs 告警场景所有操作事件dialog(告警确认、手动处理、快捷屏蔽....) 交互逻辑hook
 * @description 配套 AlertOperationDialogs 组件使用
 */
export const useAlertDialogs = (
  /** 原始数据 */
  originalData: MaybeRef<AlertTableItem[]>
) => {
  /** 是否显示dialog */
  const alertDialogShow = shallowRef(false);
  /** dialog类型 */
  const alertDialogType = shallowRef<AlertAllActionEnum>(undefined);
  /** 告警业务id */
  const alertDialogBizId = shallowRef<number>(
    (window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined
  );
  /** 告警id数组 */
  const alertDialogIds = shallowRef<string[]>([]);
  /** 各操作类型 dialog 私有参数 */
  const alertDialogParam = shallowRef<AlertOperationDialogParams>(null);

  /**
   * @description 通过 告警id数组 从原始数据中获取操作数据对象数组
   * @param {string[]} ids 告警id数组
   * @returns {AlertTableItem[]} 操作数据对象数组
   */
  const getOperationalDataByIds = (ids: string[]) => {
    const set = new Set(ids);
    return get(originalData).filter(item => set.has(item.id));
  };

  /**
   * @description 通过 操作数据对象数组 获取告警业务id数组
   * @param {AlertTableItem[]} data 操作数据对象数组
   * @returns {number[]} 告警业务id数组
   */
  const getBizIdByOperationalData = (data: AlertTableItem[]) => {
    if (!data?.length) {
      return [];
    }
    const set = new Set(data.map(item => item.bk_biz_id));
    return Array.from(set);
  };

  /**
   * @description 通过 dialog类型 获取各dialog私有参数
   * @param {AlertAllActionEnum} dialogType dialog类型
   * @param {AlertTableItem[]} data 操作数据对象数组
   * @returns {AlertOperationDialogParams} dialog私有参数
   */
  const getDialogParamByDialogType = (
    dialogType: AlertAllActionEnum,
    data: AlertTableItem[]
  ): AlertOperationDialogParams => {
    if (![AlertAllActionEnum.SHIELD, AlertAllActionEnum.CHAT].includes(dialogType) || !data?.length) return null;
    if (dialogType === AlertAllActionEnum.SHIELD) {
      return {
        alarmShieldDetail: data.map(v => ({
          severity: v.severity,
          dimension: v.dimensions,
          trigger: v.description,
          alertId: v.id,
          strategy: {
            id: v?.strategy_id,
            name: v?.strategy_name,
          },
          bkHostId: v.bk_host_id,
        })),
      };
    }

    const assignees = data.reduce((prev, curr) => {
      for (const user of curr?.assignee ?? []) {
        // if (prev.has(user)) continue;
        prev.add(user);
      }
      return prev;
    }, new Set<string>());
    return {
      alertName: data?.length === 1 ? data[0].alert_name : '',
      assignee: Array.from(assignees),
    };
  };

  /**
   * @description 告警确认dialog 确认操作成功后回调事件
   * @param {AlertTableItem[]} data 操作数据对象数组
   */
  const handleConfirmDialogSuccessCallback = (data: AlertTableItem[], event: AlertConfirmDialogEvent) => {
    if (!event || !data?.length) return;
    for (const item of data) {
      item.is_ack = true;
      item.ack_operator = window.username || window.user_name;
    }
  };

  /**
   * @description 告警屏蔽dialog 确认操作成功后回调事件
   * @param {AlertTableItem[]} data 操作数据对象数组
   */
  const handleShieldDialogSuccessCallback = (data: AlertTableItem[], event: AlertShieldDialogEvent) => {
    if (!event || !data?.length) return;
    for (const item of data) {
      item.is_shielded = true;
      item.shield_operator = [window.username || window.user_name];
    }
  };

  /**
   * @description 告警派单dialog 确认操作成功后回调事件
   * @param {AlertTableItem[]} data 操作数据对象数组
   */
  const handleDispatchDialogSuccessCallback = (data: AlertTableItem[], event: AlertDispatchDialogEvent) => {
    if (!data?.length) return;
    for (const item of data) {
      if (item.appointee) {
        const usersSet = new Set([...(item.appointee ?? []), ...(event ?? [])]);
        item.appointee = Array.from(usersSet) as string[];
      } else {
        item.appointee = event;
      }
    }
  };

  /**
   * @description dialog确认提交成功后回调事件
   * @param {AlertAllActionEnum} dialogType dialog类型
   * @param {AlertOperationDialogEvent} event dialog回调事件对象
   */
  const handleAlertDialogConfirm = (dialogType: AlertAllActionEnum, event: AlertOperationDialogEvent) => {
    const operationalData = getOperationalDataByIds(get(alertDialogIds));
    if (!operationalData?.length) return;
    switch (dialogType) {
      case AlertAllActionEnum.CONFIRM:
        handleConfirmDialogSuccessCallback(operationalData, event as AlertConfirmDialogEvent);
        break;
      case AlertAllActionEnum.DISPATCH:
        handleDispatchDialogSuccessCallback(operationalData, event as AlertDispatchDialogEvent);
        break;
      case AlertAllActionEnum.SHIELD:
        handleShieldDialogSuccessCallback(operationalData, event as AlertShieldDialogEvent);
        break;
      default:
        break;
    }
  };

  /**
   * @description 显示dialog
   * @param {AlertAllActionEnum} type dialog类型
   * @param {string | string[]} id 告警id
   * @param {AlertTableItem | AlertTableItem[]} data 告警数据
   */
  const handleAlertDialogShow = <T extends string | string[]>(
    type: AlertAllActionEnum,
    id: T,
    data?: T extends string[] ? AlertTableItem[] : AlertTableItem
  ) => {
    const ids: string[] = Array.isArray(id) ? [...id] : [id];

    let operationalData: AlertTableItem[] = [];
    // 行内操作可以直接获取行数据，不需要从原始数据中循环一遍获取
    if (data) {
      operationalData = Array.isArray(data) ? data : [data];
    } else {
      // 批量操作需要从原始数据中循环一遍获取
      operationalData = getOperationalDataByIds(ids);
    }

    const bizIds = getBizIdByOperationalData(operationalData);
    const dialogParam = getDialogParamByDialogType(type, operationalData);

    if (type !== AlertAllActionEnum.CHAT && bizIds.length > 1) {
      Message({
        message: window.i18n.t('当前不能跨业务批量操作'),
        theme: 'warning',
      });
      return;
    }
    alertDialogBizId.value = bizIds[0];
    alertDialogIds.value = ids;
    alertDialogParam.value = dialogParam;
    alertDialogType.value = type;
    alertDialogShow.value = true;
  };
  /**
   * @description 隐藏dialog
   */
  const handleAlertDialogHide = () => {
    alertDialogShow.value = false;
    alertDialogType.value = null;
    alertDialogParam.value = null;
    alertDialogIds.value = [];
    alertDialogBizId.value = (window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined;
  };

  return {
    alertDialogShow,
    alertDialogType,
    alertDialogBizId,
    alertDialogIds,
    alertDialogParam,
    handleAlertDialogShow,
    handleAlertDialogHide,
    handleAlertDialogConfirm,
  };
};
