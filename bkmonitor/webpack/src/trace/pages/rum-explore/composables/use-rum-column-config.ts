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
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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
import { type MaybeRef, type Ref, computed, shallowRef, watch } from 'vue';

import { get, useDebounceFn } from '@vueuse/core';

import {
  DEFAULT_COLUMN_WIDTH,
  DEFAULT_MIN_COLUMN_WIDTH,
  RUM_COLUMN_WIDTH_MAP,
  RUM_SORTABLE_FIELD_TYPES,
} from '../constants';
import useUserConfig from '@/hooks/useUserConfig';

import type { BaseTableColumn } from '../../trace-explore/components/trace-explore-table/typing';
import type { IRumViewConfig } from '../typings';

/** 列配置存储结构版本号，schema 变更时递增以自动失效旧缓存 */
const RUM_COLUMN_CONFIG_VERSION = '1.0.0';

/** useRumColumnConfig 返回的列配置上下文类型 */
export type IRumColumnConfig = ReturnType<typeof useRumColumnConfig>;

/** 常驻配置中存储的列配置结构 */
interface IRumColumnConfigCache {
  /** 列宽覆盖：colKey -> 宽度，覆盖常量默认值 */
  columnResizeWidth: Record<string, number>;
  /** 展示列的字段名（顺序即列顺序），同时表达显隐 */
  displayFields: string[];
  /** 配置版本号，用于清除过期缓存 */
  version?: string;
}

/**
 * @description 列配置集中管理 hook：统管列的显隐/顺序、列宽覆盖，并持久化到用户常驻配置。
 * @param {MaybeRef<string>} opts.cacheKey 列缓存 key，空串表示未就绪、跳过读取
 * @param {MaybeRef<string[]>} opts.overrideDisplayFields 受控展示列，非空数组即「受控态」，使用该列表作为展示列并锁定编辑/持久化
 * @param {Ref<IRumViewConfig>} opts.viewConfig 字段全集与接口默认列，用于校验与兜底
 */
export function useRumColumnConfig(opts: {
  /** 列缓存 key，空串表示未就绪、跳过读取 */
  cacheKey: MaybeRef<string>;
  /** 受控展示列，非空数组即受控态 */
  overrideDisplayFields: MaybeRef<string[]>;
  /** 字段全集与接口默认列 */
  viewConfig: Ref<IRumViewConfig>;
}) {
  const { cacheKey, viewConfig, overrideDisplayFields } = opts;
  const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

  /** 归一化后的缓存配置（始终为 IRumColumnConfigCache，按有效字段裁剪、版本失效回退默认） */
  const columnConfigCache = shallowRef<IRumColumnConfigCache>({
    displayFields: [],
    columnResizeWidth: {},
    version: RUM_COLUMN_CONFIG_VERSION,
  });

  /** 可作为列的字段全集，供字段设置使用 */
  const displayableFields = computed(() => get(viewConfig).fields.filter(field => field.can_displayed));
  /** 字段名 -> 字段元数据；同时承担「有效字段集合」的校验职责 */
  const fieldMap = computed(() => new Map(displayableFields.value.map(field => [field.name, field])));
  /** 是否处于非受控态；overrideDisplayFields 为空数组时用户可自由设置列 */
  const isControlled = computed(() => !get(overrideDisplayFields)?.length);
  /** 用户缓存的展示列；非受控态下可被接口默认列兜底 */
  const cachedDisplayFields = computed<string[]>({
    get: () => {
      const cached = columnConfigCache.value.displayFields;
      const result = cached?.length ? cached : get(viewConfig).display_fields;
      return result.filter(name => fieldMap.value.has(name));
    },
    /** 写入时按有效字段裁剪并触发防抖保存 */
    set: (val: string[]) => {
      columnConfigCache.value = {
        ...columnConfigCache.value,
        displayFields: val.filter(name => fieldMap.value.has(name)),
      };
      saveColumnConfig();
    },
  });
  /** 列宽覆盖（已按有效字段裁剪） */
  const fieldsWidthConfig = computed<Record<string, number>>({
    get: () => {
      const stored = columnConfigCache.value.columnResizeWidth ?? {};
      return Object.fromEntries(Object.entries(stored).filter(([key]) => fieldMap.value.has(key)));
    },
    /** 写入时合并到现有覆盖并触发防抖保存；受控态下忽略 */
    set: (val: Record<string, number>) => {
      if (isControlled.value) return;
      columnConfigCache.value = {
        ...columnConfigCache.value,
        columnResizeWidth: { ...fieldsWidthConfig.value, ...val },
      };
      saveColumnConfig();
    },
  });

  /** 生效的展示列（渲染与收藏使用） */
  const displayFields = computed<string[]>(() => {
    if (isControlled.value) {
      // 非受控态：用户缓存列 > 接口默认列
      return cachedDisplayFields.value;
    }
    // 受控态：直接展示外部指定的列（按有效字段校验裁剪），忽略用户缓存
    return get(overrideDisplayFields).filter(name => fieldMap.value.has(name));
  });

  /** 基础列配置：展示列 -> 列宽（列宽覆盖优先于常量默认值）-> 排序等元数据 */
  const baseColumns = computed<BaseTableColumn[]>(() =>
    displayFields.value
      .map(name => fieldMap.value.get(name))
      .filter(Boolean)
      .map(field => ({
        colKey: field.name,
        width: fieldsWidthConfig.value[field.name] ?? RUM_COLUMN_WIDTH_MAP[field.name] ?? DEFAULT_COLUMN_WIDTH,
        minWidth: DEFAULT_MIN_COLUMN_WIDTH,
        resizable: true,
        sorter: RUM_SORTABLE_FIELD_TYPES.has(field.type),
      }))
  );

  /**
   * @description 更新展示列
   * @param {string[]} fields 新的字段名顺序
   */
  function updateDisplayFields(fields: string[]) {
    cachedDisplayFields.value = fields;
  }

  /**
   * @description 更新列宽覆盖
   * @param {Record<string, number>} width colKey -> 宽度映射
   */
  function updateColumnResizeWidth(width: Record<string, number>) {
    fieldsWidthConfig.value = width;
  }

  /** 防抖保存列配置；仅非受控态真正落盘 */
  const saveColumnConfig = useDebounceFn(() => {
    if (isControlled.value) return;
    handleSetUserConfig(JSON.stringify(columnConfigCache.value));
  }, 300);

  /**
   * @description 从用户常驻配置加载列配置
   */
  async function loadColumnConfig() {
    // 缓存 key 未就绪（空串）时跳过读取；待 key 就绪后 watch 会重新触发加载
    if (!get(cacheKey)) return;
    let cached: IRumColumnConfigCache | undefined;
    try {
      cached = await handleGetUserConfig<IRumColumnConfigCache>(get(cacheKey));
    } catch {
      cached = undefined;
    }
    // 版本不匹配或无有效缓存：丢弃并回退默认，待用户操作后再落盘
    const isVersionValid = cached?.version === RUM_COLUMN_CONFIG_VERSION;
    if (isVersionValid) {
      columnConfigCache.value = {
        displayFields: cached.displayFields ?? [],
        columnResizeWidth: cached.columnResizeWidth ?? {},
        version: RUM_COLUMN_CONFIG_VERSION,
      };
    }
  }

  /** 缓存 key 变化时重置并重新加载配置 */
  watch(
    () => get(cacheKey),
    () => {
      columnConfigCache.value = {
        displayFields: [],
        columnResizeWidth: {},
        version: RUM_COLUMN_CONFIG_VERSION,
      };
      loadColumnConfig();
    },
    { immediate: true }
  );

  return {
    /** 生效的展示列 */
    displayFields,
    /** 列宽覆盖映射 */
    columnResizeWidth: fieldsWidthConfig,
    /** 表格基础列配置 */
    baseColumns,
    /** 可作为列的字段全集 */
    displayableFields,
    /** 字段名 -> 字段元数据 */
    fieldMap,
    /** 更新展示列 */
    updateDisplayFields,
    /** 更新列宽覆盖 */
    updateColumnResizeWidth,
    /** 手动重新加载列配置 */
    loadColumnConfig,
  };
}
