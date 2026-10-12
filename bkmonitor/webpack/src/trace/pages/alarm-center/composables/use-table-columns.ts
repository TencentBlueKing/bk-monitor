/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { computed } from 'vue';

import { type TableColumnItem, AlarmType, MY_ALARM_BIZ_ID, MY_AUTH_BIZ_ID } from '../typings';
import { useTableColumnsCache } from '@/hooks/use-table-columns-cache';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { BkUiSettings } from '@blueking/tdesign-ui';

/** 业务名称/空间名称 字段 */
const BK_BIZ_NAME_FIELD = 'bk_biz_name';

export function useAlarmTableColumns() {
  const alarmStore = useAlarmCenterStore();

  /** 列显示与列宽持久化（公共能力，存储 key 随 alarmService 切换动态变更） */
  const { storageColumns: cachedStorageColumns, fieldsWidthConfig } = useTableColumnsCache({
    storageKey: () => alarmStore.alarmService.storageKey,
    defaultColumns: () =>
      alarmStore.alarmService.allTableColumns.filter(item => item.is_default).map(item => item.colKey),
    validColumnKeys: () => alarmStore.alarmService.allTableColumns.map(col => col.colKey),
  });

  /** 显示列列表（叠加业务规则：单空间场景隐藏空间名称列） */
  const storageColumns = computed<string[]>({
    get: () => {
      const result = cachedStorageColumns.value;
      if (shouldOmitBkBizNameColumn(alarmStore.bizIds)) {
        return result.filter(f => f !== BK_BIZ_NAME_FIELD);
      }
      return result;
    },
    set: (val: string[]) => {
      cachedStorageColumns.value = shouldOmitBkBizNameColumn(alarmStore.bizIds)
        ? val.filter(f => f !== BK_BIZ_NAME_FIELD)
        : val;
    },
  });

  /** 必须显示且不可编辑隐藏列 */
  const lockedTableFields = computed(() => {
    const locked = alarmStore.alarmService.allTableColumns.filter(item => item.is_locked).map(item => item.colKey);
    if (alarmStore.alarmType === AlarmType.ALERT) {
      return ['row-select', ...locked];
    }
    return locked;
  });
  const tableColumns = computed<TableColumnItem[]>(() => {
    const widths = fieldsWidthConfig.value;
    return allTableFields.value
      .map(({ field }) => {
        if (field === 'row-select') {
          return { colKey: 'row-select', type: 'multiple' as const, width: 50, minWidth: 50, fixed: 'left' as const };
        }
        if (field === BK_BIZ_NAME_FIELD && shouldOmitBkBizNameColumn(alarmStore.bizIds)) {
          return undefined;
        }
        const column = alarmStore.alarmService.allTableColumns.find(col => col.colKey === field);
        if (!column) return undefined;
        const cachedWidth = widths[field];
        return {
          ...column,
          ...(cachedWidth ? { width: cachedWidth } : {}),
        };
      })
      .filter(Boolean);
  });
  const allTableFields = computed<BkUiSettings['fields']>(() => {
    const columns = shouldOmitBkBizNameColumn(alarmStore.bizIds)
      ? alarmStore.alarmService.allTableColumns.filter(c => c.colKey !== BK_BIZ_NAME_FIELD)
      : alarmStore.alarmService.allTableColumns;
    if ([AlarmType.ALERT, AlarmType.ISSUES].includes(alarmStore.alarmType)) {
      return [{ title: '', colKey: 'row-select' }, ...columns].map(item => ({
        label: item.title.toString(),
        field: item.colKey,
      }));
    }
    return columns.map(item => ({
      label: item.title.toString(),
      field: item.colKey,
    }));
  });
  return {
    storageColumns,
    fieldsWidthConfig,
    tableColumns,
    allTableFields,
    lockedTableFields,
  };
}

/** 与表格渲染一致：单空间（非「与我相关」聚合）不展示空间名列，默认勾选也不应包含 */
function shouldOmitBkBizNameColumn(bizIds: number[]) {
  return bizIds.length < 2 && ![MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(bizIds[0]);
}
