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
import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';
import { Button, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import CollectionCrontab from '../components/collection/collection-crontab';
import {
  collectionMethodLabels,
  collectionTypeLabels,
  deploymentStatusLabels,
  isTaskDeleteBlocked,
  scheduleLabels,
} from '../utils/collection';
import { ExploreTableColumnTypeEnum } from '@/pages/trace-explore/components/trace-explore-table/typing';

import type { CollectionTask, CollectionTaskTableColumn } from '../types/collection';
import type {
  BaseTableColumn,
  TableCellRenderContext,
} from '@/pages/trace-explore/components/trace-explore-table/typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** useCollectionTaskColumnsRenderer 入参：渲染依赖的状态 + 行操作回调 */
export type CollectionTaskColumnsRendererCtx = {
  /** 是否有任务正在执行操作，期间禁用所有行操作 */
  busy: MaybeRef<boolean>;
  /** 删除任务 */
  onDelete: (row: CollectionTask) => void;
  /** 打开任务详情 */
  onDetail: (row: CollectionTask) => void;
  /** 编辑任务 */
  onEdit: (row: CollectionTask) => void;
  /** 立即执行任务 */
  onExecute: (row: CollectionTask) => void;
  /** 查看执行记录 */
  onHistory: (row: CollectionTask) => void;
  /** 切换任务启停状态 */
  onToggle: (row: CollectionTask) => void;
  /** 是否只读，只读时禁用所有写操作 */
  readonly: MaybeRef<boolean>;
};

/**
 * @description 任务管理表格列渲染器 hook，负责将外部列配置与各列的自定义渲染逻辑合并
 * @param {CollectionTaskColumnsRendererCtx} rendererCtx - 渲染依赖的状态及行操作回调
 * @returns {{ transformColumns: (columns: CollectionTaskTableColumn[]) => BaseTableColumn[] }} 列转换函数
 */
export const useCollectionTaskColumnsRenderer = (rendererCtx: CollectionTaskColumnsRendererCtx) => {
  const { t } = useI18n();

  /**
   * @description 执行时间列渲染（周期任务展示 crontab 表达式，单次任务复用 TIME 类型渲染执行时刻）
   * @param {CollectionTask} row - 当前行任务数据
   * @param {BaseTableColumn} column - 列配置，通过 getRenderValue 读取单次任务的执行时间
   * @param {TableCellRenderContext} renderCtx - 表格单元格渲染上下文，提供 TIME 类型渲染函数
   * @returns {SlotReturnValue} 执行时间列 JSX
   */
  const renderScheduleTime = (
    row: CollectionTask,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    if (row.schedule.type === 'cron') {
      return (
        <CollectionCrontab
          timezone={row.schedule.timezone}
          value={row.schedule.cron_expression}
          readonly
        />
      ) as unknown as SlotReturnValue;
    }
    return renderCtx.cellRenderHandleMap[ExploreTableColumnTypeEnum.TIME](row, column, renderCtx);
  };

  /**
   * @description 启 / 停列渲染（开关；计划已过期的任务保留当前启停状态但禁止切换）
   * @param {CollectionTask} row - 当前行任务数据
   * @returns {SlotReturnValue} 启停开关 JSX
   */
  const renderTaskStatus = (row: CollectionTask) =>
    (
      <span
        v-tippy={{
          content: t('任务已过期，无法切换启停状态'),
          onShow: () => row.deployment_status === 'outdate',
        }}
      >
        <Switcher
          // 计划已过期（outdate）的任务保留当前启停状态，但不允许再切换
          disabled={get(rendererCtx.readonly) || get(rendererCtx.busy) || row.deployment_status === 'outdate'}
          modelValue={row.task_status === 'enabled'}
          size='small'
          theme='primary'
          onChange={() => rendererCtx.onToggle(row)}
        />
      </span>
    ) as unknown as SlotReturnValue;

  /**
   * @description 操作列渲染（执行记录 / 编辑 / 立即执行 / 删除；启用中的任务需先停用才能删除）
   * @param {CollectionTask} row - 当前行任务数据
   * @returns {SlotReturnValue} 操作列 JSX
   */
  const renderOperations = (row: CollectionTask) => {
    const disabled = get(rendererCtx.readonly) || get(rendererCtx.busy);
    return (
      <div class='collection-row-actions'>
        <Button
          theme='primary'
          text
          onClick={() => rendererCtx.onHistory(row)}
        >
          {t('执行记录')}
        </Button>
        <Button
          disabled={disabled}
          theme='primary'
          text
          onClick={() => rendererCtx.onEdit(row)}
        >
          {t('编辑')}
        </Button>
        <Button
          disabled={disabled}
          theme='primary'
          text
          onClick={() => rendererCtx.onExecute(row)}
        >
          {t('立即执行')}
        </Button>
        <span
          v-tippy={{
            content: t('请先停用任务后再删除'),
            onShow: () => isTaskDeleteBlocked(row),
          }}
        >
          <Button
            disabled={disabled || isTaskDeleteBlocked(row)}
            theme='primary'
            text
            onClick={() => rendererCtx.onDelete(row)}
          >
            {t('删除')}
          </Button>
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /** 列渲染配置映射表：按 colKey 定义各列的 cellRenderer / renderType / getRenderValue 等配置，未登记的列走表格默认文本渲染 */
  const columnsRendererMap: Record<string, Partial<BaseTableColumn>> = {
    name: {
      renderType: ExploreTableColumnTypeEnum.CLICK,
      clickCallback: (row: CollectionTask) => rendererCtx.onDetail(row),
    },
    collection_method: { getRenderValue: (row: CollectionTask) => collectionMethodLabels[row.collection_method] },
    collection_type: { getRenderValue: (row: CollectionTask) => collectionTypeLabels[row.collection_type] },
    schedule: { getRenderValue: (row: CollectionTask) => t(scheduleLabels[row.schedule.type]) },
    schedule_time: {
      cellRenderer: renderScheduleTime,
      getRenderValue: (row: CollectionTask) => ('execute_at' in row.schedule ? row.schedule.execute_at : undefined),
    },
    task_status: { cellRenderer: renderTaskStatus },
    deployment_status: {
      renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
      getRenderValue: (row: CollectionTask) => ({
        alias: deploymentStatusLabels[row.deployment_status] || row.deployment_status,
        prefixIcon: `collection-deployment-dot is-${row.deployment_status}`,
      }),
    },
    updated_at: { renderType: ExploreTableColumnTypeEnum.TIME },
    operation: { cellRenderer: renderOperations },
  };

  /**
   * @description 将外部列配置与 columnsRendererMap 中的渲染配置按 colKey 合并，生成完整列定义
   * @param {CollectionTaskTableColumn[]} columns - 外部传入的列配置
   * @returns {BaseTableColumn[]} 合并渲染配置后的完整列定义数组
   */
  const transformColumns = (columns: CollectionTaskTableColumn[]): BaseTableColumn[] =>
    columns.map(column => ({ ...column, ...columnsRendererMap[String(column.colKey)] }));

  return { transformColumns };
};
