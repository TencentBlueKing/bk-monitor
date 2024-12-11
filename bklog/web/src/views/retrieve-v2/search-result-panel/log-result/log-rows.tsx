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
import { computed, defineComponent, ref, watch, h, onMounted, onUnmounted, Ref } from 'vue';

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

    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const formatJson = computed(() => store.state.tableJsonFormat);
    const tableShowRowIndex = computed(() => store.state.tableShowRowIndex);
    const isLimitExpandView = computed(() => store.state.isLimitExpandView);
    const tableLineIsWrap = computed(() => store.state.tableLineIsWrap);
    const fieldRequestCounter = computed(() => indexFieldInfo.value.request_counter);
    const listRequestCounter = computed(() => indexSetQueryResult.value.request_counter);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading);
    const kvShowFieldsList = computed(() => Object.keys(indexSetQueryResult.value?.fields ?? {}) || []);
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
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
    const operatorToolsWidth = computed(() => {
      return indexSetOperatorConfig.value?.bcsWebConsole?.is_active ? 84 : 58;
    });

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
            const config: Ref<RowConfig> = row[ROW_CONFIG];

            const hanldeExpandClick = () => {
              config.value.expand = !config.value.expand;
              tableRowStore.get(row[ROW_KEY]).expand = config.value.expand;
            };

            return (
              <span
                class={['bklog-expand-icon', { 'is-expaned': config.value.expand }]}
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
          tableRowStore.delete(key);
        }
      });
    };

    /**
     * 当切换操作时，重新计算行高
     * 原则上，此时滚动到最上方，可视区域开始的Index为0
     */
    const resetTableMinheight = () => {
      const endIndex = visibleIndexs.value.endIndex;
      clearRowConfigCache(endIndex - 1);
      const startIndex = endIndex - 1;
      for (let i = startIndex; i < tableData.value.length; i++) {
        if (tableData.value[ROW_CONFIG]?.minHeight) {
          tableData.value[ROW_CONFIG].minHeight = 40;
        }
      }
    };

    const loadTableData = () => {
      clearRowConfigCache(tableData.value.length);
      return (indexSetQueryResult.value.list || []).map((row, index) => {
        const rowKey = `${ROW_KEY}_${index}`;

        Object.assign(row, {
          [ROW_KEY]: rowKey,
          [ROW_INDEX]: index,
          [ROW_CONFIG]: ref(getRowConfigWithCache(index)),
        });
        return row;
      });
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
      () => [fieldRequestCounter.value, props.contentType],
      () => {
        columns.value = loadTableColumns();
        setTimeout(() => {
          computeRect();
        });
      },
    );

    watch(
      () => [listRequestCounter.value],
      () => {
        tableData.value = loadTableData();
      },
    );

    watch(
      () => [tableLineIsWrap.value, formatJson.value, isLimitExpandView.value],
      () => {
        setTimeout(() => {
          resetTableMinheight();
        });
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
    const debounceSetLoading = debounce(() => {
      isRequesting.value = false;
    }, 300);

    const loadMoreTableData = () => {
      if (totalCount.value > tableData.value.length) {
        isRequesting.value = true;
        return store
          .dispatch('requestIndexSetQuery', { isPagination: true })
          .then(() => {
            visibleIndexs.value.endIndex = visibleIndexs.value.endIndex + bufferCount;
            debounceSetLoading();
            return true;
          })
          .finally(() => {
            debounceSetLoading();
            return true;
          });
      }

      return Promise.resolve(false);
    };

    // 滚动不满一行数据时，第一行数据的偏移量
    const scrollRowOffsetHeight = ref(0);
    const handleScrollEvent = (event: MouseEvent, scrollTop, offsetTop) => {
      if (isRequesting.value) {
        return;
      }

      const visibleTop = offsetTop - searchContainerHeight.value;
      const useScrollHeight = scrollTop > visibleTop ? scrollTop - visibleTop : 0;

      let startPosition = 0;
      let startIndex = 0;

      while (startPosition < useScrollHeight) {
        const nextItem = tableData.value[startIndex];
        if (nextItem) {
          const lastHeight = startPosition + nextItem[ROW_CONFIG].value.minHeight;
          if (lastHeight <= useScrollHeight) {
            startPosition = lastHeight;
            startIndex = startIndex + 1;
          } else {
            break;
          }
        }

        if (!nextItem) {
          break;
        }
      }

      const containerHeihgt = (event.target as HTMLElement).clientHeight;
      let endIndex = startIndex + bufferCount;
      const visibleHeight = tableData.value.slice(startIndex, endIndex).reduce((acc, row) => {
        return acc + row[ROW_CONFIG].value.minHeight;
      }, 0);

      if (visibleHeight < containerHeihgt) {
        endIndex = endIndex + bufferCount / 2;
      }

      scrollRowOffsetHeight.value = useScrollHeight - startPosition;
      visibleIndexs.value.startIndex = startIndex > bufferCount ? startIndex - bufferCount : 0;
      visibleIndexs.value.endIndex = endIndex;
      rowsOffsetTop.value = useScrollHeight;
    };

    useResizeObserve(SECTION_SEARCH_INPUT, entry => {
      searchContainerHeight.value = entry.contentRect.height;
    });

    onMounted(() => {
      visibleIndexs.value.startIndex = 0;
      visibleIndexs.value.endIndex = bufferCount;
    });

    onUnmounted(() => {
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
        if (event.deltaX !== 0 && hasScrollX.value) {
          scrollXOffsetLeft.value += event.deltaX;
          refScrollXBar.value?.scrollLeft(scrollXOffsetLeft.value);
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
      const { expand } = row[ROW_CONFIG].value;
      return [
        <div class='bklog-list-row'>
          {renderColumns.value.map(column => (
            <LogCell
              key={column.key}
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

    const handleRowResize = (entry, row) => {
      const config: RowConfig = row[ROW_CONFIG].value;
      config.minHeight = entry.contentRect.height;
      Object.assign(tableRowStore.get(row[ROW_KEY]), config);
    };

    const renderRowVNode = () => {
      const { startIndex, endIndex } = visibleIndexs.value;
      return tableData.value.map(row => {
        const rowIndex = row[ROW_INDEX];

        const rowStyle = {
          minHeight: `${row[ROW_CONFIG].value.minHeight}px`,
          '--row-min-height': `${row[ROW_CONFIG].value.minHeight - 2}px`,
        };

        if (rowIndex >= startIndex && rowIndex < endIndex) {
          return (
            <RowRender
              key={row[ROW_KEY]}
              style={rowStyle}
              class={[
                'bklog-row-container',
                {
                  'has-overflow-x': hasScrollX.value,
                },
              ]}
              row-index={rowIndex}
              onRow-resize={entry => handleRowResize(entry, row)}
            >
              {renderRowCells(row, rowIndex)}
            </RowRender>
          );
        }

        return (
          <RowRender
            key={row[ROW_KEY]}
            style={rowStyle}
            class={[
              'bklog-row-container',
              'is-pending',
              {
                'has-overflow-x': hasScrollX.value,
              },
            ]}
            row-index={rowIndex}
          ></RowRender>
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
        transform: `translate3d(-${scrollXOffsetLeft.value}px, 0, 0)`,
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
