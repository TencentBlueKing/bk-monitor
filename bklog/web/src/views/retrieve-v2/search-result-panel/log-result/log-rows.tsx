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
import { computed, defineComponent, ref, watch, h, onMounted, onBeforeUnmount, Ref, provide, set } from 'vue';

import { parseTableRowData, formatDateNanos, formatDate, copyMessage } from '@/common/util';
import JsonFormatter from '@/global/json-formatter.vue';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import useWheel from '@/hooks/use-wheel';
import { uniqueId, debounce } from 'lodash';

import ExpandView from '../original-log/expand-view.vue';
import OperatorTools from '../original-log/operator-tools.vue';
import { getConditionRouterParams } from '../panel-util';
import LogCell from './log-cell';
import {
  ROW_CONFIG,
  ROW_EXPAND,
  ROW_F_ORIGIN_CTX,
  ROW_F_ORIGIN_OPT,
  ROW_F_ORIGIN_TIME,
  ROW_INDEX,
  ROW_KEY,
  SECTION_SEARCH_INPUT,
} from './log-row-attributes';
import RowRender from './row-render';
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
    const columns = ref([]);
    const tableData = ref([]);
    const refRootElement: Ref<HTMLElement> = ref();
    const refBoxElement: Ref<HTMLElement> = ref();
    const rowUpdateCounter = ref(0);
    // 本地分页
    const pageIndex = ref(1);
    const pageSize = 50;

    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const formatJson = computed(() => store.state.tableJsonFormat);
    const tableShowRowIndex = computed(() => store.state.tableShowRowIndex);
    const isLimitExpandView = computed(() => store.state.isLimitExpandView);
    const tableLineIsWrap = computed(() => store.state.tableLineIsWrap);
    const fieldRequestCounter = computed(() => indexFieldInfo.value.request_counter);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading);
    const kvShowFieldsList = computed(() => Object.keys(indexSetQueryResult.value?.fields ?? {}) || []);
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const tableDataSize = computed(() => indexSetQueryResult.value?.list?.length ?? 0);

    const totalCount = computed(() => {
      const count = store.state.indexSetQueryResult.total;
      if (count._isBigNumber) {
        return count.toNumber();
      }

      return count;
    });

    const hasMoreList = computed(() => totalCount.value > tableData.value.length);

    const visibleIndexs = ref({ startIndex: 0, endIndex: 30 });

    const rowsOffsetTop = ref(0);
    const searchContainerHeight = ref(52);
    const bufferCount = 30;

    const resultContainerId = ref(uniqueId('result_container_key_'));
    const resultContainerIdSelector = `#${resultContainerId.value}`;

    const tableRowStore = new Map<string, RowConfig>();
    let updateRow: 'all' | null | number = null;

    const sizes = ref([]);
    const updateSizes = () => {
      let accumulator = 0;
      sizes.value = tableData.value.map(row => {
        const rowConfig = row[ROW_CONFIG];
        const current = rowConfig.minHeight;
        accumulator += current;
        return { accumulator: accumulator - current, size: current };
      });
    };

    const debounceUpdateSizes = debounce(updateSizes, 90);

    const operatorToolsWidth = computed(() => {
      return indexSetOperatorConfig.value?.bcsWebConsole?.is_active ? 84 : 58;
    });

    const updateRowHeight = (rowIndex: number, target: HTMLElement) => {
      const row = tableData.value[rowIndex];
      if (!row?.[ROW_KEY] || !target || !tableRowStore.has(row[ROW_KEY])) {
        return;
      }

      const config: RowConfig = row[ROW_CONFIG];
      set(config, 'minHeight', target.offsetHeight);
      const rowElement = target.querySelector('.bklog-list-row') as HTMLElement;
      set(config, 'rowMinHeight', rowElement.offsetHeight);
      Object.assign(tableRowStore.get(row[ROW_KEY]), config);
      debounceUpdateSizes();
    };

    const handleRowResize = (rowIndex, entry) => {
      updateRowHeight(rowIndex, entry.target);
    };

    const dounceSetUpdateRow = debounce((val = null, callback?) => {
      updateRow = val;
      callback?.();
    });

    const $resizeObserver = new ResizeObserver(entries => {
      if (updateRow === 'all') {
        requestAnimationFrame(() => {
          if (!Array.isArray(entries)) {
            return;
          }
          for (const entry of entries) {
            if (entry.target) {
              const index = entry.target.getAttribute('data-row-index');
              if (index) {
                updateRowHeight(parseInt(index), entry.target as HTMLElement);
              }
            }
          }
        });

        dounceSetUpdateRow();
      }
    });

    provide('vscrollResizeObserver', $resizeObserver);
    provide('handleRowResize', handleRowResize);
    provide('dounceSetUpdateRow', dounceSetUpdateRow);

    const renderColumns = computed(() => {
      return [
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
            const config: RowConfig = row[ROW_CONFIG];

            const hanldeExpandClick = () => {
              dounceSetUpdateRow('all', () => {
                config.expand = !config.expand;
                tableRowStore.get(row[ROW_KEY]).expand = config.expand;
              });
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
            return row[ROW_INDEX] + 1;
          },
        },
        ...columns.value,
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

    const handleAddCondition = (field, operator, value, isLink = false, depth = undefined) => {
      store
        .dispatch('setQueryCondition', { field, operator, value, isLink, depth })
        .then(([newSearchList, searchMode, isNewSearchPage]) => {
          if (isLink) {
            const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage);
            window.open(openUrl, '_blank');
          }
        });
    };

    const handleIconClick = (type, content, field, row, isLink, depth) => {
      let value = ['date', 'date_nanos'].includes(field.field_type) ? row[field.field_name] : content;
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');

      if (type === 'search') {
        // 将表格单元添加到过滤条件
        handleAddCondition(field.field_name, 'eq', [value], isLink);
      } else if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
      } else if (['is', 'is not', 'new-search-page-is'].includes(type)) {
        handleAddCondition(field.field_name, type, value === '--' ? [] : [value], isLink, depth);
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
    const loadTableColumns = () => {
      if (props.contentType === 'table') {
        return [
          ...visibleFields.value.map(field => {
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
                    is-wrap={tableLineIsWrap.value}
                    onIcon-click={(type, content, isLink, depth) =>
                      handleIconClick(type, content, field, row, isLink, depth)
                    }
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
          }),
        ];
      }

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
          width: 'auto',
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
    };

    const getStoreRowAttr = <K extends keyof RowConfig>(rowKey: string, attrName: K, value: RowConfig[K]) => {
      if (!tableRowStore.has(rowKey)) {
        tableRowStore.set(rowKey, { [attrName]: value });
        return value;
      }

      if (tableRowStore.get(rowKey)[attrName] === undefined) {
        Object.assign(tableRowStore.get(rowKey), { [attrName]: value });
        return value;
      }

      return tableRowStore.get(rowKey)[attrName];
    };

    const getRowConfigWithCache = index => {
      const rowKey = `${ROW_KEY}_${index}`;
      return [
        ['expand', false],
        ['isIntersect', true],
        ['minHeight', 40],
        ['rowMinHeight', 40],
        ['stickyTop', 0],
      ].reduce(
        (cfg, item: [keyof RowConfig, any]) =>
          Object.assign(cfg, { [item[0]]: getStoreRowAttr(rowKey, item[0], item[1]) }),
        {},
      );
    };

    /**
     * 当前table长度改变时清理缓存数据
     * @param length
     */
    const clearRowConfigCache = (length: number) => {
      tableRowStore.keys().forEach(key => {
        const index = Number(key.split('_')[1]);
        if (index >= length) {
          [
            ['expand', false],
            ['minHeight', 40],
            ['rowMinHeight', 40],
          ].forEach(args => {
            const field = args[0] as string;
            Object.assign(tableRowStore.get(key), { [field]: args[1] });
          });
        }
      });
    };

    /**
     * 当切换操作时，重新计算行高
     * 原则上，此时滚动到最上方，可视区域开始的Index为0
     */
    const resetTableMinheight = (length?) => {
      const endIndex = length ?? visibleIndexs.value.endIndex;
      clearRowConfigCache(endIndex - 1);
      const startIndex = endIndex - 1;
      for (let i = startIndex; i < tableData.value.length; i++) {
        const config = tableData.value[i][ROW_CONFIG];
        ['minHeight', 'rowMinHeight'].forEach(key => {
          config[key] = 40;
        });
      }
    };

    const loadTableData = (next?) => {
      clearRowConfigCache(tableData.value.length);
      const startIdx = 0;
      const endIdx = pageIndex.value * pageSize;
      dounceSetUpdateRow('all', () => {
        tableData.value = (indexSetQueryResult.value.list || []).slice(startIdx, endIdx).map((row, index) => {
          const rowKey = `${ROW_KEY}_${index}`;

          return Object.assign({}, row, {
            [ROW_KEY]: rowKey,
            [ROW_INDEX]: index,
            [ROW_CONFIG]: getRowConfigWithCache(index),
          });
        });

        next?.();
      });
    };

    const totalSize = computed(() => {
      if (sizes.value?.length) {
        return sizes.value[sizes.value.length - 1].accumulator;
      }

      return 0;
    });

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
      () => pageIndex.value,
      () => {
        loadTableData(() => {
          updateSizes();
          debounceSetLoading();
        });
      },
    );

    watch(
      () => [fieldRequestCounter.value, props.contentType],
      () => {
        dounceSetUpdateRow('all', () => {
          pageIndex.value = 1;
          columns.value = loadTableColumns();
          resetTableMinheight(1);
          setTimeout(() => {
            computeRect();
          });
        });
      },
    );

    watch(
      () => [tableDataSize.value],
      () => {
        // 如果是初始请求，执行默认赋值操作
        if (pageIndex.value === 1) {
          columns.value = loadTableColumns();
          loadTableData(() => {
            updateSizes();
          });
        }
      },
    );

    watch(
      () => [tableLineIsWrap.value, formatJson.value, isLimitExpandView.value],
      () => {
        pageIndex.value = 1;
        rowUpdateCounter.value++;
      },
    );

    const handleColumnWidthChange = (w, col) => {
      const width = w > 4 ? w : 40;
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

      col.width = width;
      store.dispatch('userFieldConfigChange', {
        fieldsWidth: newFieldsWidthObj,
      });
    };

    const isRequesting = ref(false);
    let delay = 100;
    let delayLoadingTimer;
    const debounceSetLoading = () => {
      delayLoadingTimer && clearTimeout(delayLoadingTimer);
      delayLoadingTimer = setTimeout(() => {
        isRequesting.value = false;
      }, delay);
    };

    const loadMoreTableData = () => {
      if (isRequesting.value) {
        return;
      }
      if (totalCount.value > tableData.value.length) {
        isRequesting.value = true;
        delay = 300;
        // 如果是前端已经请求缓存，这里直接启用缓存数据
        if (pageIndex.value * pageSize < tableDataSize.value) {
          pageIndex.value = pageIndex.value + 1;
          return;
        }

        delay = 120;
        return store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then(({ length }) => {
            visibleIndexs.value.endIndex = visibleIndexs.value.endIndex + (length ?? bufferCount);
            pageIndex.value = pageIndex.value + 1;
          })
          .catch(() => {
            debounceSetLoading();
          });
      }

      return Promise.resolve(false);
    };

    const getVisibleRows = (scrollTop, visibleHeight) => {
      const rows = tableData.value;
      let startIdx = 0;
      let endIdx = rows.length - 1;

      // 使用二分查找找到第一个可见的行
      while (startIdx < endIdx) {
        let midIdx = Math.floor((startIdx + endIdx) / 2);
        if (sizes.value[midIdx].accumulator < scrollTop) {
          startIdx = midIdx + 1;
        } else {
          endIdx = midIdx;
        }
      }

      let lastVisibleRow = startIdx;

      // 找到最后一个可见的行
      while (lastVisibleRow < rows.length && sizes.value[lastVisibleRow].accumulator < scrollTop + visibleHeight) {
        lastVisibleRow++;
      }

      return [startIdx, lastVisibleRow];
    };

    let $endIndex = 0;
    let $startIndex = 0;

    const updateVisibleItems = (event, scrollTop, offsetTop) => {
      if (!event?.target) {
        return;
      }

      const visibleTop = offsetTop - searchContainerHeight.value;
      const useScrollHeight = scrollTop > visibleTop ? scrollTop - visibleTop : 0;

      const visibleHeight = (event.target as HTMLElement).offsetHeight;

      const [startIndex, endIndex] = getVisibleRows(useScrollHeight, visibleHeight);

      visibleIndexs.value.startIndex = startIndex;
      visibleIndexs.value.endIndex = endIndex;
      rowsOffsetTop.value = useScrollHeight;
      const continuous = startIndex <= $endIndex && endIndex >= $startIndex;

      $startIndex = startIndex;
      $endIndex = endIndex;

      return {
        continuous,
      };
    };

    let refreshTimout;
    const handleScrollEvent = (event: MouseEvent, scrollTop, offsetTop) => {
      if (isRequesting.value) {
        return;
      }

      clearTimeout(refreshTimout);
      refreshTimout = setTimeout(() => {
        updateVisibleItems(event, scrollTop, offsetTop);
      }, 100);
    };

    useResizeObserve(SECTION_SEARCH_INPUT, entry => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    onMounted(() => {
      visibleIndexs.value.startIndex = 0;
      visibleIndexs.value.endIndex = bufferCount;
    });

    onBeforeUnmount(() => {
      tableRowStore.clear();
    });

    const scrollXOffsetLeft = ref(0);
    const refScrollXBar = ref();

    // 监听滚动条滚动位置
    // 判定是否需要拉取更多数据
    const { scrollToTop, hasScrollX, offsetWidth, scrollWidth, computeRect } = useLazyRender({
      loadMoreFn: loadMoreTableData,
      scrollCallbackFn: handleScrollEvent,
      container: resultContainerIdSelector,
      rootElement: refRootElement,
    });

    useWheel({
      target: refRootElement,
      callback: (event: WheelEvent) => {
        const maxOffset = scrollWidth.value - offsetWidth.value;
        if (event.deltaX !== 0 && hasScrollX.value) {
          event.stopPropagation();
          event.stopImmediatePropagation();
          event.preventDefault();

          const nextOffset = scrollXOffsetLeft.value + event.deltaX;
          if (nextOffset <= maxOffset && nextOffset >= 0) {
            scrollXOffsetLeft.value += event.deltaX;
            refScrollXBar.value?.scrollLeft(nextOffset);
          }
        }
      },
    });

    const operatorFixRightWidth = computed(() => {
      const operatorWidth = operatorToolsWidth.value;
      const diff = scrollWidth.value - scrollXOffsetLeft.value - offsetWidth.value;
      return diff > operatorWidth ? 0 : operatorWidth - diff;
    });

    const scrollXTransformStyle = computed(() => {
      return {
        '--scroll-left': `-${scrollXOffsetLeft.value}px`,
        '--padding-right': `${operatorToolsWidth.value}px`,
        '--fix-right-width': `${operatorFixRightWidth.value}px`,
      };
    });

    const headStyle = computed(() => {
      return {
        top: `${searchContainerHeight.value}px`,
        transform: `translateX(-${scrollXOffsetLeft.value}px)`,
      };
    });

    const showHeader = computed(() => {
      return props.contentType === 'table' && tableData.value.length > 0;
    });

    const viewList = computed(() => {
      const startIndex = visibleIndexs.value.startIndex - bufferCount;
      const endIndex = visibleIndexs.value.endIndex + bufferCount;
      const totalCount = tableData.value.length;
      const startIdx = startIndex >= 0 ? startIndex : 0;
      const endIdx = endIndex <= totalCount ? endIndex : totalCount;
      const result = new Array(endIdx - startIdx).fill('').map((_, index) => index + startIdx);
      return result;
    });

    const renderHeadVNode = () => {
      if (showHeader.value) {
        return (
          <div
            style={headStyle.value}
            class={['bklog-row-container row-header', { 'has-overflow-x': hasScrollX.value }]}
          >
            <div class='bklog-list-row'>
              {renderColumns.value.map(column => (
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
      }
      return null;
    };

    const scrollTop = () => {
      scrollToTop(visibleIndexs.value.endIndex < 100);
      visibleIndexs.value.startIndex = 0;
      visibleIndexs.value.endIndex = bufferCount * 2;
    };

    const renderScrollTop = () => {
      if (rowsOffsetTop.value > 300) {
        return (
          <span
            class='btn-scroll-top'
            v-bk-tooltips={$t('返回顶部')}
            onClick={() => scrollTop()}
          >
            <i class='bklog-icon bklog-zhankai'></i>
          </span>
        );
      }

      return null;
    };

    const renderRowCells = (row, rowIndex) => {
      const { expand } = row[ROW_CONFIG];
      return [
        <div class='bklog-list-row'>
          {renderColumns.value.map(column => (
            <LogCell
              key={`${rowIndex}-${column.key}`}
              width={column.width}
              class={[column.class ?? '', 'bklog-row-cell', column.fixed]}
              minWidth={column.minWidth ?? 'auto'}
            >
              {column.renderBodyCell?.({ row, column, rowIndex }, h) ?? column.title}
            </LogCell>
          ))}
          {hasScrollX.value ? null : (
            <LogCell
              width={operatorToolsWidth.value}
              class='hidden-field bklog-row-cell'
              minWidth={operatorToolsWidth.value ?? 'auto'}
            ></LogCell>
          )}
        </div>,
        expand ? expandOption.render({ row }) : '',
      ];
    };

    const renderRowVNode = () => {
      return viewList.value.map(rowIndex => {
        const row = tableData.value[rowIndex];
        const rowView = sizes.value[rowIndex];
        const rowStyle = {
          minHeight: `${row[ROW_CONFIG].minHeight}px`,
          transform: `translate3d(0, ${rowView.accumulator}px, 0)`,
          '--row-min-height': `${row[ROW_CONFIG].rowMinHeight - 2}px`,
        };

        return (
          <RowRender
            style={rowStyle}
            class={[
              'bklog-row-container',
              {
                'has-overflow-x': hasScrollX.value,
              },
            ]}
            row-index={rowIndex}
          >
            {renderRowCells(row, rowIndex)}
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

    const tableStyle = computed(() => {
      return {
        transform: `translateX(-${scrollXOffsetLeft.value}px)`,
        minHeight: `${totalSize.value}px`,
      };
    });

    const renderLoader = () => {
      return (
        <div class={['bklog-requsting-loading', { 'is-loading': isRequesting.value }]}>
          <div
            style={{ width: `${offsetWidth.value}px` }}
            v-bkloading={{ isLoading: isRequesting.value, opacity: 0.1 }}
          >
            {hasMoreList.value || tableData.value.length === 0 ? '' : `已加载所有数据`}
          </div>
        </div>
      );
    };

    const renderFixRightShadow = () => {
      return <div class='fixed-right-shadown'></div>;
    };

    const renderResultContainer = () => {
      if (tableData.value.length) {
        return [
          renderHeadVNode(),
          <div
            id={resultContainerId.value}
            ref={refBoxElement}
            style={tableStyle.value}
            class={['bklog-row-box', { 'show-head': showHeader.value }]}
          >
            {renderRowVNode()}
          </div>,
          renderFixRightShadow(),
          renderScrollTop(),
          renderScrollXBar(),
          renderLoader(),
          <div class='resize-guide-line'></div>,
        ];
      }

      return (
        <bk-exception
          style='margin-top: 100px;'
          class='exception-wrap-item exception-part'
          scene='part'
          type='search-empty'
        ></bk-exception>
      );
    };

    return {
      refRootElement,
      isLoading,
      isRequesting,
      renderResultContainer,
      scrollXTransformStyle,
    };
  },
  render() {
    return (
      <div
        ref='refRootElement'
        style={this.scrollXTransformStyle}
        class='bklog-result-container'
        v-bkloading={{ isLoading: this.isLoading && !this.isRequesting, opacity: 0.1 }}
      >
        {this.renderResultContainer()}
      </div>
    );
  },
});