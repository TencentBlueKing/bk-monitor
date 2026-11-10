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

import { computed, defineAsyncComponent, type ComputedRef, defineComponent, KeepAlive, onBeforeUnmount, ref, watch } from 'vue';

import { debounce } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router';

import ClusteringLoader from '@/app/skeleton/clustering-loader.vue';
import SearchResultPanel from '../../workbench/search-result-panel/index.vue';
import SearchResultTab from '../../workbench/search-result-tab/index.vue';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import { RouteQueryTab } from '../index.type.tsx';
import useStore from '@/shared/composables/use-store';
import useRetrieveEvent from '@/shared/composables/use-retrieve-event';

import './index.scss';

const ResultPanelSkeleton = defineComponent({
  name: 'ResultPanelSkeleton',
  setup() {
    return () => (
      <div class='v3-result-panel-skeleton'>
        <ClusteringLoader
          width-list={[160, 120, 120, '']}
          loader-len={16}
          is-loading
        />
      </div>
    );
  },
});

// #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
const GraphAnalysis = defineAsyncComponent({
  loader: () =>
    import(/* webpackChunkName: 'retrieve-graph-analysis' */ '../../workbench/search-result-panel/graph-analysis/index'),
  loadingComponent: ResultPanelSkeleton,
  delay: 0,
});
// #else
// #code const GraphAnalysis = () => null
// #code const SearchResultTab = () => null;
// #endif
const Grep = defineAsyncComponent({
  loader: () => import(/* webpackChunkName: 'retrieve-grep' */ '../grep/index'),
  loadingComponent: ResultPanelSkeleton,
  delay: 0,
});
const LogClustering = defineAsyncComponent({
  loader: () => import(/* webpackChunkName: 'retrieve-log-clustering' */ './log-clustering/index'),
  loadingComponent: ResultPanelSkeleton,
  delay: 0,
});

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
    const activeTab = ref((route.query.tab as string) ?? 'origin');
    watch(
      () => route.query.tab,
      value => {
        activeTab.value = (value as string) ?? 'origin';
      },
    );

    let trendSearchTimer: ReturnType<typeof setTimeout> | null = null;

    const handleTabChange = (tab: string, triggerTrend = false) => {
      activeTab.value = tab;
      debounceUpdateTabValue(tab);

      if (triggerTrend) {
        store.dispatch('requestIndexSetQuery');
        if (trendSearchTimer) {
          clearTimeout(trendSearchTimer);
        }
        trendSearchTimer = setTimeout(() => {
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
          trendSearchTimer = null;
        }, 300);
      }
    };

    const handleFavoriteChange = (item: { favorite_type: string; }) => {
      debounceUpdateTabValue(item.favorite_type === 'chart' ? 'graph_analysis' : 'origin');
    };

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, handleFavoriteChange);

    onBeforeUnmount(() => {
      debounceUpdateTabValue.cancel();
      if (trendSearchTimer) {
        clearTimeout(trendSearchTimer);
        trendSearchTimer = null;
      }
    });

    const isGraphAnalysis = computed(
      () => activeTab.value === RouteQueryTab.GRAPH_ANALYSIS || activeTab.value === RouteQueryTab.GRAPH_ANALYSIS_LEGACY,
    );
    const isGrep = computed(() => activeTab.value === RouteQueryTab.GREP);
    const isClustering = computed(() => activeTab.value === RouteQueryTab.CLUSTERING);
    const isOrigin = computed(() => !isGraphAnalysis.value && !isGrep.value && !isClustering.value);
    const visitedTabs = ref<Record<string, boolean>>({
      [activeTab.value]: true,
    });
    watch(activeTab, value => {
      visitedTabs.value[value] = true;
    });

    return () => (
      <div class='v3-bklog-body'>
        <SearchResultTab
          value={activeTab.value}
          onInput={handleTabChange}
        ></SearchResultTab>
        <div class='v3-result-tab-content'>
          <div
            v-show={isOrigin.value}
            class={{ 'v3-tab-pane-active': isOrigin.value }}
          >
            <SearchResultPanel
              activeTab={activeTab.value}
              onUpdate:active-tab={handleTabChange}
            ></SearchResultPanel>
          </div>
          {(isGraphAnalysis.value || visitedTabs.value[RouteQueryTab.GRAPH_ANALYSIS] || visitedTabs.value[RouteQueryTab.GRAPH_ANALYSIS_LEGACY]) && (
            <div
              v-show={isGraphAnalysis.value}
              class={{ 'v3-tab-pane-active': isGraphAnalysis.value }}
            >
              <GraphAnalysis></GraphAnalysis>
            </div>
          )}
          {(isGrep.value || visitedTabs.value[RouteQueryTab.GREP]) && (
            <div
              v-show={isGrep.value}
              class={{ 'v3-tab-pane-active': isGrep.value }}
            >
              <Grep></Grep>
            </div>
          )}
          {(isClustering.value || visitedTabs.value[RouteQueryTab.CLUSTERING]) && (
            <div
              v-show={isClustering.value}
              class={{ 'v3-tab-pane-active': isClustering.value }}
            >
              <LogClustering />
            </div>
          )}
        </div>
      </div>
    );
  },
});
