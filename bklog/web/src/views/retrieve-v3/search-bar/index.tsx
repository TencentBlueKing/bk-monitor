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

import useElementEvent from '@/hooks/use-element-event';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import aiBluekingSvg from '@/images/ai/ai-bluking-2.svg';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import V2SearchBar from '../../retrieve-v2/search-bar/index.vue';
import { useRoute, useRouter } from 'vue-router/composables';
import { bkMessage } from 'bk-magic-vue';


import './index.scss';

export default defineComponent({
  name: 'V3Searchbar',
  setup() {
    const { t } = useLocale();
    const store = useStore();
    const router = useRouter();
    const route = useRoute();

    const searchBarHeight = ref(0);
    const searchBarRef = ref<any>(null);

    const isAiLoading = ref(false);

    const aiSpanStyle = {
      background: 'linear-gradient(115deg, #235DFA 0%, #E28BED 100%)',
      '-webkit-background-clip': 'text',
      'background-clip': 'text',
      '-webkit-text-fill-color': 'transparent',
      color: 'transparent',
      'font-size': '12px',
      cursor: 'pointer',
    };

    const aiSpanWrapperStyle = {
      display: 'flex',
      'align-items': 'center',
      gap: '4px',
      'font-size': '12px',
      color: '#c4c6cc',
    };

    /**
     * 获取字段配置
     */
    const fieldsJsonValue = computed(() => {
      const fieldConfig = store.state.indexFieldInfo.fields.reduce((acc, field) => {
        return {
          ...acc,
          [field.field_name]: {
            type: field.field_type,
            ...(field.query_alias ? { query_alias: field.query_alias } : {}),
          },
        };
      }, {});

      return JSON.stringify(fieldConfig);
    });

    /**
     * 是否激活AI助手
     * @TODO 本周发布BKOP开启助手，上云环境关闭助手，此处需要暂时调整为 false
     */
    const isAiAssistantActive = computed(() => store.state.features.isAiAssistantActive);

    /**
     * 更新AI助手位置
     */
    const updateAiAssitantPosition = () => {
      if (RetrieveHelper.aiAssitantHelper.isShown()) {
        const rect = searchBarRef.value?.getRect();
        const left = rect?.left;
        const top = rect?.top + rect?.height + 4;
        const width = rect?.width;
        const height = 480;
        RetrieveHelper.aiAssitantHelper.setPosition(left, top, width, height);
      }
    };

    /**
     * 用于处理搜索栏高度变化
     * @param height 搜索栏高度
     */
    const handleHeightChange = (height) => {
      if (height === searchBarHeight.value || RetrieveHelper.aiAssitantHelper.activePosition !== 'search-bar') {
        return;
      }

      searchBarHeight.value = height;
      RetrieveHelper.setSearchBarHeight(height);
      updateAiAssitantPosition();
    };

    /**
     * 监听搜索栏Size变化，更新AI助手位置
     */
    useResizeObserve(() => searchBarRef.value, updateAiAssitantPosition);

    /**
     * 添加事件
     */
    const { addElementEvent } = useElementEvent();
    addElementEvent(document.body, 'click', (e: MouseEvent) => {
      RetrieveHelper.aiAssitantHelper.closeAiAssitantWithSearchBar(e);
    });

    /**
     * 使用AI编辑
     * @param e 鼠标事件
     */
    const handleAiSpanClick = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
      const rect = searchBarRef.value?.getRect();
      const left = rect?.left;
      const top = rect?.top + rect?.height + 4;
      const width = rect?.width;

      RetrieveHelper.aiAssitantHelper.showAiAssitant(
        {
          defaultLeft: left,
          defaultTop: top,
          defaultWidth: width,
          defaultHeight: 560,
          draggable: false,
          defaultChatInputPosition: 'bottom',
          showCompressionIcon: false,
          showNewChatIcon: false,
          showMoreIcon: false,
          maxWidth: '100%',
          title: t('AI编辑'),
        },
        {
          index_set_id: store.state.indexItem.ids[0],
          description: '',
          domain: window.location.origin,
          fields: fieldsJsonValue.value,
        },
      );
    };

    /**
     * 使用AI编辑
     * @param value 查询语句
     * @returns {void}
     */
    const handleTextToQuery = (value: string): void => {
      isAiLoading.value = true;
      RetrieveHelper.aiAssitantHelper.requestTextToQueryString({
        index_set_id: store.state.indexItem.ids[0],
        description: value,
        domain: window.location.origin,
        fields: fieldsJsonValue.value,
        keyword: value,
      }).then((resp) => {
        const content = resp.choices[0]?.delta?.content ?? '{}';
        try {
          const contentObj = JSON.parse(content);
          const queryString = contentObj.query_string;
          if (queryString) {
            store.commit('updateIndexItemParams', { keyword: queryString });
            router.replace({
              name: 'retrieve',
              params: route.params,
              query: {
                ...route.query,
                keyword: queryString,
              },
            }).then(() => {
              RetrieveHelper.fire(RetrieveEvent.SEARCH_VALUE_CHANGE);
              store.dispatch('requestIndexSetQuery');
            });
          }
        } catch (e) {
          console.error(e);
          bkMessage({
            theme: 'error',
            message: e.message,
          });
        }
      })
        .finally(() => {
          isAiLoading.value = false;
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
        on-text-to-query={handleTextToQuery}
        v-bkloading={{ isLoading: isAiLoading.value, opacity: 0.8, theme: 'colorful', size: 'mini', title: t('正在解析语句'), extCls: 'v3-search-ai-loading' }}
        {...{
          scopedSlots: {
            'custom-placeholder'(slotProps) {
              if (isAiAssistantActive.value) {
                return (
                  <span style={aiSpanWrapperStyle}>
                    {slotProps.isEmptyText ? t('或') : ''}
                    <span
                      style={aiSpanStyle}
                      onClick={handleAiSpanClick}
                    >
                      {t('使用AI编辑')}
                    </span>
                  </span>
                );
              }
              return null;
            },
            'search-tool': () => {
              if (isAiAssistantActive.value) {
                return (
                  <span
                    class='bklog-ai-edit-btn'
                    onClick={handleAiSpanClick}
                  >
                    <img
                      src={aiBluekingSvg}
                      alt='AI编辑'
                      style={{ width: '16px', height: '16px' }}
                    />
                    {t('AI编辑')}
                  </span>
                );
              }
              return null;
            },
          },
        }}
      ></V2SearchBar>
    );
  },
});
