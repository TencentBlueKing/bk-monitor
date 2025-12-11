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

import { type MaybeRef, computed, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

import useUserConfig from '../../../../../hooks/useUserConfig';
import { useTraceExploreStore } from '../../../../../store/modules/explore';
import { TABLE_DEFAULT_CONFIG, TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX } from '../constants';
import { useFavoriteFieldsState } from '../utils/favorite-fields';

export interface UseExploreTableDisplayFieldOptions {
  /** 当前选中的应用 Name */
  appName: MaybeRef<string>;
  /** 当前激活的视角(span | trace)  */
  mode: MaybeRef<'span' | 'trace'>;
}

/**
 * @method useExploreTableDisplayField  检索表格渲染列字段及渲染列字段宽度配置 hook
 * @param {UseExploreTableDisplayFieldOptions} options 检索表格渲染列字段及渲染列字段宽度配置 hook 参数
 */
export const useExploreTableDisplayField = (options: UseExploreTableDisplayFieldOptions) => {
  const { traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;

  /** 用户自定义配置 table 显示列名 */
  const customDisplayFields = shallowRef<string[]>([]);
  /** 用户自定义配置 table 列宽度 */
  const customFieldsWidthConfig = shallowRef<{ [colKey: string]: number }>({});

  const store = useTraceExploreStore();
  const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();
  const {
    saveKey: favoriteTableConfigKey,
    config: favoriteTableConfig,
    refreshKey: favoriteTableConfigRefreshKey,
    setConfig: setFavoriteConfig,
  } = useFavoriteFieldsState();

  /** table 列配置本地缓存时的 key */
  const customDisplayColumnFieldsCacheKey = computed(
    () => `${get(options.mode)}_${get(options.appName)}_${TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX}`
  );

  /** table 显示列配置 */
  const displayColumnFields = computed<string[]>(() => {
    // 前端写死的兜底默认显示列配置(优先级：userConfig -> appList -> defaultConfig)
    const defaultColumnsConfig = get(options.mode) === 'span' ? spanConfig : traceConfig;
    const applicationColumnConfig =
      store?.currentApp?.view_config?.[`${get(options.mode)}_config`]?.display_columns || [];
    // 需要展示的字段列名数组
    return get(customDisplayFields)?.length
      ? get(customDisplayFields)
      : applicationColumnConfig?.length
        ? applicationColumnConfig
        : ((defaultColumnsConfig?.displayFields || []) as string[]);
  });

  /**
   * @method handleSetFavoriteFields 设置收藏中表格显示字段及字段宽度配置
   * @description 将当前表格显示字段及字段宽度配置保存到收藏配置中
   */
  const handleSetFavoriteFields = () => {
    setFavoriteConfig(customDisplayColumnFieldsCacheKey.value, {
      displayFields: get(customDisplayFields),
      fieldsWidth: get(customFieldsWidthConfig),
    });
  };

  /**
   * @method getCustomFieldsConfig 获取 table 表格列配置
   * @description 从用户配置/收藏配置中获取 table 表格列配置
   */
  const getCustomFieldsConfig = async () => {
    customDisplayFields.value = [];
    customFieldsWidthConfig.value = {};
    if (!get(options.appName) || !get(options.mode)) return;
    let customCacheConfig: any = {
      displayFields: [],
      fieldsWidth: {},
    };
    if (favoriteTableConfigKey.value === customDisplayColumnFieldsCacheKey.value) {
      // 优先取收藏配置
      customCacheConfig = favoriteTableConfig.value;
    } else {
      customCacheConfig = (await handleGetUserConfig<string[]>(customDisplayColumnFieldsCacheKey.value)) || {
        displayFields: [],
        fieldsWidth: {},
      };
    }
    // 原来只缓存了展示字段，且是数组结构，目前改为对象结构需向前兼容
    if (Array.isArray(customCacheConfig)) {
      customDisplayFields.value = customCacheConfig;
    } else {
      customDisplayFields.value = customCacheConfig.displayFields;
      customFieldsWidthConfig.value = customCacheConfig.fieldsWidth;
    }
    handleSetFavoriteFields();
  };

  /**
   * @method handleDisplayColumnFieldsChange 表格列显示配置项变更回调
   * @description 表格列显示配置项变更回调
   * @param {string[]} displayFields 需要展示的字段列名数组
   */
  const handleDisplayColumnFieldsChange = (displayFields: string[]) => {
    customDisplayFields.value = displayFields;
    // 缓存列配置
    handleSetUserConfig(
      JSON.stringify({
        displayFields: get(customDisplayFields),
        fieldsWidth: get(customFieldsWidthConfig),
      })
    );
    handleSetFavoriteFields();
  };

  /**
   * @method handleDisplayColumnResize 表格列 resize 回调
   * @description 表格列宽度调整后需进行缓存
   * @param {object} context 列 resize 回调参数
   * @param {object} context.columnsWidth 列宽度配置
   */
  const handleDisplayColumnResize = (context: { columnsWidth: { [colKey: string]: number } }) => {
    customFieldsWidthConfig.value = context?.columnsWidth || {};
    // 缓存列配置
    handleSetUserConfig(
      JSON.stringify({
        displayFields: get(customDisplayFields),
        fieldsWidth: get(customFieldsWidthConfig),
      })
    );
    handleSetFavoriteFields();
  };

  watch(
    [() => favoriteTableConfigRefreshKey.value, () => customDisplayColumnFieldsCacheKey.value],
    () => {
      getCustomFieldsConfig();
    },
    { immediate: true }
  );

  return {
    displayColumnFields,
    fieldsWidthConfig: customFieldsWidthConfig,
    getCustomFieldsConfig,
    handleDisplayColumnFieldsChange,
    handleDisplayColumnResize,
  };
};
