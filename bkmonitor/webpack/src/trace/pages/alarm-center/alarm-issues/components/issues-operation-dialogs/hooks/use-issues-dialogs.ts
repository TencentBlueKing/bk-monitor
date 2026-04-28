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

import { type Ref, shallowRef } from 'vue';

import { get } from '@vueuse/core';

import { IssuesBatchActionEnum, IssueStatusEnum } from '../../../constant';

import type {
  IssueIdentifier,
  IssueItem,
  IssuesBatchActionType,
  IssuesBatchOperationResponse,
  IssuesOperationDialogParams,
} from '../../../typing';

export type UseIssuesDialogsReturnType = ReturnType<typeof useIssuesDialogs>;

/**
 * @method useIssuesDialogs Issues 场景所有操作事件 dialog (指派、标记解决、修改优先级、跟进) 交互逻辑 hook
 * @description 集成弹窗交互状态管理与业务数据回写逻辑，配套 IssuesOperationDialogs 组件使用
 */
export const useIssuesDialogs = (
  /** 原始数据 */
  originalData: Ref<IssueItem[]>
) => {
  /** 是否显示 dialog */
  const issuesDialogShow = shallowRef(false);
  /** dialog 类型 */
  const issuesDialogType = shallowRef<IssuesBatchActionType>(undefined);
  /** 当前操作目标 Issue ID 数组 */
  const issuesDialogIds = shallowRef<string[]>([]);
  /** 各操作类型 dialog 个性化(私有)属性 */
  const issuesDialogParam = shallowRef<IssuesOperationDialogParams>(null);
  /** 跨业务批量操作 Issue 标识数据（{ bk_biz_id, issue_id }[]） */
  const issuesDialogData = shallowRef<IssueIdentifier[]>([]);

  /**
   * @description 通过 Issue IDs 从原始数据中获取操作数据对象数组
   * @param {string[]} ids - Issue ID 数组
   * @returns {IssueItem[]} 匹配的 Issue 数据数组
   */
  const getOperationalDataByIds = (ids: string[]): IssueItem[] => {
    const set = new Set(ids);
    return get(originalData).filter(item => set.has(item.id));
  };

  /**
   * @description 通过操作数据对象数组构建 IssueIdentifier 数组
   * @param {IssueItem[]} data - 操作数据对象数组
   * @returns {IssueIdentifier[]} 跨业务批量操作 Issue 标识数组
   */
  const buildIssueIdentifiers = (data: IssueItem[]): IssueIdentifier[] => {
    return data.map(item => ({ bk_biz_id: item.bk_biz_id, issue_id: item.id }));
  };

  /**
   * @description 根据 dialog 操作成功事件，直接更新对应 Issue 行对象属性（依赖 deepRef 深响应式追踪属性变化触发重渲染）
   * @param {Array<T>} succeeded - dialog 操作成功回调中的 succeeded 数组，每项必须包含 issue_id
   * @returns {void}
   */
  const updateIssueItems = <
    T extends { activities?: unknown; bk_biz_id?: IssueItem['bk_biz_id']; issue_id: IssueItem['id'] },
  >(
    succeeded: T[]
  ) => {
    if (!succeeded?.length) return;
    const updatesMap = new Map(
      succeeded.map(({ activities: _, bk_biz_id: __, issue_id, ...rest }) => [issue_id, rest])
    );
    for (const item of get(originalData)) {
      const updates = updatesMap.get(item.id);
      if (updates) {
        Object.assign(item, updates);
      }
    }
  };

  /**
   * @description 指派负责人
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleAssignDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.ASSIGN>
  ) => {
    updateIssueItems(event.succeeded);
  };

  /**
   * @description 标记已解决
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleResolvedDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.RESOLVE>
  ) => {
    const list = event.succeeded.map(item => ({ ...item, is_resolved: item.status === IssueStatusEnum.RESOLVED }));
    updateIssueItems(list);
  };

  /**
   * @description 重新打开
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleUnresolveDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.UNRESOLVE>
  ) => {
    const list = event.succeeded.map(item => ({ ...item, is_resolved: item.status === IssueStatusEnum.RESOLVED }));
    updateIssueItems(list);
  };

  /**
   * @description 归档
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleArchiveDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.ARCHIVE>
  ) => {
    updateIssueItems(event.succeeded);
  };

  /**
   * @description 恢复归档
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleUnarchiveDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.UNARCHIVE>
  ) => {
    updateIssueItems(event.succeeded);
  };

  /**
   * @description 优先级变更
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handlePriorityDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.PRIORITY>
  ) => {
    updateIssueItems(event.succeeded);
  };

  /**
   * @description 添加跟进信息（待审核状态下跟进后状态可能变为未解决，需更新表格行）
   * @param {IssuesBatchOperationResponse} event dialog回调事件对象
   */
  const handleFollowUpDialogSuccessCallback = (
    event: IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.FOLLOW_UP>
  ) => {
    updateIssueItems(event.succeeded);
  };

  /**
   * @description 通过 dialog类型 获取各dialog私有参数
   * @param {AlertAllActionEnum} dialogType dialog类型
   * @param {IssueItem[]} data 操作数据对象数组
   * @returns {AlertOperationDialogParams} dialog私有参数
   */
  const getDialogParamByDialogType = (
    dialogType: IssuesBatchActionType,
    data: IssueItem[]
  ): IssuesOperationDialogParams => {
    console.log('getDialogParamByDialogType', dialogType, data);
    return {};
  };

  /**
   * @description 显示 dialog（支持单条操作和批量操作）
   * @param {IssuesBatchActionType} type - dialog 类型
   * @param {string | string[]} idsOrId - Issue ID（单条时为 string）或 ID 数组（批量时为 string[]）
   * @param {IssueItem | IssueItem[]} data - 操作数据（可选，不传则从原始数据中查找）
   * @returns {boolean} 是否成功打开 dialog
   */
  const handleIssuesDialogShow = <T extends string | string[]>(
    type: IssuesBatchActionType,
    idsOrId: T,
    data?: T extends string[] ? IssueItem[] : IssueItem
  ): boolean => {
    const ids: string[] = Array.isArray(idsOrId) ? [...idsOrId] : [idsOrId];

    let operationalData: IssueItem[] = [];
    if (data) {
      operationalData = Array.isArray(data) ? data : [data];
    } else {
      // 批量操作需要从原始数据中循环一遍获取
      operationalData = getOperationalDataByIds(ids);
    }

    const dialogParam = getDialogParamByDialogType(type, operationalData);
    const issueIdentifiers = buildIssueIdentifiers(operationalData);

    issuesDialogData.value = issueIdentifiers;
    issuesDialogIds.value = ids;
    issuesDialogParam.value = dialogParam;
    issuesDialogType.value = type;
    issuesDialogShow.value = true;
    return true;
  };

  /**
   * @description 隐藏 dialog，重置所有弹窗状态
   */
  const handleIssuesDialogHide = () => {
    issuesDialogShow.value = false;
    issuesDialogType.value = undefined;
    issuesDialogParam.value = null;
    issuesDialogIds.value = [];
    issuesDialogData.value = [];
  };

  /**
   * @description dialog 提交操作成功后的回调事件，根据 dialogType 分发至对应业务方法
   * @param {IssuesBatchActionType} dialogType - dialog 类型
   * @param {IssuesBatchOperationResponse} event - dialog 回调事件对象
   */
  const handleIssuesDialogSuccess = <U extends IssuesBatchActionType>(
    dialogType: U,
    event: IssuesBatchOperationResponse<U>
  ) => {
    switch (dialogType) {
      case IssuesBatchActionEnum.ASSIGN:
        handleAssignDialogSuccessCallback(event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.ASSIGN>);
        break;
      case IssuesBatchActionEnum.RESOLVE:
        handleResolvedDialogSuccessCallback(
          event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.RESOLVE>
        );
        break;
      case IssuesBatchActionEnum.UNRESOLVE:
        handleUnresolveDialogSuccessCallback(
          event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.UNRESOLVE>
        );
        break;
      case IssuesBatchActionEnum.ARCHIVE:
        handleArchiveDialogSuccessCallback(event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.ARCHIVE>);
        break;
      case IssuesBatchActionEnum.UNARCHIVE:
        handleUnarchiveDialogSuccessCallback(
          event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.UNARCHIVE>
        );
        break;
      case IssuesBatchActionEnum.PRIORITY:
        handlePriorityDialogSuccessCallback(
          event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.PRIORITY>
        );
        break;
      case IssuesBatchActionEnum.FOLLOW_UP:
        handleFollowUpDialogSuccessCallback(
          event as IssuesBatchOperationResponse<typeof IssuesBatchActionEnum.FOLLOW_UP>
        );
        break;
      default:
        break;
    }

    handleIssuesDialogHide();
  };

  return {
    issuesDialogShow,
    issuesDialogType,
    issuesDialogData,
    issuesDialogParam,
    updateIssueItems,
    handleIssuesDialogShow,
    handleIssuesDialogHide,
    handleIssuesDialogSuccess,
  };
};
