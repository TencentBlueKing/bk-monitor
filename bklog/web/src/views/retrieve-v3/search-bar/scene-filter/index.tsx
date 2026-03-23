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

import { computed, defineComponent, ref } from 'vue';

import useStore from '@/hooks/use-store';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { useRoute, useRouter } from 'vue-router/composables';

import V3Searchbar from '../index';
import FilterPanel from './filter-panel';
import { getAllSceneFieldNames } from './scene-config';
import { SceneType } from './types';
import type { FilterValues, SceneDisplayFields } from './types';

import './index.scss';

export default defineComponent({
  name: 'SceneFilter',
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const activeScene = computed<SceneType>({
      get: () => store.state.indexItem.scene_active || SceneType.Container,
      set: (val: SceneType) => {
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
      const { scene_active, scene_filter_values } = store.getters.retrieveParams;
      const resolver = new RetrieveUrlResolver({
        scene_active,
        scene_filter_values,
      });

      // 先清除所有可能的场景筛选字段，避免切换场景时残留旧字段
      const cleanQuery = { ...route.query };
      for (const name of getAllSceneFieldNames()) {
        cleanQuery[name] = undefined;
      }

      router.replace({
        query: { ...cleanQuery, ...resolver.resolveParamsToUrl() },
      });
    };

    const handleSceneChange = (type: SceneType) => {
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

    return () => (
      <div class='scene-filter-root'>
        <div class='scene-filter-panel-wrapper'>
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
      </div>
    );
  },
});
