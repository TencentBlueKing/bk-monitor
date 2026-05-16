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

import { computed, shallowRef, watch } from 'vue';

import { useStorage } from '@vueuse/core';

import { type TableColumnItem, AlarmType, MY_ALARM_BIZ_ID, MY_AUTH_BIZ_ID } from '../typings';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { BkUiSettings } from '@blueking/tdesign-ui';

/** 业务名称/空间名称 字段 */
const BK_BIZ_NAME_FIELD = 'bk_biz_name';

/** 与表格渲染一致：单空间（非「与我相关」聚合）不展示空间名列，默认勾选也不应包含 */
function shouldOmitBkBizNameColumn(bizIds: number[]) {
  return bizIds.length < 2 && ![MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(bizIds[0]);
}

/** 表格列配置存储版本号 */
const TABLE_STORAGE_VERSION = '1.0.0';

/** 表格列配置存储结构 */
export interface AlarmTableStorageConfig {
  /** 显示列字段列表 */
  displayFields: string[];
  /** 列宽映射，key 为 colKey，value 为像素宽度 */
  fieldsWidth: Record<string, number>;
  /** 配置版本号，用于清除过期缓存 */
  version?: string;
}

export function useAlarmTableColumns() {
  const alarmStore = useAlarmCenterStore();
  const storageKey = shallowRef<string>('');

  /** 默认列配置（响应式），随 alarmService 变化动态更新 */
  const defaultTableStorageConfig = shallowRef<AlarmTableStorageConfig>({
    displayFields: [],
    fieldsWidth: {},
    version: TABLE_STORAGE_VERSION,
  });

  /** 当前有效的列 colKey 集合，随 alarmService 变化更新 */
  let validColumnKeys = new Set<string>();

  watch(
    () => ({
      key: alarmStore.alarmService.storageKey,
      bizIdsKey: alarmStore.bizIds.join(','),
    }),
    () => {
      validColumnKeys = new Set(alarmStore.alarmService.allTableColumns.map(col => col.colKey));
      let displayFields = alarmStore.alarmService.allTableColumns
        .filter(item => item.is_default)
        .map(item => item.colKey);
      if (shouldOmitBkBizNameColumn(alarmStore.bizIds)) {
        displayFields = displayFields.filter(f => f !== BK_BIZ_NAME_FIELD);
      }
      defaultTableStorageConfig.value = {
        displayFields,
        fieldsWidth: {},
        version: TABLE_STORAGE_VERSION,
      };
      const key = alarmStore.alarmService.storageKey;
      storageKey.value = key;
    },
    { immediate: true }
  );

  /** 缓存配置对象（原始值，可能为旧版 string[] 或新版 AlarmTableStorageConfig） */
  const rawStorageConfig = useStorage<Partial<AlarmTableStorageConfig>>(storageKey, defaultTableStorageConfig);

  /** 规范化后的缓存配置（始终为 AlarmTableStorageConfig，兼容旧版 string[] 格式） */
  const tableStorageConfig = computed<AlarmTableStorageConfig>({
    get: () => {
      const raw = rawStorageConfig.value;
      const defaultFields = defaultTableStorageConfig.value.displayFields;
      // 旧版格式：string[]（纯数组）→ 自动迁移为新版结构
      if (Array.isArray(raw)) {
        return { displayFields: raw, fieldsWidth: {}, version: TABLE_STORAGE_VERSION };
      }
      // 统一返回逻辑：版本不匹配时清空列宽缓存
      const isVersionValid = raw?.version === TABLE_STORAGE_VERSION;
      return {
        displayFields: Array.isArray(raw?.displayFields) ? raw.displayFields : defaultFields,
        fieldsWidth: isVersionValid ? (raw.fieldsWidth ?? {}) : {},
        version: TABLE_STORAGE_VERSION,
      };
    },
    set: (val: AlarmTableStorageConfig) => {
      rawStorageConfig.value = val;
    },
  });

  /** 显示列列表（从统一存储结构中读取 displayFields） */
  const storageColumns = computed<string[]>({
    get: () => {
      const stored = tableStorageConfig.value?.displayFields;
      const defaults = defaultTableStorageConfig.value.displayFields;
      return stored?.length ? stored : defaults;
    },
    set: (val: string[]) => {
      tableStorageConfig.value = {
        ...tableStorageConfig.value,
        displayFields: val,
      };
    },
  });

  /** 列宽配置（从统一存储结构中读取 fieldsWidth，过滤已不存在的列） */
  const fieldsWidthConfig = computed<Record<string, number>>({
    get: () => {
      const stored = tableStorageConfig.value?.fieldsWidth ?? {};
      return Object.fromEntries(Object.entries(stored).filter(([key]) => validColumnKeys.has(key)));
    },
    set: (val: Record<string, number>) => {
      tableStorageConfig.value = {
        ...tableStorageConfig.value,
        fieldsWidth: { ...fieldsWidthConfig.value, ...val },
      };
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
    if ([AlarmType.ALERT, AlarmType.ISSUES].includes(alarmStore.alarmType)) {
      return [{ title: '', colKey: 'row-select' }, ...alarmStore.alarmService.allTableColumns].map(item => ({
        label: item.title.toString(),
        field: item.colKey,
      }));
    }
    let cols = alarmStore.alarmService.allTableColumns;
    if (shouldOmitBkBizNameColumn(alarmStore.bizIds)) {
      cols = cols.filter(c => c.colKey !== BK_BIZ_NAME_FIELD);
    }
    return cols.map(item => ({
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
