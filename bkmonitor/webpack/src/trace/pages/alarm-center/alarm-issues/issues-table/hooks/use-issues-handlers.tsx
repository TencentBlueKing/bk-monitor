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

import { IssuePriorityEnum, IssuesPriorityMap } from '../../constant';

import type { IUsePopoverTools } from '../../../components/alarm-table/hooks/use-popover';
import type { ImpactScopeEvent, IssueItem, IssuePriorityType } from '../../typing';

export interface UseIssuesHandlersOptions {
  /** click popover 工具（基础设施依赖） */
  clickPopoverTools: IUsePopoverTools;
  /** 点击指派按钮回调 */
  assignClickEmit: (id: IssueItem['id'], row: IssueItem) => void;
  /** 影响范围资源类型点击回调 */
  impactScopeClickEmit: (event: ImpactScopeEvent) => void;
  /** 标记已解决回调 */
  markResolvedEmit: (id: string) => void;
  /** 优先级变更回调 */
  priorityChangeEmit: (id: string, priority: IssuePriorityType) => void;
  /** 显示 Issue 详情回调 */
  showDetailEmit: (id: string) => void;
}

export type UseIssuesHandlersReturnType = ReturnType<typeof useIssuesHandlers>;

/** 优先级选项列表 */
const PRIORITY_OPTIONS: IssuePriorityType[] = [IssuePriorityEnum.P0, IssuePriorityEnum.P1, IssuePriorityEnum.P2];

/**
 * @description Issues 场景私有交互逻辑 hook
 * @param {UseIssuesHandlersOptions} options - 外部回调和基础设施依赖
 * @returns {UseIssuesHandlersReturnType} 交互处理函数和弹窗渲染方法
 */
export const useIssuesHandlers = ({
  clickPopoverTools,
  showDetailEmit,
  assignClickEmit,
  markResolvedEmit,
  priorityChangeEmit,
  impactScopeClickEmit,
}: UseIssuesHandlersOptions) => {
  /**
   * @description 点击 Issue 名称展示详情抽屉
   * @param {IssueItem} row - 当前 Issue 行数据
   */
  const handleShowDetail = (row: IssueItem) => {
    showDetailEmit(row.id);
  };

  /**
   * @description 点击负责人触发指派（将行数据交由上层处理弹窗）
   * @param {IssueItem} row - 当前 Issue 行数据
   */
  const handleAssignClick = (row: IssueItem) => {
    assignClickEmit(row.id, row);
  };

  /**
   * @description 标记 Issue 已解决
   * @param {IssueItem} row - 当前 Issue 行数据
   */
  const handleMarkResolved = (row: IssueItem) => {
    // 如果 Issue 已解决，不触发
    if (row.is_resolved) return;
    markResolvedEmit(row.id);
  };

  /**
   * @description 点击影响范围中某个资源类型的数量，触发侧滑展示该资源类型的实例列表
   * @param {ImpactScopeEvent} event. - 影响范围点击事件对象
   */
  const handleImpactScopeClick = (event: ImpactScopeEvent) => {
    impactScopeClickEmit(event);
  };

  /**
   * @description 优先级列点击，弹出优先级选择下拉菜单
   * @param {MouseEvent} e - 鼠标事件
   * @param {IssueItem} row - 当前 Issue 行数据
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
              <span
                style={{
                  backgroundColor: config.bgColor,
                  color: config.color,
                }}
                class='priority-tag'
              >
                {config.alias}
              </span>
            </div>
          );
        })}
      </div>
    ) as unknown as Element;

    clickPopoverTools.showPopover(e, menuDom, `${row.id}-priority`, { arrow: false, offset: [0, 4] });
  };

  return {
    handleShowDetail,
    handleAssignClick,
    handleMarkResolved,
    handlePriorityClick,
    handleImpactScopeClick,
  } as const;
};
