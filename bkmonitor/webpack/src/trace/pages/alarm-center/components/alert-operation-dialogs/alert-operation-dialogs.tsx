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

import { type PropType, defineComponent, onMounted, provide, shallowReactive, shallowRef } from 'vue';

import * as authMap from 'monitor-pc/pages/event-center/authority-map';

import { getAuthorityMap, useAuthorityStore } from '../../../../store/modules/authority';
import ChatGroup from '../../../failure/alarm-detail/chat-group/chat-group';
import AlarmConfirmDialog from '../../common-detail/components/alarm-alert/alarm-confirm-dialog';
import QuickShieldDialog from '../../common-detail/components/alarm-alert/quick-shield-dialog';
import AlarmDispatchDialog from '../../common-detail/components/alarm-info/alarm-dispatch-dialog';
import ManualDebugStatusDialog from '../../common-detail/components/alarm-info/manual-debug-status-dialog';
import ManualProcessDialog from '../../common-detail/components/alarm-info/manual-process-dialog';
import { type AlertOperationDialogEvent, type AlertOperationDialogParams, AlertAllActionEnum } from '../../typings';

import type { IAuthority } from '../../../../typings/authority';

export default defineComponent({
  name: 'AlertOperationDialogs',
  props: {
    alarmBizId: {
      type: Number,
    },
    alarmIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    show: {
      type: Boolean,
      default: false,
    },
    dialogType: {
      type: String as PropType<AlertAllActionEnum>,
    },
    dialogParam: {
      type: Object as PropType<AlertOperationDialogParams>,
    },
  },
  emits: {
    'update:show': (value: boolean) => typeof value === 'boolean',
    confirm: (dialogType: AlertAllActionEnum, event: AlertOperationDialogEvent) => dialogType && event != null,
  },
  setup(_props, { emit }) {
    /** 查看 手动处理 确认提交后的处理状态 dialog 的显示状态 */
    const manualDebugShow = shallowRef(false);
    /** 手动操作 提交后生成对应的事件ID(用于后续查看手动处理操作状态) */
    const actionIds = shallowRef([]);
    /** 手动操作 提交时所选择的处理套餐信息 */
    const mealInfo = shallowRef(null);
    const authorityStore = useAuthorityStore();
    /** 操作权限信息(告警屏蔽dialog需要) */
    const authority = shallowReactive<IAuthority>({
      map: authMap,
      auth: {},
      showDetail: authorityStore.getAuthorityDetail,
    });

    provide('authority', authority);
    /**
     * @description 初始化权限信息
     */
    const initAuthority = async () => {
      authority.auth = await getAuthorityMap(authMap);
    };

    /**
     * @description dialog 操作成功后回调
     * @param {AlertAllActionEnum} dialogType dialog 类型
     * @param {AlertOperationDialogEvent} event dialog 操作成功后回调事件对象
     */
    const handleConfirmSuccess = (dialogType: AlertAllActionEnum, event: AlertOperationDialogEvent) => {
      if (!dialogType) return;
      emit('confirm', dialogType, event);
    };
    /**
     * @description dialog 显示状态切换回调
     * @param {boolean} v dialog 显示状态
     */
    const handleShowChange = v => {
      emit('update:show', v);
    };
    /**
     * @description 显示 查看 手动处理 确认提交后的处理状态 dialog
     * @param value 手动操作 提交后生成对应的事件ID(用于后续查看手动处理操作状态)
     */
    const handleDebugStatus = (value: number[]) => {
      actionIds.value = value;
      manualDebugShow.value = true;
    };
    /**
     * @description 手动操作 提交时所选择的处理套餐信息 修改回调
     * @param {IAlarmMealInfo} value 手动操作 提交时所选择的处理套餐信息
     */
    const handleMealInfo = value => {
      mealInfo.value = value;
    };
    /**
     * @description 手动处理操作状态 dialog 显示状态切换回调
     * @param {boolean} v 手动处理操作状态 dialog 显示状态
     */
    const handleManualDebugShowChange = (v: boolean) => {
      if (!v) {
        manualDebugShow.value = false;
        mealInfo.value = null;
        actionIds.value = [];
      }
      manualDebugShow.value = v;
    };

    onMounted(() => {
      initAuthority();
    });
    return {
      manualDebugShow,
      actionIds,
      mealInfo,
      handleConfirmSuccess,
      handleShowChange,
      handleDebugStatus,
      handleMealInfo,
      handleManualDebugShowChange,
    };
  },
  render() {
    return (
      <div
        style={{ display: 'none' }}
        class='alert-operation-dialogs'
      >
        <AlarmConfirmDialog
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          show={this.dialogType === AlertAllActionEnum.CONFIRM && this.show}
          onConfirm={e => this.handleConfirmSuccess(AlertAllActionEnum.CONFIRM, e)}
          onUpdate:show={this.handleShowChange}
        />
        <QuickShieldDialog
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          alarmShieldDetail={this.dialogParam?.alarmShieldDetail ?? []}
          show={this.dialogType === AlertAllActionEnum.SHIELD && this.show}
          onSuccess={e => this.handleConfirmSuccess(AlertAllActionEnum.SHIELD, e)}
          onUpdate:show={this.handleShowChange}
        />
        <AlarmDispatchDialog
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          show={this.dialogType === AlertAllActionEnum.DISPATCH && this.show}
          onSuccess={e => this.handleConfirmSuccess(AlertAllActionEnum.DISPATCH, e)}
          onUpdate:show={this.handleShowChange}
        />
        <ManualProcessDialog
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          show={this.dialogType === AlertAllActionEnum.MANUAL_HANDLING && this.show}
          onDebugStatus={this.handleDebugStatus}
          onMealInfo={this.handleMealInfo}
          onUpdate:show={this.handleShowChange}
        />
        <ManualDebugStatusDialog
          actionIds={this.actionIds}
          alarmBizId={this.alarmBizId}
          mealInfo={this.mealInfo}
          show={this.manualDebugShow}
          onUpdate:show={this.handleManualDebugShowChange}
        />
        <ChatGroup
          alarmEventName={this.dialogParam?.alertName ?? ''}
          alertIds={this.alarmIds}
          assignee={this.dialogParam?.assignee ?? []}
          show={this.dialogType === AlertAllActionEnum.CHAT && this.show}
          onShowChange={this.handleShowChange}
        />
      </div>
    );
  },
});
