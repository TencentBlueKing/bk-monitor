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

import { IssuesBatchActionEnum } from '../../constant';
import IssuesAssignDialog from '../issues-assign-dialog/issues-assign-dialog';
import IssuesFollowUpDialog from '../issues-follow-up-dialog/issues-follow-up-dialog';
import IssuesPriorityDialog from '../issues-priority-dialog/issues-priority-dialog';
import IssuesResolveDialog from '../issues-resolve-dialog/issues-resolve-dialog';

import type {
  IssueIdentifier,
  IssuesBatchActionType,
  IssuesOperationDialogEvent,
  IssuesOperationDialogParams,
} from '../../typing';

export default defineComponent({
  name: 'IssuesOperationDialogs',
  props: {
    /** 跨业务批量操作 Issue 标识数据 */
    issuesData: {
      type: Array as PropType<IssueIdentifier[]>,
      default: () => [],
    },
    /** 控制弹窗显隐 */
    show: {
      type: Boolean,
      default: false,
    },
    /** 当前激活的操作类型 */
    dialogType: {
      type: String as PropType<IssuesBatchActionType>,
    },
    /** 各操作类型 dialog 个性化(私有)属性 */
    dialogParam: {
      type: Object as PropType<IssuesOperationDialogParams>,
    },
  },
  emits: {
    'update:show': (value: boolean) => typeof value === 'boolean',
    success: (dialogType: IssuesBatchActionType, event: IssuesOperationDialogEvent) => dialogType && event != null,
  },
  setup(_props, { emit }) {
    /**
     * @description dialog 操作成功后统一回调，将子 dialog 返回的 succeeded 数组包装为 IssuesOperationDialogEvent
     * @param {IssuesBatchActionType} dialogType - dialog 类型
     * @param {IssuesOperationDialogEvent} event - dialog 操作成功后回调事件对象
     */
    const handleConfirmSuccess = (dialogType: IssuesBatchActionType, event: IssuesOperationDialogEvent) => {
      if (!dialogType) return;
      emit('success', dialogType, event);
    };

    /**
     * @description dialog 显示状态切换回调
     * @param {boolean} v - dialog 显示状态
     */
    const handleShowChange = (v: boolean) => {
      emit('update:show', v);
    };

    return {
      handleConfirmSuccess,
      handleShowChange,
    };
  },
  render() {
    return (
      <div
        style={{ display: 'none' }}
        class='issues-operation-dialogs'
      >
        <IssuesAssignDialog
          isShow={this.dialogType === IssuesBatchActionEnum.ASSIGN && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onSuccess={(event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.ASSIGN>) =>
            this.handleConfirmSuccess(IssuesBatchActionEnum.ASSIGN, event)
          }
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesResolveDialog
          isShow={this.dialogType === IssuesBatchActionEnum.RESOLVE && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onSuccess={(event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.RESOLVE>) =>
            this.handleConfirmSuccess(IssuesBatchActionEnum.RESOLVE, event)
          }
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesPriorityDialog
          dialogParam={this.dialogParam}
          isShow={this.dialogType === IssuesBatchActionEnum.PRIORITY && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onSuccess={(event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.PRIORITY>) =>
            this.handleConfirmSuccess(IssuesBatchActionEnum.PRIORITY, event)
          }
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesFollowUpDialog
          isShow={this.dialogType === IssuesBatchActionEnum.FOLLOW_UP && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onSuccess={(event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.FOLLOW_UP>) =>
            this.handleConfirmSuccess(IssuesBatchActionEnum.FOLLOW_UP, event)
          }
          onUpdate:isShow={this.handleShowChange}
        />
      </div>
    );
  },
});
