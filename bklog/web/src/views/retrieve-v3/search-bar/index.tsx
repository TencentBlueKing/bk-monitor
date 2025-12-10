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

import { computed, defineComponent, ref, nextTick } from 'vue';

import useElementEvent from '@/hooks/use-element-event';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import useRetrieveParams from '@/hooks/use-retrieve-params';
import aiBluekingSvg from '@/images/ai/ai-bluking-2.svg';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import V2SearchBar from '../../retrieve-v2/search-bar/index.vue';
import V3AiMode from './ai-mode/index';
import { useRoute, useRouter } from 'vue-router/composables';
import { bkMessage } from 'bk-magic-vue';

import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { AiQueryResult } from './types';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { SET_APP_STATE } from '@/store';

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
    const aiModeRef = ref<any>(null);

    const isAiLoading = ref(false);
    const searchMode = ref<'normal' | 'ai'>('normal');
    const aiQueryResult = ref<AiQueryResult>({ startTime: '', endTime: '', queryString: '' });
    const aiFilterList = computed<string[]>(() => (store.state.aiMode.filterList ?? [])
      .filter(f => !/^\s*\*?\s*$/.test(f)));

    const { setRouteParamsByKeywordAndAddition } = useRetrieveParams();

    // const aiSpanStyle = {
    //   background: 'linear-gradient(115deg, #235DFA 0%, #E28BED 100%)',
    //   '-webkit-background-clip': 'text',
    //   'background-clip': 'text',
    //   '-webkit-text-fill-color': 'transparent',
    //   color: 'transparent',
    //   'font-size': '12px',
    //   cursor: 'pointer',
    // };

    // const aiSpanWrapperStyle = {
    //   display: 'flex',
    //   'align-items': 'center',
    //   gap: '4px',
    //   'font-size': '12px',
    //   color: '#c4c6cc',
    // };

    const shortcutKeyStyle = {
      width: '20px',
      height: '20px',
      background: '#A3B1CC',
      borderRadius: '10px',
      color: '#ffffff',
      fontSize: '14px',
      textAlign: 'center' as const,
      display: 'inline-flex' as const,
      alignItems: 'center' as const,
      justifyContent: 'center' as const,
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
    const formatValue = computed(() => store.getters.retrieveParams.format);

    /**
     * 当前搜索模式：'ui' | 'sql'
     */
    const currentSearchMode = computed<'ui' | 'sql'>(() =>
      store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE] === 1 ? 'sql' : 'ui'
    );
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
     * 处理 Tab 键切换模式
     * @param e 键盘事件
     */
    const handleTabKeyPress = (e: KeyboardEvent) => {
      if (isAiLoading.value) {
        return;
      }
      // 检查是否按下了 Tab 键（排除 Shift+Tab）
      if ((e.key === 'Tab' || e.keyCode === 9) && !e.shiftKey) {
        // 如果当前焦点在搜索栏相关的输入框内，才处理切换
        const activeElement = document.activeElement;
        const isSearchBarInput = activeElement?.closest('.v3-search-bar-root')
          || activeElement?.closest('.search-bar-container')
          || activeElement?.closest('.v3-ai-mode');

        if (!isSearchBarInput) {
          return;
        }

        // 阻止默认的 Tab 行为
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        // 切换模式
        if (searchMode.value === 'normal') {
          searchMode.value = 'ai';
          const keyword = store.getters.retrieveParams.keyword;
          store.state.aiMode.filterList = [keyword].filter(f => !/^\s*\*?\s*$/.test(f));
          store.state.aiMode.active = true;
          store.state.indexItem.keyword = '';

          // 打点：通过Tab键切换到AI模式
          RetrieveHelper.reportLog({
            ai_scenario: 'tab_switch',
            trigger_source: 'tab_key',
          }, store.state);

          // 切换到 AI 模式后，聚焦到 AI 输入框
          nextTick(() => {
            const aiModeEl = aiModeRef.value?.$el || aiModeRef.value;
            const aiTextarea = aiModeEl?.querySelector?.('textarea');
            if (aiTextarea) {
              aiTextarea.focus();
            }
          });
        } else {
          // 先更新 storage 和 indexItem，确保 V2SearchBar 能读取到正确的模式
          store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 1 });
          store.commit('updateIndexItemParams', { keyword: aiFilterList.value.join(' AND '), search_mode: 'sql' });

          // 更新路由参数以同步状态（需要在 nextTick 之前更新，确保路由参数正确）
          setRouteParamsByKeywordAndAddition();

          searchMode.value = 'normal';
          store.state.aiMode.active = false;
          store.state.aiMode.filterList = [];
          Object.assign(aiQueryResult.value, { startTime: '', endTime: '', queryString: '' });

          // 切换到常规模式后，点击搜索框容器以触发自动 focus
          nextTick(() => {
            const searchBarEl = searchBarRef.value?.$el || searchBarRef.value;
            // 找到搜索框容器，点击后会自动触发 focus
            const searchInputContainer = searchBarEl?.querySelector?.('.search-bar-container')
              || searchBarEl?.querySelector?.('.search-input');
            if (searchInputContainer) {
              searchInputContainer.click();
            }
          });
        }
      }
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

    addElementEvent(document, 'keydown', handleTabKeyPress, { capture: true });

    /**
     * 使用AI编辑
     * @param e 鼠标事件
     */
    const handleAiSpanClick = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();

      // 打点：点击AI编辑按钮打开对话框
      RetrieveHelper.reportLog({
        ai_scenario: 'ai_edit_dialog',
        trigger_source: `${currentSearchMode.value}_mode`,
      }, store.state);

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
     * @param triggerSource 触发来源：'ui_mode' | 'sql_mode' | 'ai_mode'
     * @returns {void}
     */
    const handleTextToQuery = (value: string, triggerSource: 'ui_mode' | 'sql_mode' | 'ai_mode' = 'ai_mode'): void => {
      isAiLoading.value = true;

      // 打点：AI 自动补全（统计所有来源：UI/SQL/AI 模式）
      RetrieveHelper.reportLog({
        ai_scenario: 'auto_complete',
        trigger_source: triggerSource,
      }, store.state);

      RetrieveHelper.aiAssitantHelper
        .requestTextToQueryString({
          index_set_id: store.state.indexItem.ids[0],
          description: value,
          domain: window.location.origin,
          fields: fieldsJsonValue.value,
          keyword: value,
        })
        .then((resp) => {
          const content = resp.choices[0]?.delta?.content ?? '{}';
          try {
            const contentObj = JSON.parse(content);
            const { end_time: endTime, start_time: startTime, query_string: queryString } = contentObj;
            const queryParams = { search_mode: 'sql' };
            let needReplace = false;
            if (startTime && endTime) {
              const results = handleTransformToTimestamp([startTime, endTime], formatValue.value);
              Object.assign(queryParams, { start_time: results[0], end_time: results[1] });
              store.commit('updateIndexItemParams', { datePickerValue: [startTime, endTime] });
              aiQueryResult.value.startTime = startTime;
              aiQueryResult.value.endTime = endTime;
              needReplace = true;
            }

            if (queryString) {
              Object.assign(queryParams, { keyword: queryString });
              needReplace = true;
              aiQueryResult.value.queryString = queryString;
            }

            if (needReplace) {
              store.commit('updateIndexItemParams', queryParams);
              store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 1 });

              router
                .replace({
                  name: 'retrieve',
                  params: route.params,
                  query: {
                    ...route.query,
                    ...queryParams,
                  },
                })
                .then(() => {
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

    const handleEditSql = () => {
      searchMode.value = 'normal';
    };

    /**
     * 处理 filterList 变化
     * @param newFilterList 新的 filterList
     */
    const handleFilterChange = (newFilterList: string[]) => {
      // 更新 store 中的 filterList
      store.state.aiMode.filterList = newFilterList;
      // 触发查询
      store.dispatch('requestIndexSetQuery');
      // 更新 URL 参数
      setRouteParamsByKeywordAndAddition();
    };

    /**
     * 渲染搜索栏
     * @returns
     */
    return () => {
      if (searchMode.value === 'ai') {
        return (
          <div class='v3-search-bar-root'>
            <V3AiMode
              ref={aiModeRef}
              is-ai-loading={isAiLoading.value}
              ai-query-result={aiQueryResult.value}
              filter-list={aiFilterList.value}
              on-height-change={handleHeightChange}
              on-text-to-query={(value: string) => {
                handleTextToQuery(value, 'ai_mode');
              }}
              on-edit-sql={handleEditSql}
              on-filter-change={handleFilterChange}
            />
          </div>
        );
      }

      return (
        <V2SearchBar
          class='v3-search-bar-root'
          ref={searchBarRef}
          on-height-change={handleHeightChange}
          on-text-to-query={(value: string) => {
            // 根据当前模式确定触发来源
            const triggerSource = `${currentSearchMode.value}_mode` as 'ui_mode' | 'sql_mode';
            handleTextToQuery(value, triggerSource);
          }}
          is-ai-loading={isAiLoading.value}
          {...{
            scopedSlots: {
              // 'custom-placeholder'(slotProps) {
              //   if (isAiAssistantActive.value) {
              //     return (
              //       <span style={aiSpanWrapperStyle}>
              //         {slotProps.isEmptyText ? t('或') : ''}
              //         <span
              //           style={aiSpanStyle}
              //           onClick={handleAiSpanClick}
              //         >
              //           {t('使用AI编辑')}
              //         </span>
              //       </span>
              //     );
              //   }
              //   return null;
              // },
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
                      <span style={shortcutKeyStyle}>
                        <i class="bklog-icon bklog-key-tab"></i>
                      </span>

                    </span>
                  );
                }
                return null;
              },
            },
          }}
        ></V2SearchBar>
      );
    };
  },
});
