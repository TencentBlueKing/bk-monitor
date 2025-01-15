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
import { computed, defineComponent, ref, watch, h, Ref, provide, set } from 'vue';

import {
  parseTableRowData,
  formatDateNanos,
  formatDate,
  copyMessage,
  setDefaultTableWidth,
  TABLE_LOG_FIELDS_SORT_REGULAR,
} from '@/common/util';
import JsonFormatter from '@/global/json-formatter.vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { uniqueId } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';

import ExpandView from '../original-log/expand-view.vue';
import OperatorTools from '../original-log/operator-tools.vue';
import { getConditionRouterParams } from '../panel-util';
import LogCell from './log-cell';
import { bkMessage } from 'bk-magic-vue';
import {
  LOG_SOURCE_F,
  ROW_EXPAND,
  ROW_F_ORIGIN_CTX,
  ROW_F_ORIGIN_OPT,
  ROW_F_ORIGIN_TIME,
  ROW_INDEX,
  ROW_KEY,
  RowProxyData,
  SECTION_SEARCH_INPUT,
} from './log-row-attributes';
import RowRender from './row-render';
import ScrollTop from './scroll-top';
import ScrollXBar from './scroll-x-bar';
import TableColumn from './table-column.vue';
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

type RowData = Record<string, any>;
type ColumnFiled = Record<string, any>;

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

    const pageIndex = ref(1);
    // 前端本地分页
    const pageSize = ref(50);
    const isRending = ref(false);
    const visibleRowLength = ref(50);

    const tableRowConfig = new WeakMap();
    const tableCellCache = new WeakMap<RowData, WeakMap<ColumnFiled, any>>();

    const renderList = ref([]);
    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const formatJson = computed(() => store.state.tableJsonFormat);
    const tableShowRowIndex = computed(() => store.state.tableShowRowIndex);
    const tableLineIsWrap = computed(() => store.state.tableLineIsWrap);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading || indexFieldInfo.value.is_loading);
    const kvShowFieldsList = computed(() => Object.keys(indexSetQueryResult.value?.fields ?? {}) || []);
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const tableDataSize = computed(() => indexSetQueryResult.value?.list?.length ?? 0);
    const fieldRequestCounter = computed(() => indexFieldInfo.value.request_counter);
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const tableList = computed(() => indexSetQueryResult.value?.list ?? []);

    const apmRelation = computed(() => store.state.indexSetFieldConfig.apm_relation);

    const fullColumns = ref([]);
    const showCtxType = ref(props.contentType);

    const router = useRouter();
    const route = useRoute();

    const totalCount = computed(() => {
      const count = store.state.indexSetQueryResult.total;
      if (count._isBigNumber) {
        return count.toNumber();
      }

      return count;
    });

    const hasMoreList = computed(
      () => totalCount.value > tableList.value.length || pageIndex.value * pageSize.value < totalCount.value,
    );

    const intersectionArgs: Ref<RowProxyData> = ref({});
    const rowProxy: RowProxyData = {};

    const setRenderList = (length?, next?) => {
      const targetLength = length ?? tableDataSize.value;
      const inteval = 50;

      const appendChildNodes = () => {
        const appendLength = targetLength - renderList.value.length;
        const stepLength = appendLength > inteval ? inteval : appendLength;
        const startIndex = renderList.value.length - 1;

        if (appendLength > 0) {
          renderList.value.push(
            ...new Array(stepLength).fill('').map((_, i) => {
              const index = i + startIndex + 1;
              const row = tableList.value[index];
              return { item: row, [ROW_KEY]: `${row.dtEventTimeStamp}_${index}` };
            }),
          );
          appendChildNodes();

          return;
        }

        next?.();
      };

      appendChildNodes();
    };

    const resetRowState = () => {
      for (let i = 0; i < tableDataSize.value; i++) {
        const target = intersectionArgs.value[`${i}`];
        if (target && !target.visible) {
          rowProxy[`${i}`].mounted = false;
          set(target, 'mounted', false);
        }
      }
    };

    /**
     * 设置预加载区域
     */
    const setVisibleIndexSection = () => {
      const idxs = Object.entries(rowProxy ?? {})
        .filter(([, v]) => v.visible)
        .map(([, { rowIndex }]) => rowIndex);

      const length = idxs.length > 0 ? idxs.length : pageSize.value;
      const buffer = Math.max(length, 1);
      const max = Math.max(...idxs, 0) + buffer;
      const min = idxs.length ? Math.min(...idxs) - buffer : 0;
      const end = Math.min(max, tableDataSize.value);
      const start = Math.max(min, 0);
      visibleRowLength.value = buffer;
      Object.assign(rowProxy, { start, end });
    };

    const delayUpdate = () => {
      setVisibleIndexSection();
      Object.keys(rowProxy).forEach(key => {
        set(intersectionArgs.value, key, rowProxy[key]);
      });
    };

    const updateIntersectionArgs = (index, visible?, height?) => {
      if (height && rowProxy[index]?.mounted === false) {
        rowProxy[index].mounted = true;
      }

      if (!rowProxy[index]) {
        Object.assign(rowProxy, {
          [index]: {
            visible,
            height,
            rowIndex: Number(index),
            mounted: false,
          },
        });
      }
      Object.assign(rowProxy[index], {
        visible: visible ?? rowProxy[index].visible,
        height: height ?? rowProxy[index].height,
      });
    };

    const intersectionObserver = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          const index = entry.target.getAttribute('data-row-index');
          updateIntersectionArgs(index, entry.isIntersecting);
        });
        delayUpdate();
      },
      { threshold: 0.001 },
    );

    provide('intersectionObserver', intersectionObserver);
    provide('rowProxy', intersectionArgs);
    provide('tableCellCache', tableCellCache);

    const searchContainerHeight = ref(52);

    const resultContainerId = ref(uniqueId('result_container_key_'));
    const resultContainerIdSelector = `#${resultContainerId.value}`;

    const operatorToolsWidth = computed(() => {
      return indexSetOperatorConfig.value?.bcsWebConsole?.is_active ? 84 : 58;
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
          return (
            // @ts-ignore
            <TableColumn
              content={getTableColumnContent(row, field)}
              field={field}
              row={row}
              onIcon-click={(type, content, isLink, depth) => handleIconClick(type, content, field, row, isLink, depth)}
            ></TableColumn>
          );
        },
        renderHeaderCell: () => {
          const sortable = field.es_doc_values && field.tag !== 'union-source';
          return renderHead(field, order => {
            if (sortable) {
              const sortList = order ? [[field.field_name, order]] : [];
              store.commit('updateIndexFieldInfo', { sort_list: sortList });
              store.commit('updateIndexItemParams', { sort_list: sortList });
              store.dispatch('requestIndexSetQuery');
            }
          });
        },
      };
    };

    const getFieldColumns = () => {
      if (showCtxType.value === 'table') {
        if (visibleFields.value.length) {
          return visibleFields.value.map(formatColumn);
        }

        return fullColumns.value.map(formatColumn);
      }

      return originalColumns.value;
    };

    const leftColumns = computed(() => [
      {
        field: '',
        key: ROW_EXPAND,
        // 设置需要显示展开图标的列
        type: 'expand',
        title: '',
        width: 50,
        align: 'center',
        resize: false,
        fixed: 'left',
        renderBodyCell: ({ row }) => {
          const config: RowConfig = tableRowConfig.get(row).value;

          const hanldeExpandClick = () => {
            config.expand = !config.expand;
          };

          return (
            <span
              class={['bklog-expand-icon', { 'is-expaned': config.expand }]}
              onClick={hanldeExpandClick}
            >
              <i class='bk-icon icon-play-shape'></i>
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

    const rightColumns = computed(() => [
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
              handle-click={event => props.handleClickTools(event, row, indexSetOperatorConfig.value)}
              index={row[ROW_INDEX]}
              operator-config={indexSetOperatorConfig.value}
              row-data={row}
            />
          );
        },
      },
    ]);

    const getTableColumnContent = (row, field) => {
      // 日志来源 展示来源的索引集名称
      if (field?.tag === 'union-source') {
        return (
          unionIndexItemList.value.find(item => item.index_set_id === String(row.__index_set_id__))?.index_set_name ??
          ''
        );
      }
      return parseTableRowData(row, field.field_name, field.field_type);
    };

    const getOriginTimeShow = data => {
      if (timeFieldType.value === 'date') {
        return formatDate(Number(data)) || data;
      }
      // 处理纳秒精度的UTC时间格式
      if (timeFieldType.value === 'date_nanos') {
        return formatDateNanos(data, true, true);
      }
      return data;
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

    const handleAddCondition = (field, operator, value, isLink = false, depth = undefined) => {
      store
        .dispatch('setQueryCondition', { field, operator, value, isLink, depth })
        .then(([newSearchList, searchMode, isNewSearchPage]) => {
          setRouteParams();
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
        const url = `${window.__IS_MONITOR_APM__ ? location.origin : window.MONITOR_URL}${path}`;
        window.open(url, '_blank');
      } else {
        bkMessage({
          theme: 'warning',
          message: $t('未找到相关的应用，请确认是否有Trace数据的接入。'),
        });
      }
    };

    const handleIconClick = (type, content, field, row, isLink, depth) => {
      let value = ['date', 'date_nanos'].includes(field.field_type) ? row[field.field_name] : content;
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');

      if (type === 'trace-view') {
        handleTraceIdClick(value);
        return;
      }

      if (type === 'search') {
        // 将表格单元添加到过滤条件
        handleAddCondition(field.field_name, 'eq', [value], isLink);
        return;
      }

      if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
        return;
      }

      if (['is', 'is not', 'new-search-page-is'].includes(type)) {
        handleAddCondition(field.field_name, type, value === '--' ? [] : [value], isLink, depth);
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
      return [
        ['expand', false],
        ['isIntersect', true],
        ['minHeight', 40],
        ['rowMinHeight', 40],
        ['stickyTop', 0],
      ].reduce((cfg, item: [keyof RowConfig, any]) => Object.assign(cfg, { [item[0]]: item[1] }), {});
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
              ...getRowConfigWithCache(),
            }),
          );
        }
      }
    };

    const isRequesting = ref(false);

    const debounceSetLoading = () => {
      setTimeout(() => {
        isRequesting.value = false;
      }, 120);
    };

    const expandOption = {
      render: ({ row }) => {
        return (
          <ExpandView
            data={row}
            kv-show-fields-list={kvShowFieldsList.value}
            list-data={row}
            onValue-click={(type, content, isLink, field, depth) =>
              handleIconClick(type, content, field, row, isLink, depth)
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
        scrollXOffsetLeft.value = 0;
        refScrollXBar.value?.scrollLeft(0);
        isRending.value = true;
        renderList.value = [];
        pageIndex.value = 1;

        setTimeout(() => {
          showCtxType.value = props.contentType;
          resetRowState();
          const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
          setRenderList(maxLength, () => {
            isRending.value = false;
          });

          computeRect();
        });
      },
    );

    watch(
      () => [fieldRequestCounter.value],
      () => {
        scrollXOffsetLeft.value = 0;
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
            renderList.value.length = 0;
            renderList.value = [];

            return;
          }

          setRenderList();
        }
      },
    );

    watch(
      () => [tableDataSize.value],
      (val, oldVal) => {
        setRenderList(null, () => {
          debounceSetLoading();
        });
        updateTableRowConfig(oldVal?.[0] ?? 0);
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
      if (isRequesting.value) {
        return;
      }

      if (pageIndex.value * pageSize.value < tableDataSize.value) {
        isRequesting.value = true;
        pageIndex.value++;
        const maxLength = Math.min(pageSize.value * pageIndex.value, tableDataSize.value);
        setRenderList(maxLength, debounceSetLoading);
        return;
      }

      if (totalCount.value > tableList.value.length) {
        isRequesting.value = true;

        return store.dispatch('requestIndexSetQuery', { isPagination: true }).finally(() => {
          pageIndex.value++;
          debounceSetLoading();
        });
      }

      return Promise.resolve(false);
    };

    useResizeObserve(SECTION_SEARCH_INPUT, entry => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    const scrollXOffsetLeft = ref(0);
    const refScrollXBar = ref();

    // 监听滚动条滚动位置
    // 判定是否需要拉取更多数据
    const { offsetWidth, computeRect } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
    });

    const scrollWidth = computed(() => {
      const callback = (acc, item) => {
        acc = acc + (item?.width ?? 0);
        return acc;
      };

      const leftWidth = leftColumns.value.reduce(callback, 0);
      const rightWidth = rightColumns.value.reduce(callback, 0);
      const visibleWidth = getFieldColumns().reduce(callback, 0);

      if (isNaN(visibleWidth)) {
        return offsetWidth.value;
      }

      return leftWidth + rightWidth + visibleWidth - 2;
    });

    const hasScrollX = computed(() => {
      return offsetWidth.value < scrollWidth.value;
    });

    useWheel({
      target: refRootElement,
      callback: (event: WheelEvent) => {
        const maxOffset = scrollWidth.value - offsetWidth.value;

        if (event.deltaX !== 0 && hasScrollX.value) {
          event.stopPropagation();
          event.stopImmediatePropagation();
          event.preventDefault();

          requestAnimationFrame(() => {
            const nextOffset = scrollXOffsetLeft.value + event.deltaX;
            if (nextOffset <= maxOffset && nextOffset >= 0) {
              scrollXOffsetLeft.value += event.deltaX;
              refScrollXBar.value?.scrollLeft(nextOffset);
            }
          });
        }
      },
    });

    const operatorFixRightWidth = computed(() => {
      const operatorWidth = operatorToolsWidth.value;
      const diff = scrollWidth.value - scrollXOffsetLeft.value - offsetWidth.value;
      return diff > operatorWidth ? 0 : operatorWidth - diff;
    });

    const setHeaderStyle = () => {
      if (refTableHead.value) {
        refTableHead.value.style.setProperty('transform', `translateX(-${scrollXOffsetLeft.value}px)`);
        refTableHead.value.style.setProperty('top', `${searchContainerHeight.value}px`);
      }
    };

    const setBodyStyle = () => {
      if (refRootElement.value) {
        refRootElement.value.style.setProperty('--scroll-left', `-${scrollXOffsetLeft.value}px`);
        refRootElement.value.style.setProperty('--padding-right', `${operatorToolsWidth.value}px`);
        refRootElement.value.style.setProperty('--fix-right-width', `${operatorFixRightWidth.value}px`);
        refRootElement.value.style.setProperty('--scroll-width', `${Math.max(offsetWidth.value, scrollWidth.value)}px`);
        refRootElement.value.style.setProperty(
          '--last-column-left',
          `${offsetWidth.value - operatorToolsWidth.value + scrollXOffsetLeft.value}px`,
        );
      }
    };

    watch(
      () => [
        scrollXOffsetLeft.value,
        operatorToolsWidth.value,
        operatorFixRightWidth.value,
        offsetWidth.value,
        scrollWidth.value,
        searchContainerHeight.value,
      ],
      () => {
        setBodyStyle();
        setHeaderStyle();
      },
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
                minWidth={column.minWidth ?? 'auto'}
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
      return <ScrollTop></ScrollTop>;
    };

    const renderRowCells = (row, rowIndex) => {
      const { expand } = tableRowConfig.get(row).value;
      const opStyle = {
        width: `${operatorToolsWidth.value}px`,
        minWidth: `${operatorToolsWidth.value}px`,
      };

      return [
        <div class='bklog-list-row'>
          {[...leftColumns.value, ...getFieldColumns(), ...rightColumns.value].map(column => {
            const width = ['100%', 'default', 'auto'].includes(column.width) ? column.width : `${column.width}px`;
            const cellStyle = {
              width,
              minWidth: column.minWidth ? `${column.minWidth}px` : `${column.width}px`,
            };
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
          <div
            style={opStyle}
            class={['hidden-field bklog-row-cell']}
          ></div>
        </div>,
        expand ? expandOption.render({ row }) : '',
      ];
    };

    const renderRowVNode = () => {
      return renderList.value.map((row, rowIndex) => {
        return (
          <RowRender
            key={row[ROW_KEY]}
            class={['bklog-row-container']}
            row-index={rowIndex}
          >
            {renderRowCells(row.item, rowIndex)}
          </RowRender>
        );
      });
    };

    const handleScrollXChanged = (event: MouseEvent) => {
      scrollXOffsetLeft.value = (event.target as HTMLElement).scrollLeft;
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

    const loadingText = computed(() => {
      if (isLoading.value && !isRequesting.value) {
        return;
      }

      if (hasMoreList.value && (isLoading.value || isRending.value)) {
        return 'Loading ...';
      }

      if (!isRequesting.value && !hasMoreList.value && tableDataSize.value > 0) {
        return `已加载所有数据: 共计${tableDataSize.value}条`;
      }

      return '';
    });

    const renderLoader = () => {
      return (
        <div class={['bklog-requsting-loading']}>
          <div style={{ width: `${offsetWidth.value}px` }}>{loadingText.value}</div>
        </div>
      );
    };

    const renderFixRightShadow = () => {
      if (tableDataSize.value > 0) {
        return <div class='fixed-right-shadown'></div>;
      }

      return null;
    };

    const isTableLoading = computed(() => {
      return (isRequesting.value && !isRequesting.value && tableDataSize.value === 0) || isRending.value;
    });

    return {
      refRootElement,
      isTableLoading,
      renderRowVNode,
      renderFixRightShadow,
      renderScrollTop,
      renderScrollXBar,
      renderLoader,
      renderHeadVNode,
      tableDataSize,
      resultContainerId,
      hasScrollX,
      showHeader,
      isRequesting,
      isLoading,
    };
  },
  render() {
    return (
      <div
        ref='refRootElement'
        class={['bklog-result-container', { 'has-scroll-x': this.hasScrollX, 'show-header': this.showHeader }]}
        v-bkloading={{ isLoading: this.isTableLoading, opacity: 0.1 }}
      >
        {this.renderHeadVNode()}
        <div
          id={this.resultContainerId}
          class={['bklog-row-box']}
        >
          {this.renderRowVNode()}
        </div>
        {this.tableDataSize === 0 ? (
          <bk-exception
            style='margin-top: 100px;'
            class='exception-wrap-item exception-part'
            scene='part'
            type='search-empty'
          >
            {this.isRequesting || this.isLoading ? 'loading...' : this.$t('检索结果为空')}
          </bk-exception>
        ) : null}
        {this.renderFixRightShadow()}
        {this.renderScrollXBar()}
        {this.renderLoader()}
        {this.renderScrollTop()}
        <div class='resize-guide-line'></div>
      </div>
    );
  },
});
