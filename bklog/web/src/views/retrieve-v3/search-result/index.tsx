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

import { computed, type ComputedRef, defineComponent, onUnmounted } from 'vue';

import useStore from '@/hooks/use-store';
import { debounce } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';

// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import GraphAnalysis from '../../retrieve-v2/search-result-panel/graph-analysis';
// #else
// #code const GraphAnalysis = () => null
// #endif
import SearchResultPanel from '../../retrieve-v2/search-result-panel/index.vue';
// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
import SearchResultTab from '../../retrieve-v2/search-result-tab/index.vue';
// #else
// #code const SearchResultTab = () => null;

// #endif
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import Grep from '../grep';
import { MSearchResultTab } from '../type';

import './index.scss';

export default defineComponent({
  name: 'V3ResultContainer',
  setup() {
    const router = useRouter();
    const route = useRoute();
    const store = useStore();

    const debounceUpdateTabValue = debounce(value => {
      const isClustering = value === 'clustering';
      router.replace({
        params: { ...(route.params ?? {}) },
        query: {
          ...(route.query ?? {}),
          tab: value,
          ...(isClustering ? {} : { clusterParams: undefined }),
        },
      });
    }, 60);

    const activeTab = computed(() => route.query.tab ?? 'origin') as ComputedRef<string>;

    const handleTabChange = (tab: string, triggerTrend = false) => {
      debounceUpdateTabValue(tab);

      if (triggerTrend) {
        store.dispatch('requestIndexSetQuery');
        setTimeout(() => {
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
        }, 300);
      }
    };

    const handleFavoriteChange = item => {
      debounceUpdateTabValue(item.favorite_type === 'chart' ? 'graphAnalysis' : 'origin');
    };

    RetrieveHelper.on(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, handleFavoriteChange);

    onUnmounted(() => {
      RetrieveHelper.off(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, handleFavoriteChange);
    });

    const renderTabContent = () => {
      if (activeTab.value === MSearchResultTab.GRAPH_ANALYSIS) {
        return <GraphAnalysis></GraphAnalysis>;
      }

      if (activeTab.value === MSearchResultTab.GREP) {
        return <Grep></Grep>;
      }

      return (
        <SearchResultPanel
          active-tab={activeTab.value}
          onUpdate:active-tab={handleTabChange}
        ></SearchResultPanel>
      );
    };

    return () => (
      <div class='v3-bklog-body'>
        <SearchResultTab
          value={activeTab.value}
          on-input={handleTabChange}
        ></SearchResultTab>
        {renderTabContent()}
      </div>
    );
  },
});
