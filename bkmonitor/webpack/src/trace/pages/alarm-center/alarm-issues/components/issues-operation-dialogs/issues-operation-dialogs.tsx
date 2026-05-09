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
  archiveIssues,
  assignIssues,
  followUpIssues,
  resolveIssues,
  showOperationResult,
  unArchiveIssues,
  unResolveIssues,
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
  IssuesBatchOperationResponse,
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
    success: (dialogType: IssuesBatchActionType, event: IssuesBatchOperationResponse) =>
      dialogType != null && event != null,
  },
  setup(props, { emit }) {
    /**
     * @description dialog 操作成功后统一回调，将子 dialog 返回的 succeeded 数组包装为 IssuesBatchOperationResponse
     * @param {IssuesBatchActionType} dialogType - dialog 类型
     * @param {IssuesBatchOperationResponse} event - dialog 操作成功后回调事件对象
     */
    const handleConfirmSuccess = (dialogType: IssuesBatchActionType, event: IssuesBatchOperationResponse) => {
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
     * @description 创建 dialog confirm 处理函数的工厂方法，统一封装 service 调用 → 结果提示 → resolve/reject 协议 → 成功回调
     * @param {object} config - 配置项
     * @param {Function} config.service - service 层异步函数
     * @param {Function} config.buildParams - 从 event.payload 构建请求参数的函数
     * @param {string} config.successMessage - 操作成功提示文案
     * @param {IssuesBatchActionType} config.dialogType - 对应的批量操作枚举值
     * @returns {Function} 可直接绑定到子 dialog onConfirm 的异步处理函数
     */
    const createConfirmHandler = <T extends Record<string, unknown> = Record<string, unknown>>(config: {
      buildParams: (payload: T) => Record<string, unknown>;
      dialogType: IssuesBatchActionType;
      service: (params: any) => Promise<IssuesBatchOperationResponse>;
      successMessage: string;
    }) => {
      return async (event: AsyncDialogConfirmEvent<T>) => {
        const res = await config.service({
          issues: props.issuesData,
          ...config.buildParams(event.payload),
        });
        const success = showOperationResult(res, config.successMessage);
        if (success) {
          event.resolve();
          handleConfirmSuccess(config.dialogType, res);
        } else {
          event.reject();
        }
      };
    };

    /** 标记已解决 dialog 的 confirm 回调 */
    const handleResolveConfirm = createConfirmHandler({
      service: resolveIssues,
      buildParams: () => ({}),
      successMessage: window.i18n.t('标记为已解决成功'),
      dialogType: IssuesBatchActionEnum.RESOLVE,
    });

    /** 指派负责人 dialog 的 confirm 回调 */
    const handleAssignConfirm = createConfirmHandler<{ assignee: string[] }>({
      service: assignIssues,
      buildParams: payload => ({ assignee: payload.assignee }),
      successMessage: window.i18n.t('指派责任人成功'),
      dialogType: IssuesBatchActionEnum.ASSIGN,
    });

    /** 修改优先级 dialog 的 confirm 回调 */
    const handlePriorityConfirm = createConfirmHandler<{ priority: IssuePriorityType }>({
      service: updateIssuesPriority,
      buildParams: payload => ({ priority: payload.priority }),
      successMessage: window.i18n.t('修改成功'),
      dialogType: IssuesBatchActionEnum.PRIORITY,
    });

    /** 添加跟进信息 dialog 的 confirm 回调 */
    const handleFollowUpConfirm = createConfirmHandler<{ content: string }>({
      service: followUpIssues,
      buildParams: payload => ({ content: payload.content }),
      successMessage: window.i18n.t('添加跟进信息成功'),
      dialogType: IssuesBatchActionEnum.FOLLOW_UP,
    });

    /** 重新打开 dialog 的 confirm 回调 */
    const handleUnresolveConfirm = createConfirmHandler({
      service: unResolveIssues,
      buildParams: () => ({}),
      successMessage: window.i18n.t('重新打开成功'),
      dialogType: IssuesBatchActionEnum.UNRESOLVE,
    });

    /** 归档 dialog 的 confirm 回调 */
    const handleArchiveConfirm = createConfirmHandler({
      service: archiveIssues,
      buildParams: () => ({}),
      successMessage: window.i18n.t('归档成功'),
      dialogType: IssuesBatchActionEnum.ARCHIVE,
    });

    /** 恢复归档 dialog 的 confirm 回调 */
    const handleUnarchiveConfirm = createConfirmHandler({
      service: unArchiveIssues,
      buildParams: () => ({}),
      successMessage: window.i18n.t('恢复成功'),
      dialogType: IssuesBatchActionEnum.UNARCHIVE,
    });

    return {
      handleConfirmSuccess,
      handleShowChange,
      handleResolveConfirm,
      handleAssignConfirm,
      handlePriorityConfirm,
      handleFollowUpConfirm,
      handleUnresolveConfirm,
      handleArchiveConfirm,
      handleUnarchiveConfirm,
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
        <IssuesResolveDialog
          isShow={this.dialogType === IssuesBatchActionEnum.UNRESOLVE && this.show}
          issuesData={this.issuesData}
          tip={this.issuesData?.length > 1 ? window.i18n.t('确认批量重新打开？') : window.i18n.t('确认重新打开？')}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handleUnresolveConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesResolveDialog
          isShow={this.dialogType === IssuesBatchActionEnum.ARCHIVE && this.show}
          issuesData={this.issuesData}
          tip={this.issuesData?.length > 1 ? window.i18n.t('确认批量归档？') : window.i18n.t('确认归档？')}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handleArchiveConfirm}
          onUpdate:isShow={this.handleShowChange}
        />
        <IssuesResolveDialog
          isShow={this.dialogType === IssuesBatchActionEnum.UNARCHIVE && this.show}
          issuesData={this.issuesData}
          tip={this.issuesData?.length > 1 ? window.i18n.t('确认批量恢复？') : window.i18n.t('确认恢复？')}
          onCancel={() => this.handleShowChange(false)}
          onConfirm={this.handleUnarchiveConfirm}
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
