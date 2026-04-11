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

import { computed, defineComponent, ref, watch } from 'vue';

import { getOs } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { isEqual } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router/composables';

import { RetrieveEvent } from '../../../retrieve-helper';
import SceneFilterTags from '../../../retrieve-v2/sub-bar/scene-filter-tags';
import V3Searchbar from '../index';
import FilterPanel from './filter-panel';
import { getAllSceneFieldKeys } from './scene-config';
import { SceneType } from './types';
import type { FilterValues, SceneDisplayFields } from './types';

import './index.scss';

export default defineComponent({
  name: 'SceneFilter',
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    const activeScene = computed<string>({
      get: () => store.state.indexItem.scene_active || SceneType.Container,
      set: (val: string) => {
        store.commit('updateIndexItem', { scene_active: val });
      },
    });

    const filterValues = computed<FilterValues>({
      get: () => store.state.indexItem.scene_filter_values ?? {},
      set: (val: FilterValues) => {
        store.commit('updateIndexItem', { scene_filter_values: val });
      },
    });

    const syncUrlParams = () => {
      const { scene_active, scene_filter_values } = store.state.indexItem;
      const resolver = new RetrieveUrlResolver({
        scene_active,
        scene_filter_values,
      });

      // 先清除所有可能的场景筛选字段，避免切换场景时残留旧字段
      const cleanQuery = { ...route.query };
      for (const key of getAllSceneFieldKeys(sceneConfigs.value)) {
        cleanQuery[key] = undefined;
      }

      router.replace({
        query: { ...cleanQuery, ...resolver.resolveParamsToUrl() },
      });
    };

    const handleSceneChange = (type: string) => {
      activeScene.value = type;
      filterValues.value = {};
      syncUrlParams();
    };

    const handleFilterChange = (values: FilterValues) => {
      filterValues.value = values;
      syncUrlParams();
    };

    const handleClear = () => {
      filterValues.value = {};
      syncUrlParams();
    };

    // 每场景独立的显示字段配置
    const sceneDisplayFields = ref<SceneDisplayFields>({});

    const currentDisplayFields = computed<string[] | null>(
      () => sceneDisplayFields.value[activeScene.value] ?? null,
    );

    const handleDisplayFieldsChange = (fields: string[] | null) => {
      sceneDisplayFields.value = {
        ...sceneDisplayFields.value,
        [activeScene.value]: fields,
      };
    };

    // ---- 条件变更提示条逻辑 ----
    const { t } = useLocale();
    const { addEvent } = useRetrieveEvent();

    /** 是否已经执行过至少一次查询 */
    const hasQueried = ref(false);
    /** 上次查询时的 filterValues 快照 */
    const lastQueriedFilterValues = ref<FilterValues | null>(null);
    /** 是否显示提示条 */
    const showQueryHint = ref(false);

    /** 上次查询时的 activeScene 快照 */
    const lastQueriedScene = ref<string | null>(null);

    // 监听查询事件，记录快照并隐藏提示条
    addEvent(RetrieveEvent.SEARCH_VALUE_CHANGE, () => {
      hasQueried.value = true;
      lastQueriedFilterValues.value = JSON.parse(JSON.stringify(store.state.indexItem.scene_filter_values ?? {}));
      lastQueriedScene.value = activeScene.value;
      showQueryHint.value = false;
    });

    // 监听索引集切换，重置快照
    addEvent(RetrieveEvent.INDEX_SET_ID_CHANGE, () => {
      hasQueried.value = false;
      lastQueriedFilterValues.value = null;
      lastQueriedScene.value = null;
      showQueryHint.value = false;
    });

    // 监听 filterValues 和 activeScene 变化，对比快照
    watch(
      [filterValues, activeScene],
      ([newFilterValues, newScene]) => {
        if (!hasQueried.value || lastQueriedFilterValues.value === null) return;
        const filtersChanged = !isEqual(newFilterValues, lastQueriedFilterValues.value);
        const sceneChanged = newScene !== lastQueriedScene.value;
        showQueryHint.value = filtersChanged || sceneChanged;
      },
      { deep: true },
    );

    const shortcutKey = getOs() === 'macos' ? 'cmd+shift+enter' : 'ctrl+shift+enter';

    const hintText = () => t('检索条件有变更，请点击{icon}按钮重新查询{shortcut}', {
      icon: '🔍',
      shortcut: `(${shortcutKey})`,
    });

    return () => (
      <div class='scene-filter-root'>
        <div class='scene-filter-panel-wrapper'>
          <SceneFilterTags class='scene-filter-tags-sticky' />
          <FilterPanel
            activeScene={activeScene.value}
            filterValues={filterValues.value}
            displayFields={currentDisplayFields.value}
            on-scene-change={handleSceneChange}
            on-filter-change={handleFilterChange}
            on-clear={handleClear}
            on-display-fields-change={handleDisplayFieldsChange}
          />
        </div>
        <V3Searchbar />
        <transition name='slide-hint'>
          {showQueryHint.value && (
            <div class='query-hint-bar'>
              <i class='bklog-icon bklog-circle-alert-filled query-hint-icon' />
              <span class='query-hint-text'>{hintText()}</span>
            </div>
          )}
        </transition>
      </div>
    );
  },
});
