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
  RUM_FIELD_DEFAULT_COLUMN_WIDTH,
  RUM_SORTABLE_FIELD_TYPES,
  RumFieldDisplayEnum,
} from '../constants';
import useUserConfig from '@/hooks/useUserConfig';

import type { BaseTableColumn } from '../../trace-explore/components/trace-explore-table/typing';
import type { IRumColumnLayoutPreset, IRumField, IRumViewConfig } from '../typings';

/** 列配置存储结构版本号，schema 变更时递增以自动失效旧缓存 */
const RUM_COLUMN_CONFIG_VERSION = '1.0.1';

/** useRumColumnConfig 返回的列配置上下文类型 */
export type IRumColumnConfig = ReturnType<typeof useRumColumnConfig>;

/** 常驻配置中存储的列配置结构 */
interface IRumColumnConfigCache {
  /** 列宽覆盖：colKey -> 宽度，覆盖常量默认值 */
  columnResizeWidth: Record<string, number>;
  /** 展示列的字段名（顺序即列顺序），同时表达显隐；受控态下不落盘 */
  displayFields: string[];
  /** 配置版本号，用于清除过期缓存 */
  version?: string;
}

/**
 * @description 列配置集中管理 hook：统管列的显隐/顺序、列宽覆盖，并持久化到用户常驻配置。
 * @param {MaybeRef<string>} opts.cacheKey 列缓存 key，空串表示未就绪、跳过读取
 * @param {MaybeRef<IRumColumnLayoutPreset>} opts.layoutPreset 列布局预设（默认列宽 / 左侧固定列），由调用方按检索视角选择
 * @param {MaybeRef<string[]>} opts.overrideDisplayFields 受控展示列，非空数组即「受控态」，使用该列表作为展示列并锁定编辑（列宽仍可调整并持久化）
 * @param {Ref<IRumViewConfig>} opts.viewConfig 字段全集与接口默认列，用于校验与兜底
 */
export function useRumColumnConfig(opts: {
  /** 列缓存 key，空串表示未就绪、跳过读取 */
  cacheKey: MaybeRef<string>;
  /** 列布局预设（默认列宽 / 左侧固定列），由调用方按检索视角选择 */
  layoutPreset: MaybeRef<IRumColumnLayoutPreset>;
  /** 受控展示列，非空数组即受控态 */
  overrideDisplayFields: MaybeRef<string[]>;
  /** 字段全集与接口默认列 */
  viewConfig: Ref<IRumViewConfig>;
}) {
  const { cacheKey, layoutPreset, viewConfig, overrideDisplayFields } = opts;
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
  /** 是否处于受控态；overrideDisplayFields 非空即受控，锁定展示列与持久化 */
  const isControlled = computed(() => get(overrideDisplayFields)?.length);
  /** 用户缓存的展示列；非受控态下可被接口默认列兜底 */
  const cachedDisplayFields = computed<string[]>({
    get: () => {
      const cached = columnConfigCache.value.displayFields;
      const result = cached?.length ? cached : get(viewConfig).display_fields;
      return result.filter(name => fieldMap.value.has(name));
    },
    /**
     * 写入时按有效字段裁剪并触发防抖保存。
     * 受控态下展示列由 span 类型决定，禁止改写：这样类型专属的列不可能进入缓存，也就不可能被落盘。
     */
    set: (val: string[]) => {
      if (isControlled.value) return;
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
    /**
     * 写入时合并到现有覆盖并触发防抖保存：
     * 必须始终是「合并后写回」，否则表格重渲染后列宽会回落到预设值（tdesign 会在列配置变化时清空内部列宽缓存）。
     */
    set: (val: Record<string, number>) => {
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
      // 受控态：直接展示外部指定的列（按有效字段校验裁剪），忽略用户缓存
      return get(overrideDisplayFields).filter(name => fieldMap.value.has(name));
    }
    // 非受控态：用户缓存列 > 接口默认列
    return cachedDisplayFields.value;
  });

  /**
   * 基础列配置：展示列 -> 列宽（用户覆盖 > 视角预设 > 字段元信息推导 > 全局默认）-> 排序 / 固定等元数据。
   * 固定列沿用展示列顺序，仅影响渲染，不改变 displayFields 的持久化顺序。
   */
  const baseColumns = computed<BaseTableColumn[]>(() => {
    const { leftFixedColumns, widthMap } = get(layoutPreset) ?? {};
    const columns: BaseTableColumn[] = displayFields.value
      .map(name => fieldMap.value.get(name))
      .filter(Boolean)
      .map(field => ({
        colKey: field.name,
        width: fieldsWidthConfig.value[field.name] ?? widthMap?.[field.name] ?? getDefaultColumnWidth(field),
        fixed: leftFixedColumns?.has(field.name) ? 'left' : undefined,
        minWidth: DEFAULT_MIN_COLUMN_WIDTH,
        resizable: true,
        sorter: RUM_SORTABLE_FIELD_TYPES.has(field.type),
      }));
    return columns;
  });

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

  /**
   * 防抖保存列配置。
   * 列宽属于字段级视觉偏好，受控态下同样落盘；展示列的写入已在 setter 处按受控态拦截，
   * 因此这里整体序列化缓存不会把类型专属的列写进全局配置（受控态下 displayFields 恒为加载时的值）。
   */
  const saveColumnConfig = useDebounceFn(() => {
    handleSetUserConfig(JSON.stringify(columnConfigCache.value));
  }, 300);

  /**
   * @description 从用户常驻配置加载列配置
   */
  async function loadColumnConfig() {
    // 空 key 由 hook 跳过请求并清空配置 ID，避免切换时写入上一个应用。
    const cached = await handleGetUserConfig<IRumColumnConfigCache>(get(cacheKey));
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

/**
 * @description 按字段元信息推导默认列宽：展示类型 > 单位 > 枚举取值 > 全局默认。
 * 仅当用户列宽缓存与视角预设都未命中时兜底，避免每个字段都在预设表里登记一遍。
 * @param {IRumField} field 字段元数据
 * @returns {number} 列宽
 */
function getDefaultColumnWidth(field: IRumField): number {
  if (field.field_display_type === RumFieldDisplayEnum.DATETIME) return RUM_FIELD_DEFAULT_COLUMN_WIDTH.datetime;
  if (field.field_display_type === RumFieldDisplayEnum.DURATION) return RUM_FIELD_DEFAULT_COLUMN_WIDTH.duration;
  if (field.field_unit) return RUM_FIELD_DEFAULT_COLUMN_WIDTH.unit;
  if (field.option_values?.length) return RUM_FIELD_DEFAULT_COLUMN_WIDTH.option;
  return DEFAULT_COLUMN_WIDTH;
}
