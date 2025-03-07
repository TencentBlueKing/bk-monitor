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

import V3Collection from './collection';
import V3Container from './container';
import V3Searchbar from './search-bar';
import V3SearchResult from './search-result';
import V3Toolbar from './toolbar';
import useAppInit from './use-app-init';

import './index.scss';

export default defineComponent({
  name: 'RetrieveV3',
  setup() {
    const collectWidth = ref(240);
    const isCollectShow = ref(false);
    const handleCollectionShowChange = () => {
      isCollectShow.value = !isCollectShow.value;
    };

    const { isStickyTop } = useAppInit();
    const handleWidthChange = (width: number) => {
      collectWidth.value = width;
    };

    const contentStyle = computed(() => {
      if (isCollectShow.value) {
        return { width: `calc(100% - ${collectWidth.value}px)` };
      }

      return { width: '100%' };
    });

    return () => (
      <div class='v3-bklog-root'>
        <V3Collection
          is-show={isCollectShow.value}
          onWidth-change={handleWidthChange}
        ></V3Collection>
        <div
          class='v3-bklog-content'
          style={contentStyle.value}
        >
          <V3Toolbar
            isCollectShow={isCollectShow.value}
            on-collection-show-change={handleCollectionShowChange}
          ></V3Toolbar>
          <V3Container>
            <V3Searchbar class={{ 'is-sticky-top': isStickyTop.value }}></V3Searchbar>
            <V3SearchResult></V3SearchResult>
          </V3Container>
        </div>
      </div>
    );
  },
});
