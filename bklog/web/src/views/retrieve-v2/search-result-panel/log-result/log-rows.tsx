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
import { computed, defineComponent, h, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue';

import { parseTableRowData, setDefaultTableWidth, TABLE_LOG_FIELDS_SORT_REGULAR, xssFilter } from '@/common/util';
import JsonFormatter from '@/global/json-formatter.vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import { UseSegmentProp } from '@/hooks/use-segment-pop';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';

import PopInstanceUtil from '../../../../global/pop-instance-util';
import { BK_LOG_STORAGE } from '../../../../store/store.type';
import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
import ExpandView from '../../components/result-cell-element/expand-view.vue';
import OperatorTools from '../../components/result-cell-element/operator-tools.vue';
import ScrollTop from '../../components/scroll-top/index';
import useTextAction from '../../hooks/use-text-action';
import LogCell from './log-cell';
import LogResultException from './log-result-exception';
import {
  LOG_SOURCE_F,
  ROW_EXPAND,
  ROW_F_ORIGIN_CTX,
  ROW_F_ORIGIN_OPT,
  ROW_F_ORIGIN_TIME,
  ROW_INDEX,
  ROW_KEY,
  ROW_SOURCE,
  SECTION_SEARCH_INPUT,
} from './log-row-attributes';
import RowRender from './row-render';
import ScrollXBar from '../../components/scroll-x-bar';
import useLazyRender from './use-lazy-render';
import useHeaderRender from './use-render-header';

import './log-rows.scss';

type RowConfig = {
  expand?: boolean;
  isIntersect?: boolean;
  minHeight?: number;
  stickyTop?: number;
  rowMinHeight?: number;
};

export default defineComponent({
  props: {
    contentType: {
      type: String,
      default: 'table',
    },
    handleClickTools: Function,
  },
  setup(props, { emit }) {
    const store = useStore();
    const { $t } = useLocale();

    const refRootElement: Ref<HTMLElement> = ref();
    const refTableHead: Ref<HTMLElement> = ref();
    const refLoadMoreElement: Ref<HTMLElement> = ref();
    const refResultRowBox: Ref<HTMLElement> = ref();
    const refSegmentContent: Ref<HTMLElement> = ref();
    const { handleOperation } = useTextAction(emit, 'origin');

    let savedSelection: Range = null;

    const popInstanceUtil = new PopInstanceUtil({
      refContent: () => refSegmentContent.value,
      tippyOptions: {
        hideOnClick: true,
        theme: 'segment-light',
        placement: 'bottom',
        appendTo: document.body,
      },
    });

    const useSegmentPop = new UseSegmentProp({
      delineate: true,
      stopPropagation: true,
      onclick: (...args) => {
        const type = args[1];
        if (type === 'add-to-ai') {
          props.handleClickTools(type, savedSelection?.toString() ?? '');
        } else {
          handleOperation(type, { value: savedSelection?.toString() ?? '', operation: type });
        }
        popInstanceUtil.hide();

        if (savedSelection) {
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(savedSelection);
        }
      },
    });

    const pageIndex = ref(1);
    // 前端本地分页
    const pageSize = ref(50);
    const isRending = ref(false);

    const tableRowConfig = new WeakMap();
    const isPageLoading = ref(RetrieveHelper.isSearching);
    // 前端本地分页loadmore触发器
    // renderList 没有使用响应式，这里需要手动触发更新，所以这里使用一个计数器来触发更新
    const localUpdateCounter = ref(0);
    const hasMoreList = ref(true);
    let renderList = Object.freeze([]);
    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const tableShowRowIndex = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX]);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading || indexFieldInfo.value.is_loading);
    const kvShowFieldsList = computed(() => indexFieldInfo.value?.fields.map(f => f.field_name));
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const tableDataSize = computed(() => indexSetQueryResult.value?.list?.length ?? 0);
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const tableList = computed<any[]>(() => Object.freeze(indexSetQueryResult.value?.list ?? []));
    const gradeOption = computed(() => store.state.indexFieldInfo.custom_config?.grade_options ?? { disabled: false });
    const indexSetType = computed(() => store.state.indexItem.isUnionIndex);

    // 检索第一页数据时，loading状态
    const isFirstPageLoading = computed(() => isLoading.value && !isRequesting.value);

    const exceptionMsg = computed(() => {
      if (/^cancel$/gi.test(indexSetQueryResult.value?.exception_msg)) {
        return $t('检索结果为空');
      }

      return indexSetQueryResult.value?.exception_msg || $t('检索结果为空');
    });
    const isShowSourceField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_SOURCE_FIELD]);
    const fullColumns = ref([]);
    const showCtxType = ref(props.contentType);

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.SEARCHING_CHANGE, isSearching => {
      isPageLoading.value = isSearching;
    });

    addEvent(
      [RetrieveEvent.SEARCH_VALUE_CHANGE, RetrieveEvent.SEARCH_TIME_CHANGE, RetrieveEvent.TREND_GRAPH_SEARCH],
      () => {
        hasMoreList.value = true;
        pageIndex.value = 1;
      },
    );
    addEvent(
      RetrieveEvent.AUTO_REFRESH,
      () => {
        hasMoreList.value = true;
        pageIndex.value = 1;
        store.dispatch("requestIndexSetQuery");
      },
    );
    const setRenderList = (length?: number) => {
      const arr: Record<string, any>[] = [];
      const endIndex = length ?? tableDataSize.value;
      const lastIndex = endIndex <= tableList.value.length ? endIndex : tableList.value.length;
      for (let i = 0; i < lastIndex; i++) {
        arr.push({
          item: tableList.value[i],
          [ROW_KEY]: `${tableList.value[i].dtEventTimeStamp}_${i}`,
        });
      }

      renderList = arr;
    };

    const searchContainerHeight = ref(52);
    const resultContainerId = ref(RetrieveHelper.logRowsContainerId);
    const resultContainerIdSelector = `#${resultContainerId.value}`;

    const operatorToolsWidth = computed(() => {
      const w = indexSetOperatorConfig.value?.bcsWebConsole?.is_active ? 84 : 58;
      return store.getters.isAiAssistantActive ? w + 26 : w;
    });

    const originalColumns = computed(() => {
      return [
        {
          field: ROW_F_ORIGIN_TIME,
          key: ROW_F_ORIGIN_TIME,
          title: ROW_F_ORIGIN_TIME,
          align: 'top',
          resize: false,
          minWidth: timeFieldType.value === 'date_nanos' ? 250 : 200,
          renderBodyCell: ({ row }) => {
            return h(
              'span',
              {
                class: 'time-field',
                domProps: {
                  innerHTML: xssFilter(RetrieveHelper.formatDateValue(row[timeField.value], timeFieldType.value)),
                },
              },
              [],
            );
          },
        },
        {
          field: ROW_F_ORIGIN_CTX,
          key: ROW_F_ORIGIN_CTX,
          title: ROW_F_ORIGIN_CTX,
          align: 'top',
          minWidth: '100%',
          width: '100%',
          resize: false,
          renderBodyCell: ({ row }) => {
            return (
              <JsonFormatter
                class='bklog-column-wrapper'
                fields={visibleFields.value}
                jsonValue={row}
                limitRow={null}
                onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink)}
              />
            );
          },
        },
      ];
    });

    const formatColumn = field => {
      return {
        field: field.field_name,
        key: field.field_name,
        title: field.field_name,
        width: field.width,
        minWidth: field.minWidth,
        align: 'top',
        resize: true,
        renderBodyCell: ({ row }) => {
          return (
            <JsonFormatter
              class='bklog-column-wrapper'
              fields={field}
              jsonValue={parseTableRowData(row, field.field_name, field.field_type, false) as any}
              onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink, { row, field })}
            />
          );
        },
        renderHeaderCell: () => {
          const sortable = field.es_doc_values && field.tag !== 'union-source' && field.field_type !== 'flattened';
          return renderHead(field, order => {
            if (sortable) {
              const sortList = order ? [[field.field_name, order]] : [];
              const updatedSortList = store.state.indexFieldInfo.sort_list.map(item => {
                if (sortList.length > 0 && item[0] === field.field_name) {
                  return sortList[0];
                }
                if (sortList.length === 0 && item[0] === field.field_name) {
                  return [field.field_name, 'desc'];
                }
                return item;
              });
              const temporarySortList = syncSpecifiedFieldSort(field.field_name, sortList);
              store.commit('updateState', { localSort: true });
              store.commit('updateIndexFieldInfo', { sort_list: updatedSortList });
              store.commit('updateIndexItemParams', { sort_list: temporarySortList });
              store.dispatch('requestIndexSetQuery');
            }
          });
        },
      };
    };

    const setColWidth = col => {
      col.minWidth = col.width - 4;
      col.width = '100%';
    };

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const getFieldColumns = () => {
      if (showCtxType.value === 'table') {
        const columnList: Record<string, any>[] = [];
        const columns = visibleFields.value.length > 0 ? visibleFields.value : fullColumns.value;
        let maxColWidth = operatorToolsWidth.value + 40;
        let logField: Record<string, any> | null = null;

        for (const col of columns) {
          const formatValue = formatColumn(col);
          if (col.field_name === 'log') {
            logField = formatValue;
          }

          columnList.push(formatValue);
          maxColWidth += formatValue.width;
        }

        if (!logField && columnList.length > 0) {
          logField = columnList.at(-1);
        }

        if (logField && offsetWidth.value > maxColWidth) {
          setColWidth(logField);
        }

        return columnList;
      }

      return originalColumns.value;
    };

    const hanldeAfterExpandClick = (target: HTMLElement) => {
      const expandTarget = target
        .closest('.bklog-row-container')
        ?.querySelector('.bklog-row-observe .expand-view-wrapper');
      if (expandTarget) {
        RetrieveHelper.highlightElement(expandTarget);
      }
    };

    const leftColumns = computed(() => [
      {
        field: '',
        key: ROW_EXPAND,
        // 设置需要显示展开图标的列
        type: 'expand',
        title: '',
        width: 36,
        align: 'center',
        resize: false,
        fixed: 'left',
        renderBodyCell: ({ row }) => {
          const config: RowConfig = tableRowConfig.get(row).value;
          return (
            <span class={['bklog-expand-icon', { 'is-expaned': config.expand }]}>
              <i
                style={{ color: '#4D4F56', fontSize: '9px' }}
                class='bk-icon icon-play-shape'
              />
            </span>
          );
        },
      },
      {
        field: '',
        key: ROW_INDEX,
        title: tableShowRowIndex.value ? '#' : '',
        width: tableShowRowIndex.value ? 50 : 0,
        fixed: 'left',
        align: 'center',
        resize: false,
        class: tableShowRowIndex.value ? 'is-show' : 'is-hidden',
        renderBodyCell: ({ row }) => {
          return tableRowConfig.get(row).value[ROW_INDEX] + 1;
        },
      },
      {
        field: '',
        key: ROW_SOURCE,
        title: '日志来源',
        width: 230,
        align: 'left',
        resize: false,
        fixed: 'left',
        disabled: !(isShowSourceField.value && indexSetType.value),
        renderBodyCell: ({ row }) => {
          const indeSetName =
            unionIndexItemList.value.find(item => item.index_set_id === String(row.__index_set_id__))?.index_set_name ??
            '';
          const hanldeSoureClick = event => {
            event.stopPropagation();
            event.preventDefault();
            event.stopImmediatePropagation();
          };

          return <span onClick={hanldeSoureClick}>{indeSetName}</span>;
        },
      },
    ]);

    const handleRowAIClcik = (e: MouseEvent, row: any) => {
      const rowIndex = tableRowConfig.get(row).value[ROW_INDEX] + 1;
      const targetRow = (e.target as HTMLElement).closest('.bklog-row-container');
      const oldRow = targetRow?.parentElement.querySelector('.bklog-row-container.ai-active');

      oldRow?.classList.remove('ai-active');
      targetRow?.classList.add('ai-active');

      props.handleClickTools('ai', row, indexSetOperatorConfig.value, rowIndex);
    };

    const rightColumns = computed(() => {
      if (window?.__IS_MONITOR_TRACE__) {
        return [];
      }
      return [
        {
          field: ROW_F_ORIGIN_OPT,
          key: ROW_F_ORIGIN_OPT,
          title: $t('操作'),
          width: operatorToolsWidth.value,
          fixed: 'right',
          resize: false,
          renderBodyCell: ({ row }) => {
            return (
              // @ts-expect-error
              <OperatorTools
                handle-click={(type, event) => {
                  if (type === 'ai') {
                    handleRowAIClcik(event, row);
                    return;
                  }
                  props.handleClickTools(
                    type,
                    row,
                    indexSetOperatorConfig.value,
                    tableRowConfig.get(row).value[ROW_INDEX] + 1,
                  );
                }}
                index={row[ROW_INDEX]}
                operator-config={indexSetOperatorConfig.value}
                row-data={row}
              />
            );
          },
        },
      ];
    });

    // 替换原有的handleIconClick
    const handleIconClick = (type, content, field, row, isLink, depth, isNestedField) => {
      handleOperation(type, { content, field, row, isLink, depth, isNestedField, operation: type });
    };

    // 替换原有的handleMenuClick
    const handleMenuClick = (option, isLink, fieldOption?: { row: any; field: any }) => {
      console.log('handleMenuClick = ', option);
      const timeTypes = ['date', 'date_nanos'];

      handleOperation(option.operation, {
        ...option,
        value: timeTypes.includes(fieldOption?.field.field_type ?? null)
          ? `${fieldOption?.row[fieldOption?.field.field_name]}`.replace(/<\/?mark>/gim, '')
          : option.value,
        fieldName: option.fieldName,
        operation: option.operation,
        isLink,
        depth: option.depth,
        displayFieldNames: option.displayFieldNames,
      });
    };

    const { renderHead } = useHeaderRender();
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const setFullColumns = () => {
      /** 清空所有字段后所展示的默认字段  顺序: 时间字段，log字段，索引字段 */
      const dataFields: Record<string, any>[] = [];
      const indexSetFields: Record<string, any>[] = [];
      const logFields: Record<string, any>[] = [];
      for (const item of indexFieldInfo.value.fields) {
        if (item.field_type === 'date') {
          dataFields.push(item);
        } else if (item.field_name === 'log' || item.field_alias === 'original_text') {
          logFields.push(item);
        } else if (!(item.field_type === '__virtual__' || item.is_built_in)) {
          indexSetFields.push(item);
        }
      }
      const sortIndexSetFieldsList = indexSetFields.sort((a, b) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      const sortFieldsList = [...dataFields, ...logFields, ...sortIndexSetFieldsList];
      if (isUnionSearch.value && indexSetOperatorConfig.value?.isShowSourceField) {
        sortFieldsList.unshift(LOG_SOURCE_F());
      }

      setDefaultTableWidth(sortFieldsList, tableList.value);
      fullColumns.value = sortFieldsList;
    };

    const getRowConfigWithCache = () => {
      return [['expand', false]].reduce((cfg, item: [keyof RowConfig, any]) => {
        cfg[item[0]] = item[1];
        return cfg;
      }, {});
    };

    const updateTableRowConfig = (nextIdx = 0) => {
      if (nextIdx >= 0) {
        for (let index = nextIdx; index < tableDataSize.value; index++) {
          const nextRow = tableList.value[index];
          if (!tableRowConfig.has(nextRow)) {
            const rowKey = `${ROW_KEY}_${index}`;
            tableRowConfig.set(
              nextRow,
              ref({
                [ROW_KEY]: rowKey,
                [ROW_INDEX]: index,
                ...getRowConfigWithCache(),
              }),
            );
          }
        }
      }

      if (nextIdx === -1) {
        for (let index = 0; index < tableDataSize.value; index++) {
          const nextRow = tableList.value[index];
          tableRowConfig.delete(nextRow);
        }
      }
    };

    const isRequesting = ref(false);
    let requestingTimer: any = null;

    const debounceSetLoading = (delay = 120) => {
      requestingTimer && clearTimeout(requestingTimer);
      requestingTimer = setTimeout(() => {
        isRequesting.value = false;
      }, delay);
    };

    const expandOption = {
      render: ({ row }) => {
        const config = tableRowConfig.get(row);
        return (
          <ExpandView
            data={row}
            kv-show-fields-list={kvShowFieldsList.value}
            list-data={row}
            row-index={config.value[ROW_INDEX]}
            onValue-click={(type, content, isLink, field, depth, isNestedField) =>
              handleIconClick(type, content, field, row, isLink, depth, isNestedField)
            }
          />
        );
      },
    };

    const resetRowListState = (oldValSize?) => {
      setRenderList(null);
      debounceSetLoading();
      updateTableRowConfig(oldValSize ?? 0);

      if (tableDataSize.value <= 50) {
        nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
      }
    };

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const syncSpecifiedFieldSort = (field_name, updatedSortList) => {
      const requiredFields = ['gseIndex', 'iterationIndex', 'dtEventTimeStamp'];
      if (!(requiredFields.includes(field_name) && updatedSortList.length)) {
        return updatedSortList;
      }
      const fields = store.state.indexFieldInfo.fields.map(item => item.field_name);
      const currentSort = updatedSortList.find(([key]) => key === field_name)[1];

      for (const field of requiredFields) {
        if (field === field_name) {
          continue;
        }
        if (fields.includes(field)) {
          const index = updatedSortList.findIndex(([key]) => key === field);
          const sortItem = [field, currentSort];

          if (index !== -1) {
            updatedSortList[index] = sortItem;
          } else {
            updatedSortList.push(sortItem);
          }
        }
      }
      return updatedSortList;
    };
    watch(
      () => [tableShowRowIndex.value],
      () => {
        computeRect();
      },
    );

    const handleResultBoxResize = (resetScroll = true) => {
      if (!RetrieveHelper.jsonFormatter.isExpandNodeClick) {
        if (resetScroll) {
          scrollXOffsetLeft = 0;
          refScrollXBar.value?.scrollLeft(0);
        }
      }

      computeRect(refResultRowBox.value);
    };

    watch(
      () => [props.contentType],
      () => {
        showCtxType.value = props.contentType;
        pageIndex.value = 1;
        setRenderList(50);
        handleResultBoxResize();
      },
    );

    watch(
      () => [visibleFields.value.length],
      () => {
        if (!visibleFields.value.length) {
          setFullColumns();
        }

        handleResultBoxResize();
      },
    );

    watch(
      () => [tableDataSize.value],
      (_, oldVal) => {
        resetRowListState(oldVal?.[0]);
      },
      {
        immediate: true,
      },
    );

    useResizeObserve(
      () => refResultRowBox.value,
      () => {
        handleResultBoxResize();
        RetrieveHelper.fire(RetrieveEvent.RESULT_ROW_BOX_RESIZE);
      },
      60,
    );

    addEvent(
      [
        RetrieveEvent.FAVORITE_WIDTH_CHANGE,
        RetrieveEvent.LEFT_FIELD_SETTING_WIDTH_CHANGE,
        RetrieveEvent.FAVORITE_SHOWN_CHANGE,
        RetrieveEvent.LEFT_FIELD_SETTING_SHOWN_CHANGE,
      ],
      handleResultBoxResize,
    );

    const handleColumnWidthChange = (w, col) => {
      const width = w > 40 ? w : 40;
      const longFiels = visibleFields.value.filter(
        item => item.width >= 800 || item.field_name === 'log' || item.field_type === 'text',
      );
      const logField = longFiels.find(item => item.field_name === 'log');
      const targetField = longFiels.length
        ? longFiels
        : visibleFields.value.filter(item => item.field_name !== col.field);

      if (width < col.width && targetField.length) {
        if (logField) {
          logField.width += width;
        } else {
          const avgWidth = (col.width - width) / targetField.length;
          for (const field of targetField) {
            field.width += avgWidth;
          }
        }
      }

      const sourceObj = visibleFields.value.reduce((acc, curField) => {
        acc[curField.field_name] = curField.width;
        return acc;
      }, {});
      const { fieldsWidth } = userSettingConfig.value;
      const newFieldsWidthObj = Object.assign(fieldsWidth, sourceObj, {
        [col.field]: Math.ceil(width),
      });

      const field = visibleFields.value.find(item => item.field_name === col.field);
      field.width = width;

      store.dispatch('userFieldConfigChange', {
        fieldsWidth: newFieldsWidthObj,
      });

      store.commit('updateVisibleFields', visibleFields.value);
    };

    const loadMoreTableData = () => {
      // tableDataSize.value === 0 用于判定是否是第一次渲染导致触发的请求
      // visibleFields.value 在字段重置时会清空，所以需要判断
      if (isRequesting.value || tableDataSize.value === 0 || visibleFields.value.length === 0) {
        return;
      }

      if (pageIndex.value * pageSize.value < tableDataSize.value) {
        hasMoreList.value = true;
        isRequesting.value = true;
        pageIndex.value++;
        const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
        setRenderList(maxLength);
        debounceSetLoading(0);
        nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
        localUpdateCounter.value++;
        return;
      }

      if (hasMoreList.value) {
        isRequesting.value = true;
        return store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then(resp => {
            pageIndex.value++;
            handleResultBoxResize(false);

            if (resp?.length !== pageSize.value) {
              hasMoreList.value = false;
            }
          })
          .finally(() => {
            debounceSetLoading(0);
            nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
          });
      }

      return Promise.resolve(false);
    };

    useResizeObserve(SECTION_SEARCH_INPUT, entry => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    let scrollXOffsetLeft = 0;
    const refScrollXBar = ref();

    const afterScrollTop = () => {
      pageIndex.value = 1;
      const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
      renderList = renderList.slice(0, maxLength);
      localUpdateCounter.value++;
    };

    // 监听滚动条滚动位置
    // 判定是否需要拉取更多数据
    const { offsetWidth, scrollWidth, computeRect } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
      refLoadMoreElement,
    });

    const setRowboxTransform = () => {
      if (refResultRowBox.value && refRootElement.value) {
        refResultRowBox.value.scrollLeft = scrollXOffsetLeft;
        if (refTableHead.value) {
          refTableHead.value.style.setProperty('width', `${scrollWidth.value}px`);
          refTableHead.value.style.transform = `translateX(-${scrollXOffsetLeft}px)`;
          const fixedRight = refTableHead.value?.querySelector(
            '.bklog-list-row .bklog-row-cell.header-cell.right',
          ) as HTMLElement;
          if (fixedRight) {
            fixedRight.style.transform = `translateX(${scrollXOffsetLeft}px)`;
          }
        }
      }
    };

    const hasScrollX = computed(() => {
      return showCtxType.value === 'table' && scrollWidth.value > offsetWidth.value;
    });

    let isAnimating = false;

    useWheel({
      target: refRootElement,
      callback: (event: WheelEvent) => {
        const maxOffset = scrollWidth.value - offsetWidth.value;

        // 检查是否按住 shift 键
        if (event.shiftKey) {
          // 当按住 shift 键时，让 refScrollXBar 执行系统默认的横向滚动能力
          if (hasScrollX.value && refScrollXBar.value) {
            event.stopPropagation();
            event.stopImmediatePropagation();
            event.preventDefault();

            // 使用系统默认的滚动行为，通过 refScrollXBar 执行横向滚动
            const currentScrollLeft = refScrollXBar.value.getScrollLeft?.() || 0;
            const scrollStep = event.deltaY || event.deltaX;
            const newScrollLeft = Math.max(0, Math.min(maxOffset, currentScrollLeft + scrollStep));

            refScrollXBar.value.scrollLeft(newScrollLeft);
            scrollXOffsetLeft = newScrollLeft;
            setRowboxTransform();
          }
          return;
        }

        if (event.deltaX !== 0 && hasScrollX.value) {
          event.stopPropagation();
          event.stopImmediatePropagation();
          event.preventDefault();
          if (!isAnimating) {
            isAnimating = true;
            requestAnimationFrame(() => {
              isAnimating = false;
              const nextOffset = scrollXOffsetLeft + event.deltaX;
              if (nextOffset <= maxOffset && nextOffset >= 0) {
                scrollXOffsetLeft += event.deltaX;
                setRowboxTransform();
                refScrollXBar.value?.scrollLeft(nextOffset);
              }
            });
          }
        }
      },
    });

    const operatorFixRightWidth = computed(() => {
      const operatorWidth = operatorToolsWidth.value;
      const diff = scrollWidth.value - scrollXOffsetLeft - offsetWidth.value;

      return operatorWidth + (diff > 0 ? diff : 0);
    });

    watch(
      () => [operatorFixRightWidth.value, offsetWidth.value, scrollWidth.value],
      () => {
        setRowboxTransform();
      },
      { immediate: true },
    );

    const showHeader = computed(() => {
      return showCtxType.value === 'table' && tableList.value.length > 0;
    });

    const renderHeadVNode = () => {
      if (isFirstPageLoading.value) {
        return null;
      }

      const columnLength = allColumns.value.length;
      let hasFullWidth = false;

      return (
        <div
          ref={refTableHead}
          class={['bklog-row-container row-header']}
        >
          <div class='bklog-list-row'>
            {allColumns.value.map((column, index) => {
              const cellStyle = getColumnWidth(
                column,
                !hasFullWidth && (column.width === '100%' || index === columnLength - 2),
              );
              hasFullWidth = hasFullWidth || column.width === '100%' || index === columnLength - 2;

              return (
                <LogCell
                  key={column.key}
                  width={column.width}
                  class={[column.class ?? '', 'bklog-row-cell header-cell', column.fixed]}
                  customStyle={cellStyle}
                  minWidth={column.minWidth > 0 ? column.minWidth : column.width}
                  resize={column.resize}
                  onResize-width={w => handleColumnWidthChange(w, column)}
                >
                  {column.renderHeaderCell?.({ column }, h) ?? column.title}
                </LogCell>
              );
            })}
          </div>
        </div>
      );
    };

    const renderScrollTop = () => {
      return <ScrollTop on-scroll-top={afterScrollTop} />;
    };

    const getColumnWidth = (column, fullWidth = false) => {
      if (fullWidth) {
        return {
          width: '100%',
          minWidth: `${Math.max(column.minWidth, column.width)}px`,
        };
      }

      if (typeof column.width === 'number') {
        return {
          width: `${column.width}px`,
          minWidth: `${column.width}px`,
          maxWidth: `${column.width}px`,
        };
      }
      return {
        width: column.width,
        minWidth: `${column.minWidth ?? 80}px`,
      };
    };

    const allColumns = computed(() =>
      [...leftColumns.value, ...getFieldColumns(), ...rightColumns.value].filter(item => !item.disabled),
    );

    const renderRowCells = (row, rowIndex) => {
      const { expand } = tableRowConfig.get(row).value;
      const columnLength = allColumns.value.length;
      let hasFullWidth = false;

      return [
        <div
          key={`${rowIndex}-row`}
          class='bklog-list-row'
          data-row-index={rowIndex}
          data-row-click
        >
          {allColumns.value.map((column, index) => {
            const cellStyle = getColumnWidth(
              column,
              !hasFullWidth && (column.width === '100%' || index === columnLength - 2),
            );
            hasFullWidth = hasFullWidth || column.width === '100%' || index === columnLength - 2;

            return (
              <div
                key={`${rowIndex}-${column.key}`}
                style={cellStyle}
                class={[column.class ?? '', 'bklog-row-cell', column.fixed]}
              >
                {column.renderBodyCell?.({ row, column, rowIndex }, h) ?? column.title}
              </div>
            );
          })}
        </div>,
        expand ? expandOption.render({ row }) : '',
      ];
    };

    const handleRowMousedown = (e: MouseEvent) => {
      if (RetrieveHelper.isClickOnSelection(e, 2)) {
        RetrieveHelper.stopEventPropagation(e);
        return;
      }

      RetrieveHelper.setMousedownEvent(e);
      savedSelection = null;
    };

    const handleRowMouseup = (e: MouseEvent, item: any) => {
      if (RetrieveHelper.isClickOnSelection(e, 2) || RetrieveHelper.isMouseSelectionUpEvent(e)) {
        RetrieveHelper.stopEventPropagation(e);
        RetrieveHelper.setMousedownEvent(null);
        const selection = window.getSelection();
        if (selection.rangeCount > 0) {
          savedSelection = selection.getRangeAt(0);
        }
        popInstanceUtil.show(e.target);
        return;
      }

      const target = e.target as HTMLElement;
      const expandCell = target.closest('.bklog-row-observe')?.querySelector('.expand-view-wrapper');

      if (target.classList.contains('valid-text') || expandCell?.contains(target)) {
        return;
      }

      const config: RowConfig = tableRowConfig.get(item).value;
      config.expand = !config.expand;
      nextTick(() => {
        if (config.expand) {
          hanldeAfterExpandClick(target);
        }
      });
    };

    const renderRowVNode = () => {
      if (isFirstPageLoading.value) {
        return null;
      }

      return renderList.map((row, rowIndex) => {
        const logLevel = gradeOption.value.disabled ? '' : RetrieveHelper.getLogLevel(row.item, gradeOption.value);

        return [
          <RowRender
            key={row[ROW_KEY]}
            class={['bklog-row-container', logLevel ?? 'normal']}
            row-index={rowIndex}
            on-row-mousedown={handleRowMousedown}
            on-row-mouseup={e => handleRowMouseup(e, row.item)}
          >
            {renderRowCells(row.item, rowIndex)}
          </RowRender>,
        ];
      });
    };

    const handleScrollXChanged = (event: MouseEvent) => {
      scrollXOffsetLeft = (event.target as HTMLElement)?.scrollLeft || 0;
      setRowboxTransform();
    };

    const renderScrollXBar = () => {
      return (
        <ScrollXBar
          ref={refScrollXBar}
          innerWidth={scrollWidth.value}
          outerWidth={offsetWidth.value}
          onScroll-change={handleScrollXChanged}
        />
      );
    };

    const loadingText = computed(() => {
      if (isLoading.value && !isRequesting.value) {
        return '';
      }

      if (hasMoreList.value && (isLoading.value || isRending.value)) {
        return 'Loading ...';
      }

      if (!(isRequesting.value || hasMoreList.value) || tableDataSize.value < pageSize.value) {
        return ` - 已加载所有数据: 共计 ${tableDataSize.value} 条 - `;
      }

      return '';
    });

    const updateLoader = () => {
      if (refLoadMoreElement.value) {
        const targetElement = refLoadMoreElement.value.firstElementChild as HTMLElement;
        targetElement.style.width = `${offsetWidth.value}px`;
        targetElement.textContent = loadingText.value;
      }
    };

    const updateRootElementClass = () => {
      if (refRootElement.value) {
        refRootElement.value.classList.toggle('has-scroll-x', hasScrollX.value);
        refRootElement.value.classList.toggle('show-header', showHeader.value);
      }
    };

    watch(
      () => [offsetWidth.value, loadingText.value],
      () => {
        updateLoader();
      },
    );

    watch(
      () => [hasScrollX.value, showHeader.value],
      () => {
        updateRootElementClass();
      },
    );

    const renderLoader = () => {
      return (
        <div
          ref={refLoadMoreElement}
          class='bklog-requsting-loading'
        >
          <div style='min-width: 100%' />
        </div>
      );
    };

    const renderFixRightShadow = () => {
      if (window?.__IS_MONITOR_TRACE__) {
        return null;
      }
      if (tableDataSize.value > 0 && showCtxType.value === 'table') {
        return <div class='fixed-right-shadown' />;
      }

      return null;
    };

    const isTableLoading = computed(() => {
      return (
        tableDataSize.value === 0 && (isRequesting.value || isRending.value || isPageLoading.value || isLoading.value)
      );
    });

    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const exceptionType = computed(() => {
      if (tableDataSize.value === 0 || indexFieldInfo.value.is_loading) {
        if (isRequesting.value || isLoading.value || isPageLoading.value) {
          return 'loading';
        }

        if ($t('检索结果为空') === exceptionMsg.value) {
          return 'search-empty';
        }

        if (/^index-set-not-found/.test(exceptionMsg.value)) {
          return 'index-set-not-found';
        }

        if (/^index-set-field-not-found/.test(exceptionMsg.value)) {
          return 'index-set-field-not-found';
        }

        return exceptionMsg.value.length ? 'error' : 'empty';
      }

      return 'hidden';
    });

    const getExceptionRender = () => {
      return (
        <LogResultException
          message={exceptionMsg.value}
          type={exceptionType.value}
        />
      );
    };

    const renderDelineatePopContent = () => {
      return <div style='display: none;'>{useSegmentPop.createSegmentContent(refSegmentContent)}</div>;
    };

    onBeforeUnmount(() => {
      popInstanceUtil.uninstallInstance();
      resetRowListState(-1);
    });

    return {
      refRootElement,
      refResultRowBox,
      isTableLoading,
      renderDelineatePopContent,
      renderRowVNode,
      renderFixRightShadow,
      renderScrollTop,
      renderScrollXBar,
      renderLoader,
      renderHeadVNode,
      getExceptionRender,
      tableDataSize,
      resultContainerId,
      hasScrollX,
      showHeader,
      isRequesting,
      exceptionMsg,
      localUpdateCounter,
    };
  },
  render() {
    return (
      <div
        ref='refRootElement'
        class='bklog-result-container'
      >
        {this.renderHeadVNode()}
        <div
          id={this.resultContainerId}
          ref='refResultRowBox'
          class='bklog-row-box'
          data-local-update-counter={this.localUpdateCounter}
        >
          {this.renderRowVNode()}
        </div>
        {this.getExceptionRender()}
        {this.renderFixRightShadow()}
        {this.renderScrollXBar()}
        {this.renderLoader()}
        {this.renderScrollTop()}
        {this.renderDelineatePopContent()}
        <div class='resize-guide-line' />
      </div>
    );
  },
});
