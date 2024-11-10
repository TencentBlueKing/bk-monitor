import { computed, defineComponent, ref, watch, h } from 'vue';
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';

import {
  parseTableRowData,
  formatDateNanos,
  formatDate,
  copyMessage,
  TABLE_LOG_FIELDS_SORT_REGULAR,
  setDefaultTableWidth,
} from '@/common/util';
import JsonFormatter from '@/global/json-formatter.vue';
import TableColumn from './table-column.vue';
import LogCell from './log-cell';
import OperatorTools from '../original-log/operator-tools.vue';
import useScrollLoading from './use-scroll-loading';
import LazyRender from '@/global/lazy-render.vue';
import ExpandView from '../original-log/expand-view.vue';
import useHeaderRender from './use-render-header';
import './log-rows.scss';
import { getConditionRouterParams } from '../panel-util';

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
    const offsetTop = ref(0);

    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetQueryResult = computed(() => store.state.indexSetQueryResult);
    const visibleFields = computed(() => store.state.visibleFields);
    const indexSetOperatorConfig = computed(() => store.state.indexSetOperatorConfig);
    const formatJson = computed(() => store.state.tableJsonFormat);
    const tableShowRowIndex = computed(() => store.state.tableShowRowIndex);

    const tableLineIsWrap = computed(() => store.state.tableLineIsWrap);
    const fieldRequestCounter = computed(() => indexFieldInfo.value.request_counter);
    const listRequestCounter = computed(() => indexSetQueryResult.value.request_counter);
    const unionIndexItemList = computed(() => store.getters.unionIndexItemList);
    const timeField = computed(() => indexFieldInfo.value.time_field);
    const timeFieldType = computed(() => indexFieldInfo.value.time_field_type);
    const isLoading = computed(() => indexSetQueryResult.value.is_loading);
    const kvShowFieldsList = computed(() => Object.keys(indexSetQueryResult.value?.fields ?? {}) || []);
    const userSettingConfig = computed(() => store.state.retrieve.catchFieldCustomConfig);
    const tableDataMap = new WeakMap();

    const renderColumns = computed(() => {
      return [
        {
          field: '',
          key: '__component_row_expand',
          // 设置需要显示展开图标的列
          type: 'expand',
          title: '',
          width: 50,
          align: 'center',
          resize: false,
          renderBodyCell: ({ row, rowIndex }, h) => {
            const config = row.__component_row_config;

            const hanldeExpandClick = () => {
              config.value.expand = !config.value.expand;
              tableDataMap.set(row, { expand: config.value.expand });
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
          key: '__component_row_index',
          title: tableShowRowIndex.value ? '#' : '',
          width: tableShowRowIndex.value ? 50 : 0,
          fixed: 'left',
          align: 'center',
          resize: false,
          class: tableShowRowIndex.value ? 'is-show' : 'is-hidden',
          renderBodyCell: ({ row, column, rowIndex }, h) => {
            return row.__component_row_index + 1;
          },
        },
        ...columns.value,
        {
          field: '__component_table_operator',
          key: '__component_table_operator',
          title: $t('操作'),
          width: 80,
          fixed: 'right',
          resize: false,
          renderBodyCell: ({ row, column, rowIndex }, h) => {
            return (
              //@ts-ignore
              <OperatorTools
                handle-click={event => props.handleClickTools(event, row, indexSetOperatorConfig.value)}
                index={row.__component_row_index}
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
              align: 'top',
              resize: true,
              renderBodyCell: ({ row, column, rowIndex }, h) => {
                return (
                  //@ts-ignore
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
              renderHeaderCell: ({ column }, h) => {
                const sortable = field.es_doc_values && field.tag !== 'union-source';
                return renderHead(field, order => {
                  if (sortable) {
                    const sortList = order ? [[field.field_name, order]] : [];
                    store.commit('updateIndexItemParams', {
                      sort_list: sortList,
                    });
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
          field: '__component_origin_time',
          key: '__component_origin_time',
          title: '__component_origin_time',
          align: 'top',
          resize: false,
          minWidth: timeFieldType.value === 'date_nanos' ? 250 : 200,
          renderBodyCell: ({ row, column, rowIndex }, h) => {
            return <span class='time-field'>{getOriginTimeShow(row[timeField.value])}</span>;
          },
        },
        {
          field: '__component_origin_content',
          key: '__component_origin_content',
          title: '__component_origin_content',
          align: 'top',
          minWidth: '100%',
          width: 'auto',
          resize: false,
          renderBodyCell: ({ row, column, rowIndex }, h) => {
            return (
              <JsonFormatter
                jsonValue={row}
                fields={visibleFields.value}
                formatJson={formatJson.value}
                class='bklog-column-wrapper'
                onMenu-click={({ option, isLink }) => handleMenuClick(option, isLink)}
              ></JsonFormatter>
            );
          },
        },
      ];
    };

    const loadTableData = () => {
      return (indexSetQueryResult.value.list || []).map((row, index) => {
        let isExpand = false;
        if (tableDataMap.has(row)) {
          isExpand = tableDataMap.get(row).expand;
        }

        tableDataMap.set(row, { expand: isExpand });
        Object.assign(row, {
          __component_row_key: `__component_row_key_${index}`,
          __component_row_index: index,
          __component_row_config: ref({ expand: isExpand }),
        });
        return row;
      });
    };

    const expandOption = {
      render: ({ row, column, rowIndex }, h) => {
        return (
          <ExpandView
            kv-show-fields-list={kvShowFieldsList.value}
            data={row}
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
      },
    );

    watch(
      () => [listRequestCounter.value],
      () => {
        tableData.value = loadTableData();
      },
    );

    const handleColumnWidthChange = (w, col) => {
      const width = w > 4 ? w : 40;
      const { fieldsWidth } = userSettingConfig.value;
      const newFieldsWidthObj = Object.assign(fieldsWidth, {
        [col.field_name]: Math.ceil(width),
      });

      col.width = width;
      store.dispatch('userFieldConfigChange', {
        fieldsWidth: newFieldsWidthObj,
      });
    };

    const renderHeadVNode = () => {
      if (props.contentType === 'table' && tableData.value.length > 0) {
        return (
          <LazyRender class='bklog-row-container'>
            <div class='bklog-list-row '>
              {renderColumns.value.map(column => (
                <LogCell
                  key={column.key}
                  width={column.width}
                  minWidth={column.minWidth ?? 'auto'}
                  class={[column.class ?? '', 'bklog-row-cell header-cell', column.fixed]}
                  resize={column.resize}
                  onResize-width={w => handleColumnWidthChange(w, column)}
                >
                  {column.renderHeaderCell?.({ column }, h) ?? column.title}
                </LogCell>
              ))}
            </div>
          </LazyRender>
        );
      }
      return null;
    };

    const { scrollToTop } = useScrollLoading(
      () => {
        return store.dispatch('requestIndexSetQuery', { isPagination: true });
      },
      top => {
        offsetTop.value = top;
      },
    );

    const renderScrollTop = () => {
      if (offsetTop.value > 300) {
        return (
          <span
            class='btn-scroll-top'
            onClick={() => scrollToTop()}
          >
            <i class='bklog-icon bklog-xiazai'></i> {$t('返回顶部')}
          </span>
        );
      }

      return null;
    };

    return { renderColumns, tableData, isLoading, expandOption, renderHeadVNode, renderScrollTop };
  },
  render(h) {
    return (
      <div
        class='bklog-result-container'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {this.renderHeadVNode()}
        {this.tableData.length === 0 ? (
          <bk-exception
            class='exception-wrap-item exception-part'
            type='search-empty'
            scene='part'
            style='margin-top: 100px;'
          ></bk-exception>
        ) : (
          ''
        )}
        {this.tableData.map((row, rowIndex) => {
          return (
            <LazyRender
              class='bklog-row-container'
              delay={1}
              key={row.__component_row_key}
              index={rowIndex}
            >
              <div
                class='bklog-list-row'
                key={row.__component_row_key}
              >
                {this.renderColumns.map(column => (
                  <LogCell
                    key={column.key}
                    width={column.width}
                    minWidth={column.minWidth ?? 'auto'}
                    class={[column.class ?? '', 'bklog-row-cell', column.fixed]}
                  >
                    {column.renderBodyCell?.({ row, column, rowIndex }, h) ?? column.title}
                  </LogCell>
                ))}
              </div>
              {row.__component_row_config.value.expand ? this.expandOption.render({ row, rowIndex }, h) : ''}
            </LazyRender>
          );
        })}
        {this.renderScrollTop()}
        <div class='resize-guide-line'></div>
      </div>
    );
  },
});
