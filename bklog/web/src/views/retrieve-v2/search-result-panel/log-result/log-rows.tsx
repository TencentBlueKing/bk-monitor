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
import { computed, defineComponent, ref, watch, h, Ref, provide, onBeforeUnmount, nextTick } from 'vue';

import {
  parseTableRowData,
  formatDateNanos,
  formatDate,
  copyMessage,
  setDefaultTableWidth,
  TABLE_LOG_FIELDS_SORT_REGULAR,
} from '@/common/util';
import JsonFormatter from '@/global/json-formatter.vue';
import useFieldNameHook from '@/hooks/use-field-name';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { bkMessage } from 'bk-magic-vue';
import { useRoute, useRouter } from 'vue-router/composables';

import PopInstanceUtil from '../../../../global/pop-instance-util';
import ExpandView from '../../components/result-cell-element/expand-view.vue';
import OperatorTools from '../../components/result-cell-element/operator-tools.vue';
import { getConditionRouterParams } from '../panel-util';
import LogCell from './log-cell';
import {
  LOG_SOURCE_F,
  ROW_EXPAND,
  ROW_F_JSON,
  ROW_F_ORIGIN_CTX,
  ROW_F_ORIGIN_OPT,
  ROW_F_ORIGIN_TIME,
  ROW_INDEX,
  ROW_KEY,
  SECTION_SEARCH_INPUT,
} from './log-row-attributes';
import RowRender from './row-render';
import ScrollTop from './scroll-top';
import ScrollXBar from './scroll-x-bar';
import TableColumn from './table-column.vue';
import useLazyRender from './use-lazy-render';
import useHeaderRender from './use-render-header';
import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';

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

    const popInstanceUtil = new PopInstanceUtil({
      refContent: ref('智能分析'),
      tippyOptions: {
        appendTo: document.body,
        placement: 'top',
        theme: 'dark',
      },
    });

    const pageIndex = ref(1);
    // 前端本地分页
    const pageSize = ref(50);
    const isRending = ref(false);

    const tableRowConfig = new WeakMap();
    const hasMoreList = ref(true);

    let renderList = Object.freeze([]);
    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const formatJson = computed(() => store.state.storage.tableJsonFormat);
    const tableShowRowIndex = computed(() => store.state.storage.tableShowRowIndex);
    const tableLineIsWrap = computed(() => store.state.storage.tableLineIsWrap);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading || indexFieldInfo.value.is_loading);
    const kvShowFieldsList = computed(() => indexFieldInfo.value?.fields.map(f => f.field_name));
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const tableDataSize = computed(() => indexSetQueryResult.value?.list?.length ?? 0);
    const fieldRequestCounter = computed(() => indexFieldInfo.value.request_counter);
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const tableList = computed<Array<any>>(() => Object.freeze(indexSetQueryResult.value?.list ?? []));
    const gradeOption = computed(() => store.state.indexFieldInfo.custom_config?.grade_options ?? { disabled: false });

    const exceptionMsg = computed(() => {
      if (/^cancel$/gi.test(indexSetQueryResult.value?.exception_msg)) {
        return $t('检索结果为空');
      }

      return indexSetQueryResult.value?.exception_msg || $t('检索结果为空');
    });

    const apmRelation = computed(() => store.state.indexSetFieldConfig.apm_relation);

    const fullColumns = ref([]);
    const showCtxType = ref(props.contentType);

    const router = useRouter();
    const route = useRoute();

    const setRenderList = (length?) => {
      const targetLength = length ?? tableDataSize.value;
      const inteval = 50;

      const appendChildNodes = () => {
        const appendLength = targetLength - renderList.length;
        const stepLength = appendLength > inteval ? inteval : appendLength;
        const startIndex = renderList.length;

        if (appendLength > 0) {
          const arr = [];
          const endIndex = startIndex + stepLength;
          const lastIndex = endIndex <= tableList.value.length ? endIndex : tableList.value.length;
          for (let i = 0; i < lastIndex; i++) {
            arr.push({
              item: tableList.value[i],
              [ROW_KEY]: `${tableList.value[i].dtEventTimeStamp}_${i}`,
            });
          }

          renderList = Object.freeze(arr);
          appendChildNodes();
          return;
        }
      };

      appendChildNodes();
    };

    /**
     * 分步更新行属性
     * 主要是是否Json格式化
     * @param startIndex
     */
    const stepUpdateRowProp = (startIndex = 0, formatJson = false) => {
      const inteval = 50;
      const endIndex = startIndex + inteval;

      for (let i = startIndex; i < endIndex; i++) {
        if (i < tableList.value.length) {
          const row = tableList.value[i];
          const config = tableRowConfig.get(row);
          config.value[ROW_F_JSON] = formatJson;
        }
      }

      if (endIndex < tableList.value.length) {
        requestAnimationFrame(() => stepUpdateRowProp(endIndex, formatJson));
      }
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
            return <span class='time-field'>{getOriginTimeShow(row[timeField.value])}</span>;
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
                formatJson={formatJson.value}
                jsonValue={row}
                onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink)}
              ></JsonFormatter>
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
          const config: RowConfig = tableRowConfig.get(row).value;
          return (
            // @ts-ignore
            <TableColumn
              content={getTableColumnContent(row, field)}
              field={field}
              formatJson={config[ROW_F_JSON]}
              row={row}
              onIcon-click={(type, content, isLink, depth, isNestedField) =>
                handleIconClick(type, content, field, row, isLink, depth, isNestedField)
              }
            ></TableColumn>
          );
        },
        renderHeaderCell: () => {
          const sortable = field.es_doc_values && field.tag !== 'union-source';
          return renderHead(field, order => {
            if (sortable) {
              const sortList = order ? [[field.field_name, order]] : [];
              const updatedSortList = store.state.indexFieldInfo.sort_list.map(item => {
                if (sortList.length > 0 && item[0] === field.field_name) {
                  return sortList[0];
                } else if (sortList.length === 0 && item[0] === field.field_name) {
                  return [field.field_name, 'desc'];
                }
                return item;
              });
              store.commit('updateIndexFieldInfo', { sort_list: updatedSortList });
              store.commit('updateIndexItemParams', { sort_list: sortList });
              store.dispatch('requestIndexSetQuery');
            }
          });
        },
      };
    };

    const setColWidth = (col, w = '100%') => {
      col.minWidth = col.width - 4;
      col.width = '100%';
    };

    const getFieldColumns = () => {
      if (showCtxType.value === 'table') {
        const columnList = [];
        const columns = visibleFields.value.length > 0 ? visibleFields.value : fullColumns.value;
        let maxColWidth = operatorToolsWidth.value + 40;
        let logField = null;

        columns.forEach(col => {
          const formatValue = formatColumn(col);
          if (col.field_name === 'log') {
            logField = formatValue;
          }

          columnList.push(formatValue);
          maxColWidth += formatValue.width;
        });

        if (!logField && columnList.length > 0) {
          logField = columnList[columnList.length - 1];
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

          const hanldeExpandClick = event => {
            event.stopPropagation();
            event.preventDefault();
            event.stopImmediatePropagation();

            config.expand = !config.expand;
            nextTick(() => {
              if (config.expand) {
                hanldeAfterExpandClick(event.target);
              }
            });
          };

          return (
            <span
              class={['bklog-expand-icon', { 'is-expaned': config.expand }]}
              onClick={hanldeExpandClick}
            >
              <i
                style={{ color: '#4D4F56', fontSize: '9px' }}
                class='bk-icon icon-play-shape'
              ></i>
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
              // @ts-ignore
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

    const getTableColumnContent = (row, field) => {
      // 日志来源 展示来源的索引集名称
      if (field?.tag === 'union-source') {
        return (
          unionIndexItemList.value.find(item => item.index_set_id === String(row.__index_set_id__))?.index_set_name ??
          ''
        );
      }
      return parseTableRowData(row, field.field_name, field.field_type, false);
    };

    const formatDateValue = (data, field_type) => {
      if (field_type === 'date') {
        return formatDate(Number(data)) || data;
      }
      // 处理纳秒精度的UTC时间格式
      if (field_type === 'date_nanos') {
        return formatDateNanos(data, true, true);
      }
      return data;
    };

    const getOriginTimeShow = data => {
      return formatDateValue(data, timeFieldType.value);
    };

    const setRouteParams = () => {
      const query = { ...route.query };

      const resolver = new RetrieveUrlResolver({
        keyword: store.getters.retrieveParams.keyword,
        addition: store.getters.retrieveParams.addition,
      });

      Object.assign(query, resolver.resolveParamsToUrl());

      router.replace({
        query,
      });
    };

    const handleAddCondition = (field, operator, value, isLink = false, depth = undefined, isNestedField = 'false') => {
      store
        .dispatch('setQueryCondition', { field, operator, value, isLink, depth, isNestedField })
        .then(([newSearchList, searchMode, isNewSearchPage]) => {
          setRouteParams();
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
          if (isLink) {
            const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage);
            window.open(openUrl, '_blank');
          }
        });
    };

    const handleTraceIdClick = traceId => {
      if (apmRelation.value?.is_active) {
        const { app_name: appName, bk_biz_id: bkBizId } = apmRelation.value.extra;
        const path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${traceId}`;
        const url = `${window.__IS_MONITOR_COMPONENT__ ? location.origin : window.MONITOR_URL}${path}`;
        window.open(url, '_blank');
      } else {
        bkMessage({
          theme: 'warning',
          message: $t('未找到相关的应用，请确认是否有Trace数据的接入。'),
        });
      }
    };

    const handleIconClick = (type, content, field, row, isLink, depth, isNestedField) => {
      let value = ['date', 'date_nanos'].includes(field.field_type) ? row[field.field_name] : content;
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');

      if (type === 'highlight') {
        RetrieveHelper.fire(RetrieveEvent.HILIGHT_TRIGGER, {
          event: 'mark',
          value: formatDateValue(value ?? content, field.field_type),
        });
        return;
      }

      if (type === 'trace-view') {
        handleTraceIdClick(value);
        return;
      }

      if (type === 'search') {
        // 将表格单元添加到过滤条件
        handleAddCondition(field.field_name, 'eq', [value], isLink, depth, isNestedField);
        return;
      }

      if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
        return;
      }
      // 根据当前显示字段决定传参
      if (['is', 'is not', 'new-search-page-is'].includes(type)) {
        const { getQueryAlias } = useFieldNameHook({ store });
        handleAddCondition(getQueryAlias(field), type, value === '--' ? [] : [value], isLink, depth, isNestedField);
        return;
      }
    };

    const handleMenuClick = (option, isLink) => {
      switch (option.operation) {
        case 'is':
        case 'is not':
        case 'not':
        case 'new-search-page-is':
          const { fieldName, operation, value, depth } = option;
          const operator = operation === 'not' ? 'is not' : operation;
          handleAddCondition(fieldName, operator, value === '--' ? [] : [value], isLink, depth);
          break;
        case 'copy':
          copyMessage(option.value);
          break;
        case 'highlight':
          RetrieveHelper.fire(RetrieveEvent.HILIGHT_TRIGGER, { event: 'mark', value: option.value });
          break;
        case 'display':
          emit('fields-updated', option.displayFieldNames, undefined, false);
          break;
        default:
          break;
      }
    };

    const { renderHead } = useHeaderRender();
    const setFullColumns = () => {
      /** 清空所有字段后所展示的默认字段  顺序: 时间字段，log字段，索引字段 */
      const dataFields = [];
      const indexSetFields = [];
      const logFields = [];
      indexFieldInfo.value.fields.forEach(item => {
        if (item.field_type === 'date') {
          dataFields.push(item);
        } else if (item.field_name === 'log' || item.field_alias === 'original_text') {
          logFields.push(item);
        } else if (!(item.field_type === '__virtual__' || item.is_built_in)) {
          indexSetFields.push(item);
        }
      });
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
      return [['expand', false]].reduce(
        (cfg, item: [keyof RowConfig, any]) => Object.assign(cfg, { [item[0]]: item[1] }),
        {},
      );
    };

    const updateTableRowConfig = (nextIdx = 0) => {
      for (let index = nextIdx; index < tableDataSize.value; index++) {
        const nextRow = tableList.value[index];
        if (!tableRowConfig.has(nextRow)) {
          const rowKey = `${ROW_KEY}_${index}`;
          tableRowConfig.set(
            nextRow,
            ref({
              [ROW_KEY]: rowKey,
              [ROW_INDEX]: index,
              [ROW_F_JSON]: formatJson.value,
              ...getRowConfigWithCache(),
            }),
          );
        }
      }
    };

    const isRequesting = ref(false);

    const debounceSetLoading = (delay = 120) => {
      setTimeout(() => {
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
          ></ExpandView>
        );
      },
    };

    watch(
      () => [tableShowRowIndex.value],
      () => {
        setTimeout(() => {
          computeRect();
        });
      },
    );

    watch(
      () => [props.contentType, formatJson.value, tableLineIsWrap.value],
      () => {
        scrollXOffsetLeft = 0;
        refScrollXBar.value?.scrollLeft(0);

        showCtxType.value = props.contentType;
        stepUpdateRowProp(0, formatJson.value);
        computeRect();
      },
    );

    watch(
      () => [fieldRequestCounter.value],
      () => {
        scrollXOffsetLeft = 0;
        refScrollXBar.value?.scrollLeft(0);

        setTimeout(() => {
          computeRect();
        });
      },
    );

    watch(
      () => [visibleFields.value.length],
      () => {
        if (!visibleFields.value.length) {
          setFullColumns();
        }
      },
    );

    watch(
      () => isLoading.value,
      () => {
        if (!isRequesting.value) {
          if (isLoading.value) {
            scrollToTop(0);
            renderList = [];
            return;
          }

          setRenderList();
        }
      },
    );

    watch(
      () => [tableDataSize.value],
      (val, oldVal) => {
        hasMoreList.value = tableDataSize.value > 0 && tableDataSize.value % 50 === 0;
        setRenderList(null);
        debounceSetLoading();
        updateTableRowConfig(oldVal?.[0] ?? 0);

        if (tableDataSize.value <= 50) {
          nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
        }
      },
      {
        immediate: true,
      },
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
          logField.width = logField.width + width;
        } else {
          const avgWidth = (col.width - width) / targetField.length;
          targetField.forEach(field => {
            field.width = field.width + avgWidth;
          });
        }
      }

      const sourceObj = visibleFields.value.reduce(
        (acc, field) => Object.assign(acc, { [field.field_name]: field.width }),
        {},
      );
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
        isRequesting.value = true;
        pageIndex.value++;
        const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
        setRenderList(maxLength);
        debounceSetLoading(0);
        nextTick(RetrieveHelper.updateMarkElement.bind(RetrieveHelper));
        return;
      }

      if (hasMoreList.value) {
        isRequesting.value = true;

        return store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then(resp => {
            if (resp?.size === 50) {
              pageIndex.value++;
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
    };

    // 监听滚动条滚动位置
    // 判定是否需要拉取更多数据
    const { offsetWidth, scrollWidth, computeRect, scrollToTop } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
      refLoadMoreElement,
    });

    const setRowboxTransform = () => {
      if (refResultRowBox.value && refRootElement.value) {
        refResultRowBox.value.scrollLeft = scrollXOffsetLeft;
        if (refTableHead.value) {
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
      return (
        <div
          ref={refTableHead}
          class={['bklog-row-container row-header']}
        >
          <div class='bklog-list-row'>
            {[...leftColumns.value, ...getFieldColumns(), ...rightColumns.value].map(column => (
              <LogCell
                key={column.key}
                width={column.width}
                class={[column.class ?? '', 'bklog-row-cell header-cell', column.fixed]}
                minWidth={column.minWidth > 0 ? column.minWidth : column.width}
                resize={column.resize}
                onResize-width={w => handleColumnWidthChange(w, column)}
              >
                {column.renderHeaderCell?.({ column }, h) ?? column.title}
              </LogCell>
            ))}
          </div>
        </div>
      );
    };

    const renderScrollTop = () => {
      return <ScrollTop on-scroll-top={afterScrollTop}></ScrollTop>;
    };

    const renderRowCells = (row, rowIndex) => {
      const { expand } = tableRowConfig.get(row).value;

      return [
        <div
          class='bklog-list-row'
          data-row-index={rowIndex}
          data-row-click
        >
          {[...leftColumns.value, ...getFieldColumns(), ...rightColumns.value].map(column => {
            const width = ['100%', 'default', 'auto'].includes(column.width) ? column.width : `${column.width}px`;
            const cellStyle = {
              width,
              minWidth: column.minWidth ? `${column.minWidth}px` : `${column.width}px`,
            };
            if (typeof column.minWidth === 'number' && column.width < column.minWidth) {
              cellStyle.minWidth = `${column.width}px`;
            }
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

    const renderRowVNode = () => {
      return renderList.map((row, rowIndex) => {
        const logLevel = gradeOption.value.disabled ? '' : RetrieveHelper.getLogLevel(row.item, gradeOption.value);

        return [
          <RowRender
            key={row[ROW_KEY]}
            class={['bklog-row-container', logLevel ?? 'normal']}
            row-index={rowIndex}
          >
            {renderRowCells(row.item, rowIndex)}
          </RowRender>,
        ];
      });
    };

    const handleScrollXChanged = (event: MouseEvent) => {
      scrollXOffsetLeft = (event.target as HTMLElement)?.scrollLeft;
      setRowboxTransform();
    };

    const renderScrollXBar = () => {
      return (
        <ScrollXBar
          ref={refScrollXBar}
          innerWidth={scrollWidth.value}
          outerWidth={offsetWidth.value}
          onScroll-change={handleScrollXChanged}
        ></ScrollXBar>
      );
    };

    const isFieldSettingShow = computed(() => {
      return !store.getters.isUnionSearch && !isExternal.value;
    });

    const hasCollectorConfigId = computed(() => {
      const indexSetList = store.state.retrieve.indexSetList;
      const indexSetId = route.params?.indexId;
      const currentIndexSet = indexSetList.find(item => item.index_set_id == indexSetId);
      return currentIndexSet?.collector_config_id;
    });

    const isExternal = computed(() => store.state.isExternal);

    const loadingText = computed(() => {
      if (isLoading.value && !isRequesting.value) {
        return;
      }

      if (hasMoreList.value && (isLoading.value || isRending.value)) {
        return 'Loading ...';
      }

      if (!isRequesting.value && !hasMoreList.value && tableDataSize.value > 0) {
        return ` - 已加载所有数据: 共计 ${tableDataSize.value} 条 - `;
      }

      return '';
    });

    const renderLoader = () => {
      return (
        <div
          ref={refLoadMoreElement}
          class={['bklog-requsting-loading']}
        >
          <div style={{ width: `${offsetWidth.value}px`, minWidth: '100%' }}>{loadingText.value}</div>
        </div>
      );
    };

    const renderFixRightShadow = () => {
      if (window?.__IS_MONITOR_TRACE__) {
        return null;
      }
      if (tableDataSize.value > 0 && showCtxType.value === 'table') {
        return <div class='fixed-right-shadown'></div>;
      }

      return null;
    };

    const isTableLoading = computed(() => {
      return (isRequesting.value && !isRequesting.value && tableDataSize.value === 0) || isRending.value;
    });

    const getExceptionRender = () => {
      if (tableDataSize.value === 0) {
        if (isRequesting.value || isLoading.value) {
          return (
            <bk-exception
              style='margin-top: 100px;'
              class='exception-wrap-item exception-part'
              scene='part'
              type='search-empty'
            >
              loading...
            </bk-exception>
          );
        }
        if ($t('检索结果为空') === exceptionMsg.value) {
          return (
            <div class='bklog-empty-data'>
              <h1>{$t('检索无数据')}</h1>
              <div class='sub-title'>您可按照以下顺序调整检索方式</div>
              <div class='empty-validate-steps'>
                <div class='validate-step1'>
                  <h3>1. 优化查询语句</h3>
                  <div class='step1-content'>
                    <span class='step1-content-label'>查询范围：</span>
                    <span class='step1-content-value'>
                      log: bklog*
                      <br />
                      包含bklog
                      <br />= bklog 使用通配符 (*)
                    </span>
                  </div>
                  <div class='step1-content'>
                    <span class='step1-content-label'>精准匹配：</span>
                    <span class='step1-content-value'>log: "bklog"</span>
                  </div>
                </div>
                <div class='validate-step2'>
                  <h3>2. 检查是否为分词问题</h3>
                  <div>
                    当您的鼠标移动至对应日志内容上时，该日志单词将展示为蓝色。
                    <br />
                    <br />
                    若目标内容为整段蓝色，或中间存在字符粘连的情况。
                    <br />
                    可能是因为分词导致的问题；
                    <br />
                    <span
                      class='segment-span-tag'
                      onClick={openConfiguration}
                    >
                      点击设置自定义分词
                    </span>
                    <br />
                    <br />
                    将字符粘连的字符设置至自定义分词中，等待 3～5 分钟，新上报的日志即可生效设置。
                  </div>
                </div>
                <div class='validate-step3'>
                  <h3>3. 一键反馈</h3>
                  <div>
                    若您仍无法确认问题原因，请点击下方反馈按钮与我们联系，平台将第一时间响应处理。 <br></br>
                    {/* <span class='segment-span-tag'>问题反馈</span> */}
                    <a
                      class='segment-span-tag'
                      href={`wxwork://message/?username=BK助手`}
                    >
                      问题反馈
                    </a>
                  </div>
                </div>
              </div>
            </div>
          );
        }

        return (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='search-empty'
          >
            {exceptionMsg.value}
          </bk-exception>
        );
      }

      return null;
    };

    const onRootClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;

      if (
        (target?.hasAttribute('data-row-click') && target?.hasAttribute('data-row-index')) ||
        !(
          target?.classList.contains('segment-content') ||
          target?.classList.contains('bklog-json-view-icon-expand') ||
          target?.classList.contains('bklog-json-view-icon-text') ||
          target?.classList.contains('black-mark') ||
          target?.parentElement?.classList.contains('segment-content')
        )
      ) {
        const row = target.hasAttribute('data-row-index') ? target : target.closest('[data-row-click]');
        const index = parseInt(row?.getAttribute?.('data-row-index') ?? '-1', 10);

        if (index >= 0) {
          const { item } = renderList[index] ?? {};
          if (item) {
            const config: RowConfig = tableRowConfig.get(item).value;
            config.expand = !config.expand;
            nextTick(() => {
              if (config.expand) {
                hanldeAfterExpandClick(target);
              }
            });
          }
        }
      }
    };

    const openConfiguration = () => {
      if (isFieldSettingShow.value && store.state.spaceUid && hasCollectorConfigId.value) {
        RetrieveHelper.setIndexConfigOpen(true);
      } else {
        bkMessage({
          theme: 'primary',
          message: '第三方ES、计算平台索引集类型不支持自定义分词',
        });
      }
    };
    onBeforeUnmount(() => {
      popInstanceUtil.uninstallInstance();
    });

    return {
      refRootElement,
      refResultRowBox,
      isTableLoading,
      renderRowVNode,
      renderFixRightShadow,
      renderScrollTop,
      renderScrollXBar,
      renderLoader,
      renderHeadVNode,
      getExceptionRender,
      onRootClick,
      tableDataSize,
      resultContainerId,
      hasScrollX,
      showHeader,
      isRequesting,
      isLoading,
      exceptionMsg,
    };
  },
  render() {
    return (
      <div
        ref='refRootElement'
        class={['bklog-result-container', { 'has-scroll-x': this.hasScrollX, 'show-header': this.showHeader }]}
        v-bkloading={{ isLoading: this.isTableLoading, opacity: 0.1 }}
        onClick={this.onRootClick}
      >
        {this.renderHeadVNode()}
        <div
          id={this.resultContainerId}
          ref='refResultRowBox'
          class={['bklog-row-box']}
        >
          {this.renderRowVNode()}
        </div>
        {this.getExceptionRender()}
        {this.renderFixRightShadow()}
        {this.renderScrollXBar()}
        {this.renderLoader()}
        {this.renderScrollTop()}
        <div class='resize-guide-line'></div>
      </div>
    );
  },
});
