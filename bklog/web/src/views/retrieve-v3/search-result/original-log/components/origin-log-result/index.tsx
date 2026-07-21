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
import { defineComponent, ref, watch, computed, onMounted, onBeforeUnmount } from 'vue';

import axios from 'axios';
import { readBlobRespToJson, parseBigNumberList } from '@/common/util';

import JsonFormatter from '@/global/json-formatter.vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import SearchBar from '@/views/retrieve-v2/search-bar/index.vue';
import { cloneDeep, debounce } from 'lodash-es';
import RetrieveHelper from '@/views/retrieve-helper';
import { buildHighlightHtml, parseResultMarkedText } from '@/views/retrieve-core/page-highlight';
import { retrieveRowCacheService } from '@/storage';
import type { RetrieveRowRenderMeta } from '@/storage/utils/retrieve-render-meta';
import { resolveAddToSearch } from '@/hooks/log-query-compiler';

import RenderJsonCell from './render-json-cell';
import { axiosInstance } from '@/api';

import './index.scss';

export default defineComponent({
  name: 'LogResult',
  props: {
    indexSetId: {
      type: Number,
      default: 0,
    },
    logIndex: {
      type: Number,
      default: 0,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const searchBarRef = ref<any>();
    const tableRef = ref<HTMLElement>();
    const logList = ref<any[]>([]);
    const renderMetaList = ref<(RetrieveRowRenderMeta | undefined)[]>([]);
    const cachedRowKeys = ref<string[]>([]);
    const choosedIndex = ref(props.logIndex);
    const listLoading = ref(false);
    const isCollapsed = ref(false);
    const exceptionMsg = ref('');

    const fieldsMap = computed(() => store.getters.rawFieldList.reduce((dataMap, item) => {
      dataMap[item.field_name] = item;
      return dataMap;
    }, {}),
    );

    const timeField = computed(() => store.state.indexFieldInfo.time_field);
    const timeFieldType = computed(() => fieldsMap.value[timeField.value]?.field_type);
    const visibleFields = computed(() => store.getters.visibleFields);

    const requestOtherparams = cloneDeep(props.retrieveParams);
    delete requestOtherparams.format;

    // 隐藏掉tippy弹出框中的非必要按钮
    const styleContent = `
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(1),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(2),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(5) {
        display: none !important;
      }
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(3),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(4) {
        .segment-new-link {
          display: none !important;
        }
      }
    `;

    let styleElement: any = null;
    let begin = 0;
    const size = 50;
    let total = 0;
    let isUnmounted = false;
    let requestSeq = 0;
    let abortController: AbortController | null = null;
    let scrollIntoViewTimer: ReturnType<typeof setTimeout> | null = null;

    const isMonitorApm = window.__IS_MONITOR_APM__;

    watch(
      () => props.logIndex,
      () => {
        choosedIndex.value = props.logIndex;
      },
      {
        immediate: true,
      },
    );

    const setExceptionMsg = (message = '') => {
      exceptionMsg.value = message || '';
    };

    const isRequestCanceled = (error: any) =>
      axios.isCancel(error)
      || error?.code === 'ERR_CANCELED'
      || error?.name === 'CanceledError'
      || error?.name === 'AbortError';

    /** 取消进行中的检索请求，保证永远只有最后一次生效 */
    const cancelPendingRequest = () => {
      if (!abortController) {
        return;
      }
      abortController.abort();
      abortController = null;
    };

    const requestLogList = (isManualSearch = true) => {
      // 新请求发起前先取消旧请求，避免乱序回写
      cancelPendingRequest();
      const controller = new AbortController();
      abortController = controller;
      const currentRequestSeq = ++requestSeq;

      listLoading.value = true;
      if (begin === 0) {
        setExceptionMsg('');
      }
      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
      const searchUrl = store.getters.isSceneMode
        ? '/search/scene/search/'
        : `/search/index_set/${props.indexSetId}/search/`;
      const requestData = {
        ...requestOtherparams,
        sort_list: store.state.indexFieldInfo.default_sort_list.filter(item => item.length > 0 && !!item[1]) || [],
        size,
        begin,
      };
      const params: any = {
        method: 'post',
        url: searchUrl,
        withCredentials: true,
        baseURL: baseUrl,
        responseType: 'blob',
        data: requestData,
        signal: controller.signal,
        headers: {},
      };
      if (store.state.isExternal) {
        params.headers = {
          'X-Bk-Space-Uid': store.state.spaceUid,
        };
      }
      axiosInstance(params)
        .then((resp: any) => {
          if (isUnmounted || currentRequestSeq !== requestSeq || controller.signal.aborted) {
            return;
          }
          if (resp.data && !resp.message) {
            readBlobRespToJson(resp.data).then(({ code, data, result, message, permission }) => {
              if (isUnmounted || currentRequestSeq !== requestSeq || controller.signal.aborted) {
                return;
              }
              if (code === '9900403') {
                store.commit('updateState', {
                  authDialogData: {
                    apply_url: data?.apply_url,
                    apply_data: permission,
                  },
                });
                setExceptionMsg(message || t('无权限'));
                return;
              }
              if (result) {
                begin += size;
                total = data.total.toNumber();
                const list = parseBigNumberList(data.list);
                logList.value.push(...list);
                renderMetaList.value.push(...list.map(() => undefined));
                setExceptionMsg('');
                if (isManualSearch) {
                  // 本地重新检索后不再复用外部缓存 rowKey
                  cachedRowKeys.value = [];
                  choosedIndex.value = -1;
                  handleChooseRow(0, list[0]);
                }
                return;
              }

              // 检索失败：首屏清空并回显错误；分页失败保留已加载数据
              if (begin === 0) {
                logList.value = [];
                renderMetaList.value = [];
                cachedRowKeys.value = [];
                total = 0;
              }
              setExceptionMsg(message || t('检索失败'));
            });
          }
        })
        .catch((error: any) => {
          // 主动取消不视为失败，也不回写异常态
          if (isRequestCanceled(error) || controller.signal.aborted || currentRequestSeq !== requestSeq) {
            return;
          }
          if (isUnmounted) {
            return;
          }
          if (begin === 0) {
            logList.value = [];
            renderMetaList.value = [];
            cachedRowKeys.value = [];
            total = 0;
          }
          setExceptionMsg(error?.message || error?.response?.message || t('检索失败'));
        })
        .finally(() => {
          if (abortController === controller) {
            abortController = null;
          }
          if (!isUnmounted && currentRequestSeq === requestSeq) {
            listLoading.value = false;
          }
        });
    };

    const getValidUISearchValue = (searchValue: any[]) => searchValue.reduce((addtions, item) => {
      if (!item.disabled) {
        addtions.push({
          field: item.field,
          operator: item.operator,
          value:
            item.hidden_values?.length > 0
              ? item.value.filter(value => !item.hidden_values.includes(value))
              : item.value,
        });
      }
      return addtions;
    }, []);

    /**
     * 分词「添加到本次检索」：统一走 resolveAddToSearch（UI + 语句）。
     * 旧 getSqlAdditionMappingOperator 仅映射 is/is not，遇到 contains match phrase 会原样回填。
     */
    const handleMenuClick = (data: {
      option: {
        depth: number;
        fieldName: string;
        fieldType: string;
        operation: string;
        value: string;
        fullPlain?: string;
        isSoleToken?: boolean;
        tokenIndex?: number;
        tokenCount?: number;
      };
      isLink: boolean;
    }) => {
      const searchMode = requestOtherparams.search_mode === 'sql' ? 'sql' : 'ui';
      const fieldName = data.option.fieldName || '*';
      const fieldType = fieldsMap.value[fieldName]?.field_type
        ?? store.state.indexFieldInfo?.fields?.find?.(item => item.field_name === fieldName)?.field_type
        ?? data.option.fieldType;
      const rawValue = String(data.option.value ?? '').replace(/<\/?mark>/gim, '').trim();
      let fullPlain = String(data.option.fullPlain ?? '').replace(/<\/?mark>/gim, '').trim();
      if (!fullPlain || fullPlain === '--') {
        // 本地检索结果行里回填叶子完整 VALUE
        const row = logList.value[choosedIndex.value];
        const fromRow = row ? (row[fieldName]
          ?? fieldName.split('.').reduce((cur: any, key: string) => (cur == null ? undefined : cur[key]), row))
          : undefined;
        fullPlain = fromRow == null || fromRow === ''
          ? ''
          : String(fromRow).replace(/<\/?mark>/gim, '').trim();
      }
      const soleByValue = Boolean(fullPlain && fullPlain === rawValue);
      const isSoleToken = Boolean(
        data.option.isSoleToken
        || (typeof data.option.tokenCount === 'number'
          && data.option.tokenCount === 1
          && (!fullPlain || soleByValue))
        || soleByValue,
      );
      const payload = resolveAddToSearch({
        field: fieldName,
        value: rawValue,
        fieldType,
        fullText: fullPlain || (isSoleToken ? rawValue : undefined),
        operatorHint: data.option.operation,
        isSoleToken,
        tokenIndex: data.option.tokenIndex ?? (isSoleToken ? 0 : undefined),
        tokenCount: data.option.tokenCount ?? (isSoleToken ? 1 : undefined),
        searchMode,
      });

      let isNeedRefresh = false;
      if (searchMode === 'ui') {
        const searchItem = {
          disabled: false,
          field: payload.field,
          field_type: payload.fieldType ?? fieldType,
          operator: payload.operator,
          value: payload.value,
          relation: 'OR',
          showAll: true,
        };
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = '*';
      } else {
        const searchItem = payload.queryString || '';
        if (!searchItem) {
          return;
        }
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = [];
        requestOtherparams.keyword = searchValue;
      }
      if (isNeedRefresh) {
        handleReset();
        requestLogList();
      }
    };

    const handleSearch = (mode: string, isManualSearch = true) => {
      requestOtherparams.search_mode = mode;
      const searchValue = searchBarRef.value.getValue();
      if (mode === 'ui') {
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = '*';
      } else {
        requestOtherparams.addition = [];
        requestOtherparams.keyword = !searchValue ? '*' : searchValue;
      }
      handleReset();

      requestLogList(isManualSearch);
    };

    const handleChooseRow = (index: number, fallbackRow?: Record<string, any>) => {
      if (choosedIndex.value === index) {
        return;
      }

      choosedIndex.value = index;
      const rowKey = cachedRowKeys.value[index];
      if (rowKey) {
        emit('choose-row', { rowKey });
        return;
      }
      if (fallbackRow) {
        emit('choose-row', fallbackRow);
      }
    };

    const handleScrollContent = debounce((e: any) => {
      if (logList.value.length === total) {
        return;
      }

      const { scrollTop, scrollHeight, clientHeight } = e.target;
      if (scrollHeight - scrollTop - clientHeight <= 1) {
        requestLogList(false);
      }
    }, 600);

    const handleReset = () => {
      logList.value = [];
      renderMetaList.value = [];
      cachedRowKeys.value = [];
      begin = 0;
      setExceptionMsg('');
    };

    // 添加样式函数
    const addSegmentLightStyle = () => {
      if (!styleElement) {
        styleElement = document.createElement('style');
        styleElement.id = 'dynamic-segment-light-style';
        styleElement.innerHTML = styleContent;
        document.head.appendChild(styleElement);
      }
    };

    // 移除样式函数
    const removeSegmentLightStyle = () => {
      if (styleElement) {
        document.head.removeChild(styleElement);
        styleElement = null;
      }
    };

    const handleCollpaseToggle = () => {
      isCollapsed.value = !isCollapsed.value;
      emit('toggle-collapse', isCollapsed.value);
    };

    const renderTimeCell = (row: any) => {
      const formatValue = RetrieveHelper.formatDateValue(row[timeField.value], timeFieldType.value);
      // formatDateValue 可能返回 <mark>格式化时间</mark>，需解析后渲染，避免标签被当作纯文本
      const { plainText, markRanges } = parseResultMarkedText(formatValue);
      const displayText = plainText || String(formatValue ?? '');
      return buildHighlightHtml({
        text: displayText,
        resultRanges: markRanges,
      });
    };

    onMounted(() => {
      addSegmentLightStyle();
    });

    onBeforeUnmount(() => {
      isUnmounted = true;
      requestSeq += 1;
      cancelPendingRequest();
      handleScrollContent.cancel();
      if (scrollIntoViewTimer) {
        clearTimeout(scrollIntoViewTimer);
        scrollIntoViewTimer = null;
      }
      logList.value = [];
      renderMetaList.value = [];
      removeSegmentLightStyle();
    });

    expose({
      // init: () => handleSearch(requestOtherparams.search_mode, false),
      init: async () => {
        // 初始化搜索框
        const modeIndex = store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE];
        searchBarRef.value.setLocalMode(modeIndex);
        requestOtherparams.search_mode = modeIndex === 0 ? 'ui' : 'sql';
        const addition = props.retrieveParams.addition || [];
        // 初始化带上常用查询设置
        if (modeIndex === 0) {
          // ui 模式
          const searchValue = searchBarRef.value.getValue();
          if (addition.length > 0 && !searchValue.length) {
            // 常用设置项回填到搜索框
            const addAdditionList = addition.map(item => ({
              disabled: false,
              field: item.field,
              field_type: fieldsMap.value[item.field]?.field_type ?? item.field_type,
              operator: item.operator,
              value: item.value,
              relation: 'OR',
              showAll: true,
            }));
            addAdditionList.forEach((addition) => {
              searchBarRef.value.addValue(addition);
            });
          }
          requestOtherparams.addition = addition;
          requestOtherparams.keyword = '*';
        } else {
          // sql 模式
          const keyword = props.retrieveParams.keyword;
          requestOtherparams.keyword = keyword;
          if (addition.length) {
            requestOtherparams.addition = addition;
          }
        }
        // 设置外部数据：优先读 IndexedDB 渲染行（含检索高亮 overlay），避免初次丢失 mark
        const outerLogResult = store.state.indexSetQueryResult;
        total = outerLogResult.total;
        setExceptionMsg(outerLogResult.is_error ? (outerLogResult.exception_msg || '') : '');
        const rowKeys = outerLogResult.row_keys ?? [];
        cachedRowKeys.value = rowKeys;
        if (rowKeys.length) {
          const cachedEntries = await retrieveRowCacheService.getRenderEntries(rowKeys);
          const renderRows = cachedEntries.map(entry => entry?.row).filter(Boolean);
          if (renderRows.length === rowKeys.length) {
            logList.value = renderRows;
            renderMetaList.value = cachedEntries.map(entry => entry?.renderMeta);
          } else {
            // 渲染行不完整时回退原始行，避免列表空白
            const cachedRows = await retrieveRowCacheService.getRows(rowKeys);
            logList.value = cachedRows.length === rowKeys.length ? cachedRows : (outerLogResult.list ?? []).slice();
            renderMetaList.value = logList.value.map(() => undefined);
          }
        } else {
          cachedRowKeys.value = [];
          logList.value = (outerLogResult.list ?? []).slice();
          renderMetaList.value = logList.value.map(() => undefined);
        }
        begin = logList.value.length;
        if (scrollIntoViewTimer) {
          clearTimeout(scrollIntoViewTimer);
        }
        scrollIntoViewTimer = setTimeout(() => {
          if (isUnmounted) {
            return;
          }
          // 自动定位到选中行
          const isChoosedRow = Array.from(tableRef.value?.querySelectorAll('.is-choosed') ?? [])[0] as HTMLElement;
          if (!isChoosedRow) {
            return;
          }
          const positionInfo = isChoosedRow.getBoundingClientRect();
          if (positionInfo.top > window.innerHeight - 70) {
            isChoosedRow.scrollIntoView();
          }
        });
      },
      reset: handleReset,
    });

    const rowStyle = `font-family: var(--bklog-v3-row-ctx-font);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);`;

    return () => (
      <div class='log-result-main'>
        <div
          class='collapse-main'
          on-click={handleCollpaseToggle}
        >
          <log-icon
            class={{ 'collpase-icon': true, 'is-collapsed': isCollapsed.value }}
            type='angle-left'
            common
          />
        </div>
        <div class='title-main'>
          <div class='title'>{t('原始日志检索结果')}</div>
          <div class='split-line'></div>
          <div class='desc'>{t('可切换原始日志，查看该日志的上下文')}</div>
        </div>
        <div class={['search-main', { 'is-monitor-apm': isMonitorApm }]}>
          <SearchBar
            ref={searchBarRef}
            showClear={false}
            showCopy={false}
            showFavorites={false}
            showQuerySetting={false}
            usageType='local'
            popupAppendToBody
            on-mode-change={handleSearch}
            on-search={handleSearch}
          />
        </div>
        <div
          class='content-main'
          on-scroll={handleScrollContent}
        >
          <table
            ref={tableRef}
            class='log-result-table'
          >
            <thead>
              <tr class='table-header'>
                <th style='width:90px;padding-left:42px'>{t('行号')}</th>
                <th style='width:200px'>{t('时间')}</th>
                <th style='min-width:300px'>{t('原始日志')}</th>
              </tr>
            </thead>
            <tbody v-bkloading={{ isLoading: listLoading.value, opacity: 0.6 }}>
              {logList.value.length > 0
                && logList.value.map((row, index) => (
                  <tr
                    key={`${index}_${row.time}`}
                    class={{ 'is-choosed': choosedIndex.value === index }}
                    on-click={() => handleChooseRow(index)}
                  >
                    <td>
                      <div class='index-column'>
                        <span>{index + 1}</span>
                        <div class='choosed-bgd'>
                          <div class={['check-icon-main', { 'is-monitor-apm-icon':isMonitorApm }]}>
                            {
                              isMonitorApm ? (
                                <span class='bk-icon icon-check-1'></span>
                              ) : (
                                <span class='bk-icon bklog-icon bklog-correct'></span>
                              )
                            }
                          </div>
                        </div>
                      </div>
                    </td>
                    <td style={rowStyle} domProps={{ innerHTML: renderTimeCell(row) }}></td>
                    <td style='padding:4px 0'>
                      <RenderJsonCell>
                        <JsonFormatter
                          class='bklog-column-wrapper'
                          fields={visibleFields.value}
                          jsonValue={row}
                          limitRow={null}
                          renderMeta={renderMetaList.value[index]}
                          onMenu-click={handleMenuClick}
                        ></JsonFormatter>
                      </RenderJsonCell>
                    </td>
                  </tr>
                ))}
              {!listLoading.value && !logList.value.length && exceptionMsg.value && (
                <tr>
                  <td
                    colspan={3}
                    style='padding: 24px 16px; border-bottom: none;'
                  >
                    <bk-exception
                      scene='part'
                      type='500'
                    >
                      <span>{exceptionMsg.value}</span>
                    </bk-exception>
                  </td>
                </tr>
              )}
              {!listLoading.value && !logList.value.length && !exceptionMsg.value && (
                <tr>
                  <td
                    colspan={3}
                    style='padding: 24px 16px; border-bottom: none;'
                  >
                    <bk-exception
                      scene='part'
                      type='empty'
                    >
                      <span>{t('检索结果为空')}</span>
                    </bk-exception>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  },
});
