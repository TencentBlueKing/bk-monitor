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

import { computed, ComputedRef, defineComponent } from 'vue';
import { debounce } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';
import SearchResultPanel from '../../retrieve-v2/search-result-panel/index.vue';
import SearchResultTab from '../../retrieve-v2/search-result-tab/index.vue';
import GraphAnalysis from '../../retrieve-v2/search-result-panel/graph-analysis';
import './index.scss';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

export default defineComponent({
  name: 'v3-container',
  setup(_, { slots }) {
    const router = useRouter();
    const route = useRoute();

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
    const showAnalysisTab = computed(() => activeTab.value === 'graphAnalysis');

    const handleTabChange = (tab: string) => {
      debounceUpdateTabValue(tab);
    };

    RetrieveHelper.on(RetrieveEvent.FAVORITE_ACTIVE_CHANGE, item => {
      debounceUpdateTabValue(item.favorite_type === 'chart' ? 'graphAnalysis' : 'origin');
    });

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
