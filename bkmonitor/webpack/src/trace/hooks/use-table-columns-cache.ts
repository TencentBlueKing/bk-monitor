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

import { computed, toValue } from 'vue';

import { useReactiveStorage } from './use-reactive-storage';

import type { StorageLike, UseStorageOptions } from '@vueuse/core';
import type { MaybeRefOrGetter } from '@vueuse/shared';

/** 表格列配置存储默认版本号（旧数据未携带 version 时按此处理） */
export const TABLE_COLUMNS_STORAGE_VERSION = '1.0.0';

/** 表格列配置存储结构 */
export interface TableColumnsStorageConfig {
  /** 显示列字段列表 */
  displayFields: string[];
  /** 列宽映射，key 为 colKey，value 为像素宽度 */
  fieldsWidth: Record<string, number>;
  /** 配置版本号，用于清除过期缓存 */
  version?: string;
}

export interface UseTableColumnsCacheOptions {
  /** 默认显示列（缓存为空或结构异常时的回退值） */
  defaultColumns: MaybeRefOrGetter<string[]>;
  /** 透传 useReactiveStorage 的选项 */
  options?: UseStorageOptions<Partial<TableColumnsStorageConfig>>;
  /** 透传 useReactiveStorage 的存储实现与选项 */
  storage?: StorageLike;
  /** 存储 key，支持响应式 getter（业务随服务/视图切换动态变更） */
  storageKey: MaybeRefOrGetter<string>;
  /** 当前全部有效列 key（可选，用于过滤已删除列的残留宽度） */
  validColumnKeys?: MaybeRefOrGetter<string[]>;
  /** 配置版本号，不匹配时清空列宽缓存 */
  version?: string;
}

/**
 * useTableColumnsCache — 表格「显示列 + 列宽」持久化缓存公共 hook（与具体业务解耦）
 *
 * 只负责两个可写响应式状态的读写与持久化：
 *  - storageColumns：当前显示列 id 列表（配合 tdesign bkUiSettings.checked）
 *  - fieldsWidthConfig：列宽映射（配合 PrimaryTable resizable + onColumnResizeChange）
 *
 * 内置能力：
 *  - 旧版 string[] 格式缓存自动迁移为新版结构
 *  - 版本号不匹配时清空列宽缓存
 *  - 动态 key（useReactiveStorage）支持存储 key 变化时重建缓存实例
 *
 * 列定义组装（tableColumns 等）由各业务自行完成，本 hook 不感知列结构。
 */
export function useTableColumnsCache(options: UseTableColumnsCacheOptions) {
  const { storageKey, defaultColumns, validColumnKeys, version = TABLE_COLUMNS_STORAGE_VERSION } = options;

  /** 默认列配置（响应式，供 useReactiveStorage 在缓存为空时兜底） */
  const defaultStorageConfig = computed<TableColumnsStorageConfig>(() => ({
    displayFields: toValue(defaultColumns) ?? [],
    fieldsWidth: {},
    version,
  }));

  /** 缓存配置对象（原始值，可能为旧版 string[] 或新版 TableColumnsStorageConfig） */
  const rawStorageConfig = useReactiveStorage<Partial<TableColumnsStorageConfig>>(
    storageKey,
    defaultStorageConfig,
    options.storage,
    options.options
  );

  /** 规范化后的缓存配置（始终为 TableColumnsStorageConfig，兼容旧版 string[] 格式） */
  const tableStorageConfig = computed<TableColumnsStorageConfig>({
    get: () => {
      const raw = rawStorageConfig.value;
      const defaultFields = defaultStorageConfig.value.displayFields;
      // 旧版格式：string[]（纯数组）→ 自动迁移为新版结构
      if (Array.isArray(raw)) {
        return { displayFields: raw, fieldsWidth: {}, version };
      }
      // 统一返回逻辑：版本不匹配时清空列宽缓存
      const isVersionValid = raw?.version === version;
      return {
        displayFields: Array.isArray(raw?.displayFields) ? raw.displayFields : defaultFields,
        fieldsWidth: isVersionValid ? (raw.fieldsWidth ?? {}) : {},
        version,
      };
    },
    set: (val: TableColumnsStorageConfig) => {
      rawStorageConfig.value = val;
    },
  });

  /** 当前显示列列表（缓存为空时回退默认列） */
  const storageColumns = computed<string[]>({
    get: () => {
      const stored = tableStorageConfig.value?.displayFields;
      const defaults = defaultStorageConfig.value.displayFields;
      return stored?.length ? stored : defaults;
    },
    set: (val: string[]) => {
      tableStorageConfig.value = {
        ...tableStorageConfig.value,
        displayFields: val,
      };
    },
  });

  /** 列宽配置（读取时过滤已不存在的列） */
  const fieldsWidthConfig = computed<Record<string, number>>({
    get: () => {
      const stored = tableStorageConfig.value?.fieldsWidth ?? {};
      const validKeys = validColumnKeys ? new Set(toValue(validColumnKeys) ?? []) : null;
      const entries = Object.entries(stored);
      return Object.fromEntries(validKeys ? entries.filter(([key]) => validKeys.has(key)) : entries);
    },
    set: (val: Record<string, number>) => {
      tableStorageConfig.value = {
        ...tableStorageConfig.value,
        fieldsWidth: { ...fieldsWidthConfig.value, ...val },
      };
    },
  });

  return {
    storageColumns,
    fieldsWidthConfig,
  };
}
