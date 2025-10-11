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

import { defineComponent, ref } from 'vue';

import RetrieveHelper from '../../retrieve-helper';
import V2SearchBar from '../../retrieve-v2/search-bar/index.vue';
import useLocale from '@/hooks/use-locale';

import './index.scss';
import useElementEvent from '@/hooks/use-element-event';

export default defineComponent({
  name: 'V3Searchbar',
  setup() {
    const { t } = useLocale();

    const searchBarHeight = ref(0);
    const searchBarRef = ref<any>(null);

    const aiSpanStyle = {
      'background': 'linear-gradient(115deg, #235DFA 0%, #E28BED 100%)',
      '-webkit-background-clip': 'text',
      'background-clip': 'text',
      '-webkit-text-fill-color': 'transparent',
      'color': 'transparent',
      'font-size': '12px',
    };

    const aiBtnStyle = {
      'font-size': '12px',
      'color': '#313238',
      'width': 'max-content',
      'background-image': 'linear-gradient(-79deg, #F1EDFA 0%, #EBF0FF 100%)',
      'border-radius': '12px',
    };

    /**
     * 用于处理搜索栏高度变化
     * @param height 搜索栏高度
     */
    const handleHeightChange = height => {
      searchBarHeight.value = height;
      RetrieveHelper.setSearchBarHeight(height);
      // update ai assitant options
    };

    /**
     * 添加事件
     */
    const { addElementEvent } = useElementEvent();
    addElementEvent(document.body, 'click', (e: MouseEvent) => {
      RetrieveHelper.aiAssitantHelper.closeAiAssitantWithSearchBar(e);
    });

    const handleAiSpanClick = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
      const rect = searchBarRef.value?.getRect();
      const left = rect?.left;
      const top = rect?.top + rect?.height + 4;
      const width = rect?.width;

      RetrieveHelper.aiAssitantHelper.showAiAssitant({
        defaultLeft: left,
        defaultTop: top,
        defaultWidth: width,
        defaultHeight: 400,
        draggable: false,
        title: t('AI编辑'),
      });
    };

    /**
     * 渲染搜索栏
     * @returns 
     */
    return () => (
      <V2SearchBar
        class='v3-search-bar-root'
        ref={searchBarRef}
        on-height-change={handleHeightChange}
        {...{
          scopedSlots: {
            'custom-placeholder': () => (
              <span
                style={aiSpanStyle}
                onClick={handleAiSpanClick}
              >
                {t('使用AI编辑')}
              </span>
            ),
            'search-tool': () => (
              <span onClick={handleAiSpanClick} style={aiBtnStyle}>
                {t('AI编辑')}
              </span>
            ),
          },
        }}
      >
      </V2SearchBar>
    );
  },
});
