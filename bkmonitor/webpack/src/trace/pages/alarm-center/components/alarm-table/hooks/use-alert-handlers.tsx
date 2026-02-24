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
  type AlertContentNameEditInfo,
  type AlertRowOperationAction,
  type AlertSelectBatchAction,
  type AlertTableItem,
  AlertAllActionEnum,
} from '../../../typings';
import AlertContentDetail, {
  type AlertSavePromiseEvent,
} from '../components/alert-content-detail/alert-content-detail';

import type { UseAlertDialogsReturnType } from '../../../composables/use-alert-dialogs';
import type { IUsePopoverTools } from './use-popover';

export interface UseAlertHandlersOptions {
  /** 点击 popover 工具栏 */
  clickPopoverTools: IUsePopoverTools;
  /** 打开交互弹窗回调(如：告警确认、告警屏蔽、告警分派、手动处理) */
  openDialogEmit: UseAlertDialogsReturnType['handleAlertDialogShow'];
  /** 表格选中的行 key */
  selectedRowKeys: MaybeRef<string[]>;
  /** 清除表格选中的行 */
  clearSelected: () => void;
  /** 保存告警内容数据含义回调 */
  saveContentNameEmit: (saveInfo: AlertContentNameEditInfo, savePromiseEvent: AlertSavePromiseEvent) => void;
  /** 显示告警详情抽屉回调 */
  showDetailEmit: (id: string, defaultTab?: string) => void;
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
  saveContentNameEmit,
}: UseAlertHandlersOptions) => {
  /** 告警内容详情 popover 实例 ref */
  const alertContentDetailRef = useTemplateRef<InstanceType<typeof AlertContentDetail>>('alertContentDetailRef');
  /** 当前告警记录所处的业务 ID */
  const activeBizId = shallowRef();
  /** 当前查看的告警记录 id */
  const activeAlertId = shallowRef<string>('');
  /** 当前查看的告警内容详情数据 */
  const activeAlertContentDetail = shallowRef<AlertContentItem>(null);
  /** 是否正在保存告警内容名称 */
  const isSaveContentNameActive = shallowRef(false);

  /**
   * @description: 展示 告警 详情抽屉
   */
  const handleAlertSliderShowDetail = (id: string, defaultTab?: string) => {
    showDetailEmit(id, defaultTab);
  };

  /**
   * @description 打开告警内容详情 popover
   */
  const handleAlertContentDetailShow = (e: MouseEvent, row: AlertTableItem, colKey: string) => {
    if (isSaveContentNameActive.value) return;
    activeAlertContentDetail.value = row?.items?.[0];
    activeBizId.value = row.bk_biz_id;
    activeAlertId.value = row.id;
    clickPopoverTools.showPopover(e, () => alertContentDetailRef.value.$el, `${row.id}-${colKey}`, {
      onHide: () => (isSaveContentNameActive.value ? false : void 0),
      onHidden: () => {
        activeBizId.value = void 0;
        activeAlertId.value = '';
        activeAlertContentDetail.value = null;
      },
    });
  };

  /**
   * @description 保存告警内容数据含义
   * @param {AlertContentNameEditInfo} saveInfo 保存信息
   * @param {AlertSavePromiseEvent} savePromiseEvent 保存事件
   */
  const handleSaveContentName = (saveInfo: AlertContentNameEditInfo, savePromiseEvent: AlertSavePromiseEvent) => {
    isSaveContentNameActive.value = true;
    savePromiseEvent?.promiseEvent
      ?.then(() => {
        isSaveContentNameActive.value = false;
      })
      .catch(() => {
        isSaveContentNameActive.value = false;
      });
    saveContentNameEmit(saveInfo, savePromiseEvent);
  };

  /**
   * @description 告警行操作工具栏按钮点击回调事件
   */
  const handleAlertOperationClick = (actionType: AlertRowOperationAction, row: AlertTableItem) => {
    clickPopoverTools.hidePopover();
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

  /**
   * @description 告警场景私有交互 DOM 渲染入口
   */
  const renderAlertHandlerDom = () => (
    <AlertContentDetail
      ref='alertContentDetailRef'
      alertContentDetail={activeAlertContentDetail.value}
      alertId={activeAlertId.value}
      bizId={activeBizId.value}
      onSave={handleSaveContentName}
    />
  );

  return {
    handleAlertSliderShowDetail,
    handleAlertContentDetailShow,
    handleAlertOperationClick,
    handleAlertBatchSet,
    renderAlertHandlerDom,
  } as const;
};
