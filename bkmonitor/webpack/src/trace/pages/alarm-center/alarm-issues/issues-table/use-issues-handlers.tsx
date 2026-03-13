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

import { shallowRef } from 'vue';

import { Button, Dialog, Input } from 'bkui-vue';

import { type IssuePriority, IssuePriorityEnum, IssuesPriorityMap } from './typings';

import type { IUsePopoverTools } from '../../components/alarm-table/hooks/use-popover';
import type { IssueItem } from './typings';

export interface UseIssuesHandlersOptions {
  /** click popover 工具（基础设施依赖） */
  clickPopoverTools: IUsePopoverTools;
  /** 指派负责人回调 */
  assignEmit: (id: string, assignee: string[]) => void;
  /** 标记已解决回调 */
  markResolvedEmit: (id: string) => void;
  /** 优先级变更回调 */
  priorityChangeEmit: (id: string, priority: IssuePriority) => void;
  /** 显示 Issue 详情回调 */
  showDetailEmit: (id: string) => void;
}

export type UseIssuesHandlersReturnType = ReturnType<typeof useIssuesHandlers>;

/** 优先级选项列表 */
const PRIORITY_OPTIONS: IssuePriority[] = [
  IssuePriorityEnum.CRITICAL,
  IssuePriorityEnum.HIGH,
  IssuePriorityEnum.MEDIUM,
  IssuePriorityEnum.LOW,
];

/**
 * @description Issues 场景私有交互逻辑 hook
 * @param options - 外部回调和基础设施依赖
 * @returns 交互处理函数和弹窗渲染方法
 */
export const useIssuesHandlers = ({
  clickPopoverTools,
  showDetailEmit,
  assignEmit,
  markResolvedEmit,
  priorityChangeEmit,
}: UseIssuesHandlersOptions) => {
  // ===================== 指派弹窗状态 =====================

  /** 指派弹窗是否可见 */
  const assignDialogVisible = shallowRef(false);
  /** 当前指派目标 Issue */
  const assignTarget = shallowRef<IssueItem | null>(null);
  /** 指派负责人输入值 */
  const assignInputValue = shallowRef('');

  // ===================== 交互处理函数 =====================

  /**
   * @description 点击 Issue 名称展示详情抽屉
   * @param id - Issue ID
   */
  const handleShowDetail = (id: string) => {
    showDetailEmit(id);
  };

  /**
   * @description 点击负责人触发指派弹窗
   * @param row - 当前 Issue 行数据
   */
  const handleAssignClick = (row: IssueItem) => {
    assignTarget.value = row;
    assignInputValue.value = '';
    assignDialogVisible.value = true;
  };

  /**
   * @description 确认指派负责人
   */
  const handleAssignConfirm = () => {
    if (!assignInputValue.value?.trim() || !assignTarget.value) return;
    assignEmit(assignTarget.value.id, [assignInputValue.value.trim()]);
    assignDialogVisible.value = false;
    assignTarget.value = null;
    assignInputValue.value = '';
  };

  /**
   * @description 取消指派
   */
  const handleAssignCancel = () => {
    assignDialogVisible.value = false;
    assignTarget.value = null;
    assignInputValue.value = '';
  };

  /**
   * @description 标记 Issue 已解决
   * @param id - Issue ID
   */
  const handleMarkResolved = (id: string) => {
    markResolvedEmit(id);
  };

  /**
   * @description 优先级列点击，弹出优先级选择下拉菜单
   * @param e - 鼠标事件
   * @param row - 当前 Issue 行数据
   */
  const handlePriorityClick = (e: MouseEvent, row: IssueItem) => {
    const menuDom = (
      <div class='issues-priority-menu'>
        {PRIORITY_OPTIONS.map(priority => {
          const config = IssuesPriorityMap[priority];
          const isActive = row.priority === priority;
          return (
            <div
              key={priority}
              class={['priority-menu-item', { 'is-active': isActive }]}
              onClick={() => {
                priorityChangeEmit(row.id, priority);
                clickPopoverTools.hidePopover();
              }}
            >
              <i
                style={{ color: config.color }}
                class={`priority-icon ${config.prefixIcon}`}
              />
              <span class='priority-text'>{config.alias}</span>
            </div>
          );
        })}
      </div>
    ) as unknown as Element;

    clickPopoverTools.showPopover(e, menuDom, `${row.id}-priority`, { arrow: false });
  };

  // ===================== 弹窗 DOM 渲染 =====================

  /**
   * @description 渲染指派负责人 Dialog DOM（在组件 render 中以隐藏容器挂载）
   * @returns Dialog 渲染内容
   */
  const renderAssignDialog = () => (
    <Dialog
      width={400}
      v-slots={{
        default: () => (
          <div class='issues-assign-dialog-content'>
            <div class='assign-field'>
              <span class='assign-label'>
                {window.i18n.t('负责人')}
                <span class='required'>*</span>
              </span>
              <Input
                v-model={assignInputValue.value}
                placeholder={window.i18n.t('请输入')}
              />
            </div>
          </div>
        ),
        footer: () => (
          <div class='issues-assign-dialog-footer'>
            <Button
              style='margin-right: 8px'
              disabled={!assignInputValue.value?.trim()}
              theme='primary'
              onClick={handleAssignConfirm}
            >
              {window.i18n.t('确定')}
            </Button>
            <Button onClick={handleAssignCancel}>{window.i18n.t('取消')}</Button>
          </div>
        ),
      }}
      header-position='left'
      isShow={assignDialogVisible.value}
      title={window.i18n.t('指派负责人')}
      onUpdate:isShow={(v: boolean) => {
        assignDialogVisible.value = v;
      }}
    />
  );

  return {
    handleShowDetail,
    handleAssignClick,
    handleMarkResolved,
    handlePriorityClick,
    renderAssignDialog,
  } as const;
};
