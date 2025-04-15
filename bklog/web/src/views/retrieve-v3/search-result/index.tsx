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
import { debounce } from 'lodash';
import useStore from '@/hooks/use-store';
import { useRoute, useRouter } from 'vue-router/composables';
import SearchResultPanel from '../../retrieve-v2/search-result-panel/index.vue';
import SearchResultTab from '../../retrieve-v2/search-result-tab/index.vue';
import GraphAnalysis from '../../retrieve-v2/search-result-panel/graph-analysis';
import './index.scss';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

export default defineComponent({
  name: 'v3-container',
  setup(_, { slots }) {
    const activeTab = ref('origin');
    const store = useStore();
    const router = useRouter();
    const route = useRoute();

    watch(
      () => store.state.indexItem.isUnionIndex,
      () => {
        if (store.state.indexItem.isUnionIndex && activeTab.value === 'clustering') {
          activeTab.value = 'origin';
        }
      },
    );

    RetrieveHelper.on(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, item => {
      activeTab.value = item.favorite_type === 'chart' ? 'graphAnalysis' : 'origin';
    });

    const debounceUpdateTabValue = debounce(() => {
      const isClustering = activeTab.value === 'clustering';
      router.replace({
        params: { ...(route.params ?? {}) },
        query: {
          ...(route.query ?? {}),
          tab: activeTab.value,
          ...(isClustering ? {} : { clusterParams: undefined }),
        },
      });
    }, 60);

    watch(
      () => activeTab.value,
      () => {
        debounceUpdateTabValue();
      },
      { immediate: true },
    );

    const showAnalysisTab = computed(() => activeTab.value === 'graphAnalysis');
    const handleTabChange = (tab: string) => {
      activeTab.value = tab;
    };

    return () => (
      <div class='v3-bklog-body'>
        <SearchResultTab
          value={activeTab.value}
          on-input={handleTabChange}
        ></SearchResultTab>
        {showAnalysisTab.value ? (
          <GraphAnalysis></GraphAnalysis>
        ) : (
          <SearchResultPanel
            active-tab={activeTab.value}
            onUpdate:active-tab={handleTabChange}
          ></SearchResultPanel>
        )}
      </div>
    );
  },
});
