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
import { type MaybeRef, shallowRef, useTemplateRef } from 'vue';

import { get } from '@vueuse/core';

import {
  type AlertContentItem,
  type AlertRowOperationAction,
  type AlertSelectBatchAction,
  type AlertTableItem,
  AlertAllActionEnum,
} from '../../../typings';

import type { UseAlertDialogsReturnType } from '../../../composables/use-alert-dialogs';
import type AlertContentDetail from '../components/alert-content-detail/alert-content-detail';
import type { IUsePopoverTools } from './use-popover';

export interface UseAlertHandlersOptions {
  clickPopoverTools: IUsePopoverTools;
  openDialogEmit: UseAlertDialogsReturnType['handleAlertDialogShow'];
  selectedRowKeys: MaybeRef<string[]>;
  clearSelected: () => void;
  showDetailEmit: (id: string) => void;
}

export type UseAlertHandlersReturnType = ReturnType<typeof useAlertHandlers>;

/**
 * @description 告警场景私有交互逻辑
 */
export const useAlertHandlers = ({
  clickPopoverTools,
  selectedRowKeys,
  clearSelected,
  showDetailEmit,
  openDialogEmit,
}: UseAlertHandlersOptions) => {
  /** 告警内容详情 popover 实例 ref */
  const alertContentDetailRef = useTemplateRef<InstanceType<typeof AlertContentDetail>>('alertContentDetailRef');
  /** 当前查看的告警内容详情数据 */
  const activeAlertContentDetail = shallowRef<AlertContentItem>(null);

  /**
   * @description: 展示 告警 详情抽屉
   */
  const handleAlertSliderShowDetail = (id: string) => {
    showDetailEmit(id);
  };

  /**
   * @description 打开告警内容详情 popover
   */
  const handleAlertContentDetailShow = (e: MouseEvent, row: AlertTableItem, colKey: string) => {
    activeAlertContentDetail.value = row?.items?.[0];
    clickPopoverTools.showPopover(e, () => alertContentDetailRef.value.$el, `${row.id}-${colKey}`, {
      onHidden: () => {
        activeAlertContentDetail.value = null;
      },
    });
  };

  /**
   * @description 告警行操作工具栏按钮点击回调事件
   */
  const handleAlertOperationClick = (actionType: AlertRowOperationAction, row: AlertTableItem) => {
    openDialogEmit(actionType, row.id, row);
  };

  /**
   * @description 告警批量设置
   */
  const handleAlertBatchSet = (actionType: AlertSelectBatchAction) => {
    if (actionType === AlertAllActionEnum.CANCEL) {
      clearSelected();
      return;
    }
    openDialogEmit(actionType, get(selectedRowKeys));
  };

  return {
    activeAlertContentDetail,
    handleAlertSliderShowDetail,
    handleAlertContentDetailShow,
    handleAlertOperationClick,
    handleAlertBatchSet,
  } as const;
};
