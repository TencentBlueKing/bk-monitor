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
import { computed, shallowRef } from 'vue';
import type { Ref } from 'vue';

import { Message } from 'bkui-vue';
import { updateFavorite } from 'monitor-api/modules/model';
import { useI18n } from 'vue-i18n';

import { EMode } from '../../../components/retrieval-filter/typing';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useAppStore } from '../../../store/modules/app';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { RUM_FAVORITE_TYPE } from '../constants';

import type { IWhereItem } from '../../../components/retrieval-filter/typing';
import type { IRumFavoriteConfig } from '../typings';

interface IRumFavoriteItem {
  config: IRumFavoriteConfig;
  id: number;
  name: string;
}

interface IUseRumFavoriteOptions {
  commonWhere: Ref<IWhereItem[]>;
  /** 表格当前展示的列，随收藏一起保存 */
  displayFields: Ref<string[]>;
  filterMode: Ref<EMode>;
  queryString: Ref<string>;
  where: Ref<IWhereItem[]>;
  /** 收藏应用完成后触发一次查询 */
  onApplied: () => void;
}

/**
 * 收藏读写。
 *
 * 收藏配置与 trace 检索保持同构（queryParams + componentData），
 * 这样收藏夹组件不需要为 RUM 增加分支就能渲染列表与详情。
 */
export function useRumFavorite(options: IUseRumFavoriteOptions) {
  const { t } = useI18n();
  const appStore = useAppStore();
  const store = useRumExploreStore();

  const currentFavorite = shallowRef<IRumFavoriteItem | null>(null);
  const editFavoriteShow = shallowRef(false);
  const editFavoriteData = shallowRef(null);
  /** 收藏夹侧栏是否展开 */
  const favoriteShow = shallowRef(false);

  /** 传给检索条件区，用于判断当前条件相对收藏是否有改动 */
  const selectedFavorite = computed(() => {
    if (!currentFavorite.value) return null;
    return {
      commonWhere: currentFavorite.value.config?.componentData?.commonWhere || [],
      where: currentFavorite.value.config?.queryParams?.filters || [],
    };
  });

  function buildPayload() {
    const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
    const isQueryStringMode = options.filterMode.value === EMode.queryString;
    return {
      config: {
        bk_biz_id: appStore.bizId,
        componentData: {
          mode: store.mode,
          spanType: store.spanType,
          filterMode: options.filterMode.value,
          commonWhere: options.commonWhere.value,
          timeRange: store.timeRange,
          refreshInterval: store.refreshInterval,
          displayFields: options.displayFields.value,
        },
        queryParams: {
          app_name: store.appName,
          mode: store.mode,
          start_time: startTime,
          end_time: endTime,
          filters: isQueryStringMode ? [] : options.where.value,
          query: isQueryStringMode ? options.queryString.value : '',
          sort: store.sortParams,
        },
      },
    };
  }

  /**
   * @param isEdit 为 true 时直接更新当前收藏，否则打开新建收藏弹窗
   * @param onUpdated 更新成功后的回调，用于刷新收藏夹列表
   */
  async function saveFavorite(isEdit = false, onUpdated?: () => void) {
    const payload = buildPayload();
    if (!isEdit || !currentFavorite.value) {
      editFavoriteData.value = payload;
      editFavoriteShow.value = true;
      return;
    }
    await updateFavorite(currentFavorite.value.id, { type: RUM_FAVORITE_TYPE, ...payload });
    onUpdated?.();
    Message({ theme: 'success', message: t('收藏成功') });
  }

  /** 选中或清除收藏，把收藏里的查询条件回填到页面 */
  function applyFavorite(favorite: IRumFavoriteItem | null) {
    currentFavorite.value = favorite || null;
    if (!favorite) {
      options.where.value = [];
      options.commonWhere.value = [];
      options.queryString.value = '';
      options.onApplied();
      return;
    }
    const { componentData, queryParams } = favorite.config || ({} as IRumFavoriteConfig);
    // 收藏的 filters 已经包含常驻条件，回填时不再单独设置 commonWhere，避免条件翻倍
    options.where.value = queryParams?.filters || [];
    options.commonWhere.value = [];
    options.queryString.value = queryParams?.query || '';
    options.filterMode.value = componentData?.filterMode || EMode.ui;
    store.init({
      mode: queryParams?.mode || store.mode,
      appName: queryParams?.app_name || store.appName,
      timeRange: componentData?.timeRange,
      timezone: store.timezone,
      refreshInterval: componentData?.refreshInterval,
      spanType: componentData?.spanType,
      sortParams: queryParams?.sort || [],
    });
    options.onApplied();
  }

  /** 收藏夹新开标签页 */
  function openFavoriteInBlank(favorite: IRumFavoriteItem, routePath: string) {
    const href = `${location.origin}${location.pathname}?bizId=${appStore.bizId}#${routePath}`;
    window.open(`${href}?favorite_id=${favorite.id}`, '_blank');
  }

  return {
    currentFavorite,
    editFavoriteData,
    editFavoriteShow,
    favoriteShow,
    selectedFavorite,
    applyFavorite,
    openFavoriteInBlank,
    saveFavorite,
  };
}
