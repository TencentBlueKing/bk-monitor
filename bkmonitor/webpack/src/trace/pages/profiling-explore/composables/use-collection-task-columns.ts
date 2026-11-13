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
import { type MaybeRef, computed } from 'vue';

import { get } from '@vueuse/core';

import { FALLBACK_TASK_COLUMNS, TASK_OPERATION_FIELD, taskFieldConfigs } from '../utils/collection';
import { useTableColumnsCache } from '@/hooks/use-table-columns-cache';

import type { CollectionTaskColumn, CollectionTaskTableColumn } from '../types/collection';
import type { BkUiSettings } from '@blueking/tdesign-ui';

/** 任务列表显示列与列宽的本地缓存 key */
const TASK_COLUMNS_STORAGE_KEY = 'trace_profiling_collection_task_columns';
/** 未登记字段（含后端后续新增列）的兜底列宽 */
const DEFAULT_COLUMN_WIDTH = 160;

/**
 * @description 任务管理表格的列配置与列设置字段
 *
 * 可用列就是接口下发的 columns（顺序同样以后端为准），接口未下发时回退固定列；
 * 列的结构属性（列名、列宽、固定、排序、筛选、默认/锁定态）在此组装后下发给表格，
 * 与告警中心 issues 表格一致，表格组件只负责单元格渲染。
 * 显示列与列宽走公共缓存 hook 持久化。
 *
 * @param columns 接口下发的列定义
 */
export function useCollectionTaskColumns(columns: MaybeRef<CollectionTaskColumn[]>) {
  /** 可用列就是后端下发的列（顺序同样以后端为准）；接口未下发时才回退固定列 */
  const taskColumns = computed(() => {
    const list = get(columns);
    return list.length ? list : FALLBACK_TASK_COLUMNS;
  });
  /** 表格渲染的列 key：后端列 + 表格追加的操作列 */
  const columnKeys = computed(() => [...taskColumns.value.map(column => column.field), TASK_OPERATION_FIELD]);
  /** 默认展示列取自字段配置，顺序跟随后端列 */
  const defaultColumns = computed(() => columnKeys.value.filter(field => !!taskFieldConfigs[field]?.is_default));
  const { storageColumns, fieldsWidthConfig } = useTableColumnsCache({
    storageKey: TASK_COLUMNS_STORAGE_KEY,
    defaultColumns: () => defaultColumns.value,
    validColumnKeys: () => columnKeys.value,
  });
  /** 锁定列：列设置里必须显示且不可取消（含操作列） */
  const lockedTableFields = computed(() =>
    Object.keys(taskFieldConfigs).filter(field => taskFieldConfigs[field].is_locked)
  );
  /** 组装后的表格列：字段配置打底，列名与列类型以后端为准，列宽优先取缓存值；末尾固定补操作列 */
  const tableColumns = computed<CollectionTaskTableColumn[]>(() => {
    const operation = taskFieldConfigs[TASK_OPERATION_FIELD];
    return [
      ...taskColumns.value.map(column => {
        const config = taskFieldConfigs[column.field] ?? {};
        return {
          ...config,
          colKey: column.field,
          // 列名以后端下发为准，缺失时用字段配置里已翻译好的兜底列名
          title: column.name || config.title || column.field,
          width: fieldsWidthConfig.value[column.field] || config.width || DEFAULT_COLUMN_WIDTH,
          resizable: true,
          is_default: config.is_default ?? false,
          is_locked: config.is_locked ?? false,
        };
      }),
      // 操作列：展示属性取字段配置，列宽同样走缓存，单元格渲染由表格负责
      {
        ...operation,
        colKey: TASK_OPERATION_FIELD,
        title: String(operation.title),
        width: fieldsWidthConfig.value[TASK_OPERATION_FIELD] || operation.width || DEFAULT_COLUMN_WIDTH,
        is_default: operation.is_default ?? false,
        is_locked: operation.is_locked ?? false,
      },
    ];
  });
  /** 列设置面板中可配置的列 */
  const allTableFields = computed<BkUiSettings['fields']>(() =>
    tableColumns.value.map(column => ({ field: String(column.colKey), label: String(column.title) }))
  );
  /** 列设置面板关闭时回写显示列，过滤掉已下线的列并补回锁定列 */
  function handleSettingsChange(value: string[]) {
    const validKeys = new Set(columnKeys.value);
    // 锁定列（任务名、操作列）不随面板取消而隐藏
    const locked = lockedTableFields.value.filter(field => validKeys.has(field));
    storageColumns.value = [...new Set([...value.filter(field => validKeys.has(field)), ...locked])];
  }
  /** 列宽拖拽后合并进缓存，缺失的列宽在读取时按可用列过滤 */
  function handleColumnResize(value: Record<string, number>) {
    fieldsWidthConfig.value = value;
  }
  return {
    tableColumns,
    storageColumns,
    allTableFields,
    lockedTableFields,
    columnWidths: fieldsWidthConfig,
    handleSettingsChange,
    handleColumnResize,
  };
}
