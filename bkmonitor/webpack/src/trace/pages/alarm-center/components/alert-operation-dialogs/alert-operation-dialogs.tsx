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

import { type PropType, defineComponent } from 'vue';

import AlarmConfirmDialog from '../../common-detail/components/alarm-alert/alarm-confirm-dialog';
import QuickShieldDialog from '../../common-detail/components/alarm-alert/quick-shield-dialog';
import AlarmDispatch from '../../common-detail/components/alarm-info/alarm-dispatch';
import { type AlarmShieldDetail, AlertAllActionEnum } from '../../typings';

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
      type: Object as PropType<AlarmShieldDetail[]>,
    },
  },
  emits: {
    'update:show': (value: boolean) => typeof value === 'boolean',
  },
  setup(_props, { emit }) {
    const handleSuccess = () => {};
    /**
     * @description dialog 显示状态切换回调
     * @param {boolean} v dialog 显示状态
     */
    const handleShowChange = v => {
      emit('update:show', v);
    };
    return {
      handleSuccess,
      handleShowChange,
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
          onConfirm={this.handleSuccess}
          onUpdate:show={this.handleShowChange}
        />
        <QuickShieldDialog
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          alarmShieldDetail={this.dialogParam}
          show={this.dialogType === AlertAllActionEnum.SHIELD && this.show}
          onSuccess={this.handleSuccess}
          onUpdate:show={this.handleShowChange}
        />
        <AlarmDispatch
          alarmBizId={this.alarmBizId}
          alarmIds={this.alarmIds}
          show={this.dialogType === AlertAllActionEnum.DISPATCH && this.show}
          // onSuccess={this.handleSuccess}
          onUpdate:show={this.handleShowChange}
        />
      </div>
    );
  },
});
