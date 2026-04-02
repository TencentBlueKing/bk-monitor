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
import {
  assignIssues,
  followUpIssues,
  resolveIssues,
  showOperationResult,
  updateIssuesPriority,
} from '../../services/issues-operations';
import IssuesAssignDialog from '../issues-assign-dialog/issues-assign-dialog';
import IssuesFollowUpDialog from '../issues-follow-up-dialog/issues-follow-up-dialog';
import IssuesPriorityDialog from '../issues-priority-dialog/issues-priority-dialog';
import IssuesResolveDialog from '../issues-resolve-dialog/issues-resolve-dialog';

import type { AsyncDialogConfirmEvent } from '../../hooks/use-async-dialog';
import type {
  IssueIdentifier,
  IssuePriorityType,
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
  setup(props, { emit }) {
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

    /**
     * @description 标记已解决 dialog 的 confirm 回调——接管 useAsyncDialog 的 { resolve, reject } 协议，
     *   调用 service 层发起请求，成功后 resolve 关闭弹窗，失败则 reject 保留弹窗让用户可重试。
     * @param {AsyncDialogConfirmEvent} event - useAsyncDialog 创建的确认事件对象
     * @returns {void}
     */
    const handleResolveConfirm = async (event: AsyncDialogConfirmEvent) => {
      try {
        const res = await resolveIssues({ issues: props.issuesData });
        showOperationResult(res, window.i18n.t('标记为已解决成功'));
        event.resolve();
        handleConfirmSuccess(IssuesBatchActionEnum.RESOLVE, res);
      } catch {
        event.reject();
      }
    };

    /**
     * @description 指派负责人 dialog 的 confirm 回调——接管 useAsyncDialog 的 { resolve, reject } 协议，
     *   调用 service 层发起请求，成功后 resolve 关闭弹窗，失败则 reject 保留弹窗让用户可重试。
     * @param {AsyncDialogConfirmEvent<{ assignee: string[] }>} event - useAsyncDialog 创建的确认事件对象
     * @returns {void}
     */
    const handleAssignConfirm = async (event: AsyncDialogConfirmEvent<{ assignee: string[] }>) => {
      try {
        const res = await assignIssues({
          issues: props.issuesData,
          assignee: event.payload.assignee,
        });
        showOperationResult(res, window.i18n.t('指派责任人成功'));
        event.resolve();
        handleConfirmSuccess(IssuesBatchActionEnum.ASSIGN, res);
      } catch {
        event.reject();
      }
    };

    /**
     * @description 修改优先级 dialog 的 confirm 回调——接管 useAsyncDialog 的 { resolve, reject } 协议，
     *   调用 service 层发起请求，成功后 resolve 关闭弹窗，失败则 reject 保留弹窗让用户可重试。
     * @param {AsyncDialogConfirmEvent<{ priority: IssuePriorityType }>} event - useAsyncDialog 创建的确认事件对象
     * @returns {void}
     */
    const handlePriorityConfirm = async (event: AsyncDialogConfirmEvent<{ priority: IssuePriorityType }>) => {
      try {
        const res = await updateIssuesPriority({
          issues: props.issuesData,
          priority: event.payload.priority,
        });
        showOperationResult(res, window.i18n.t('修改成功'));
        event.resolve();
        handleConfirmSuccess(IssuesBatchActionEnum.PRIORITY, res);
      } catch {
        event.reject();
      }
    };

    /**
     * @description 添加跟进信息 dialog 的 confirm 回调——接管 useAsyncDialog 的 { resolve, reject } 协议，
     *   调用 service 层发起请求，成功后 resolve 关闭弹窗，失败则 reject 保留弹窗让用户可重试。
     * @param {AsyncDialogConfirmEvent<{ content: string }>} event - useAsyncDialog 创建的确认事件对象
     * @returns {void}
     */
    const handleFollowUpConfirm = async (event: AsyncDialogConfirmEvent<{ content: string }>) => {
      try {
        const res = await followUpIssues({
          issues: props.issuesData,
          content: event.payload.content,
        });
        showOperationResult(res, window.i18n.t('添加跟进信息成功'));
        event.resolve();
        handleConfirmSuccess(IssuesBatchActionEnum.FOLLOW_UP, res);
      } catch {
        event.reject();
      }
    };

    return {
      handleConfirmSuccess,
      handleShowChange,
      handleResolveConfirm,
      handleAssignConfirm,
      handlePriorityConfirm,
      handleFollowUpConfirm,
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
          onConfirm={this.handleAssignConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesResolveDialog
          isShow={this.dialogType === IssuesBatchActionEnum.RESOLVE && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handleResolveConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesPriorityDialog
          dialogParam={this.dialogParam}
          isShow={this.dialogType === IssuesBatchActionEnum.PRIORITY && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handlePriorityConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesFollowUpDialog
          isShow={this.dialogType === IssuesBatchActionEnum.FOLLOW_UP && this.show}
          issuesData={this.issuesData}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handleFollowUpConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
      </div>
    );
  },
});
