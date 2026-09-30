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
import {
  type PropType,
  computed,
  defineComponent,
  getCurrentInstance,
  nextTick,
  onMounted,
  toRef,
  useTemplateRef,
} from 'vue';

import {
  type BkUiSettings,
  type FilterValue,
  type TableSort,
  type TdBaseTableProps,
  PrimaryTable,
} from '@blueking/tdesign-ui';
import { Exception, Pagination } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import TableSkeleton from '../../../../../../components/skeleton/table-skeleton';
import { useTableEllipsis } from '../../../../../../hooks/use-table-popover';
import { useTableCell } from '../../../../../trace-explore/components/trace-explore-table/hooks/use-table-cell';
import {
  type ColumnResizeContext,
  type TableEmpty,
  type TablePagination,
  type TableRenderer,
  COMMON_TABLE_ELLIPSIS_CLASS_NAME,
} from '../../../../typings';
import { DEFAULT_TABLE_CONFIG } from './table-constants';

import type {
  BaseTableColumn,
  EllipsisPosition,
  TableCellRenderer,
} from '../../../../../trace-explore/components/trace-explore-table/typing';
import type { CheckboxGroupValue, SelectOptions, SizeEnum, SlotReturnValue, TdAffixProps } from 'tdesign-vue-next';

import './common-table.scss';

export default defineComponent({
  name: 'CommonTable',
  props: {
    /** 表格行数据唯一值 key 名 */
    rowKey: {
      type: String,
      default: 'id',
    },
    /** 在根元素容器高度仍有剩余的情况下，表格是否自适应填满根元素容器的剩余空间 */
    autoFillSpace: {
      type: Boolean,
      default: false,
    },
    /** 表格列配置 */
    columns: {
      type: Array as PropType<BaseTableColumn[]>,
      default: () => [],
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<Record<string, unknown>[]>,
      default: () => [],
    },
    /** 表格行高主题 */
    tableSize: {
      type: String as PropType<SizeEnum>,
      default: 'small',
    },
    /** 表格设置属性类型 */
    tableSettings: {
      type: Object as PropType<BkUiSettings>,
    },
    /** 表格排序信息,字符串格式，以id为例：倒序 => -id；正序 => id；*/
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
    /** 表格分页属性类型 */
    pagination: {
      type: Object as PropType<TablePagination>,
    },
    /** 选中行 keys */
    selectedRowKeys: {
      type: Array as PropType<(number | string)[]>,
    },
    /** 表格加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 按真实列布局渲染首屏骨架；已有数据时保留表格并显示刷新状态。 */
    loadingCell: {
      type: Function as PropType<(column: BaseTableColumn, rowIndex: number) => SlotReturnValue>,
    },
    /** 表格空数据展示 */
    empty: {
      type: [Object, Function] as PropType<TableEmpty>,
    },
    /** 表头吸顶。使用该功能，需要非常注意表格是相对于哪一个父元素进行滚动 */
    headerAffixedTop: {
      type: [Boolean, Object] as PropType<boolean | TdAffixProps>,
    },
    /** 滚动条吸底 */
    horizontalScrollAffixedBottom: {
      type: [Boolean, Object] as PropType<boolean | TdAffixProps>,
    },
    /** 首行内容，横跨所有列。 */
    firstFullRow: {
      type: Function as PropType<TableRenderer>,
    },
    /** 表格尾行内容，横跨所有列。 */
    lastFullRow: {
      type: Function as PropType<TableRenderer>,
    },
    /** 表格单元格自定义渲染集合 key => customerRenderType,  value => TableCellRenderer */
    customCellRenderMap: {
      type: Object as PropType<Record<string, TableCellRenderer>>,
    },
    /** 表格单元格默认取值逻辑（列自身配置了 getRenderValue 时，以列配置为准） */
    customDefaultGetRenderValue: {
      type: Function as PropType<(row: Record<string, unknown>, column: BaseTableColumn) => unknown>,
    },
    /** 表格单元格溢出省略号位置全局默认值（end: 末尾省略；start: 开头省略。优先级低于列配置 ellipsisPosition） */
    ellipsisPosition: {
      type: String as PropType<EllipsisPosition>,
    },
    /** 行高亮类型：single 高亮一行、multiple 高亮多行，'' 关闭（官方类型未声明，运行时默认值） */
    activeRowType: {
      type: String as PropType<'' | TdBaseTableProps['activeRowType']>,
      default: 'single',
    },
    /**
     * 受控高亮行 keys（与 PrimaryTable activeRowKeys 语义一致）：父级传了该 prop 即受控（以 vnode.props 是否携带 key 判定，
     * 显式传 undefined 同样算受控，调用方需保证值为数组），行点击 / 键盘高亮只触发 activeChange 事件，由调用方决定是否更新
     */
    activeRowKeys: {
      type: Array as PropType<(number | string)[]>,
      default: undefined,
    },
    /** 非受控高亮行 keys（与 PrimaryTable defaultActiveRowKeys 语义一致）：仅初始化时读取，后续变化不生效 */
    defaultActiveRowKeys: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /** 表头筛选受控值（与 PrimaryTable filterValue 一致） */
    filterValue: {
      type: Object as PropType<FilterValue>,
    },
    /** 行类名，参数为 { row, rowIndex, type } */
    rowClassName: {
      type: [String, Function] as PropType<TdBaseTableProps['rowClassName']>,
    },
    /** 表格滚动配置，可用于开启虚拟滚动 */
    scroll: {
      type: Object as PropType<{
        bufferSize?: number;
        isFixedRowHeight?: boolean;
        rowHeight?: number;
        threshold?: number;
        type: 'lazy' | 'virtual';
      }>,
    },
    /** 表格最大高度，超出后出现滚动条 */
    maxHeight: {
      type: [String, Number] as PropType<number | string>,
    },
    /** 是否显示表格边框 */
    bordered: {
      type: Boolean,
      default: false,
    },
    /** 是否允许拖拽调整列宽 */
    resizable: {
      type: Boolean,
      default: true,
    },
    /** 刷新 key，值变化时强制重新渲染 PrimaryTable */
    refreshKey: {
      type: [Number, String] as PropType<number | string>,
      default: '',
    },
  },
  emits: {
    /** 当前页变化回调 */
    currentPageChange: (currentPage: number) => typeof currentPage === 'number',
    /** 每页条数变化回调 */
    pageSizeChange: (pageSize: number) => typeof pageSize === 'number',
    /** 排序变化回调 */
    sortChange: (sort: string | string[]) => typeof sort === 'string' || Array.isArray(sort),
    /** 显示列配置变化回调 */
    displayColFieldsChange: (displayColFields: string[]) => Array.isArray(displayColFields),
    /** 行选择变化回调 */
    selectChange: (selectedRowKeys: (number | string)[], options: SelectOptions<unknown>) =>
      Array.isArray(selectedRowKeys) && options,
    filterChange: (filterValue: FilterValue) => filterValue != null,
    /** 高亮行变化回调（透传 PrimaryTable onActiveChange，参数语义一致） */
    activeChange: (rowKeys: Array<number | string>, _context?: unknown) => Array.isArray(rowKeys),
    /** 列宽拖拽变化回调 */
    columnResizeChange: (context: ColumnResizeContext) => context && typeof context.columnsWidth === 'object',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /**
     * activeRowKeys 是否受控：与 TDesign useDefaultValue 的判定一致，以父级 vnode.props 是否携带该 key 为准
     * （prop 默认值 undefined 使 props 值无法区分「未传」与「显式传 undefined」，显式传 undefined 按 TDesign 语义同样算受控）。
     * 与 TDesign 相同，该判定在挂载时确定，不支持运行期切换受控 / 非受控模式。
     */
    const vProps = getCurrentInstance().vnode.props || {};
    const isControlledActiveRowKeys =
      Object.hasOwn(vProps, 'activeRowKeys') || Object.hasOwn(vProps, 'active-row-keys');
    const wrapperRef = useTemplateRef<HTMLElement>('wrapperRef');
    /** 表格单元格渲染逻辑 */
    const { tableCellRender, renderContext } = useTableCell({
      rowKeyField: toRef(props, 'rowKey'),
      customCellRenderMap: props.customCellRenderMap,
      customDefaultGetRenderValue: props.customDefaultGetRenderValue,
      cellEllipsisClass: COMMON_TABLE_ELLIPSIS_CLASS_NAME,
      ellipsisPosition: toRef(props, 'ellipsisPosition'),
    });
    /** 表格功能单元格内容溢出弹出 popover 功能（绑定到包裹层，避免表格重建时事件委托丢失） */
    const { initListeners: initEllipsisListeners } = useTableEllipsis(wrapperRef, {
      trigger: {
        selector: `.${COMMON_TABLE_ELLIPSIS_CLASS_NAME}`,
      },
    });
    const showLoadingRows = computed(() => !!props.loadingCell && props.loading);
    const displayedData = computed(() =>
      showLoadingRows.value && !props.data.length
        ? Array.from({ length: 8 }, (_, index) => ({ [props.rowKey]: `loading-${index}` }))
        : props.data
    );
    /** 处理后的表格列配置 */
    const tableColumns = computed(() =>
      props.columns.map(column => ({
        // @ts-expect-error cellEllipsis 不在 BaseTableColumn 类型中，但 TDesign 运行时支持
        cellEllipsis: column?.ellipsis != null ? column?.ellipsis : true,
        ellipsis: false,
        // @ts-expect-error ellipsisTitle 不在 BaseTableColumn 类型中，但 TDesign 运行时支持
        ellipsisTitle: column?.ellipsisTitle != null ? column?.ellipsisTitle : true,
        ...column,
        ...(showLoadingRows.value ? { type: undefined, ellipsis: false } : {}),
        cell: (_, cellParams) =>
          showLoadingRows.value
            ? props.loadingCell(column, cellParams.rowIndex)
            : column?.cellRenderer
              ? column?.cellRenderer(cellParams.row, column, { ...renderContext, runtime: cellParams })
              : tableCellRender(cellParams.row, column, { ...renderContext, runtime: cellParams }),
      }))
    );
    /** 表格骨架屏展示相关配置 */
    const tableSkeletonConfig = computed(() => {
      if (!props.loading || props.loadingCell) return null;
      const config = {
        tableClass: 'common-table-hidden-body',
        skeletonClass: 'common-skeleton-show-body',
      };
      return config;
    });
    /** 是否展示分页器 */
    const showPagination = computed(() => props.pagination?.total && props.data?.length);
    /** 表格排序，将字符串形式转换成 TableSort 形式 */
    const tableSort = computed(() => {
      // 统一处理为数组形式
      const sortRules = Array.isArray(props.sort) ? props.sort : [props.sort];
      const parsedSorts = [];

      for (const rule of sortRules) {
        if (!rule) continue;

        // 解析排序规则字符串
        const isDescending = rule.startsWith('-');
        const sortField = isDescending ? rule.slice(1) : rule;

        if (sortField) {
          parsedSorts.push({
            sortBy: sortField,
            descending: isDescending,
          });
        }
      }

      return parsedSorts;
    });

    /**
     * @description 表格排序变化后回调
     * @param {TableSort} sort
     * @returns {void}
     */
    const handleSortChange = (sortEvent: TableSort) => {
      if (Array.isArray(sortEvent)) {
        // 处理数组形式的排序
        const sortStrings = sortEvent
          .filter(item => item?.sortBy)
          .map(item => `${item.descending ? '-' : ''}${item.sortBy}`);
        emit('sortChange', sortStrings.length === 1 ? sortStrings[0] : sortStrings);
        return;
      }

      let sort = '';
      if (sortEvent?.sortBy) {
        sort = `${sortEvent.descending ? '-' : ''}${sortEvent.sortBy}`;
      }
      emit('sortChange', sort);
    };

    /**
     * @description 表格当前页码变化时的回调
     * @param {number} page 当前页码
     * @returns {void}
     */
    const handleCurrentPageChange = (page: number) => {
      emit('currentPageChange', page);
    };

    /**
     * @description 选中行发生变化时触发
     * @param selectedRowKeys 选中行 keys
     * @param options.type uncheck: 当前行操作为「取消行选中」; check: 当前行操作为「行选中」
     * @param options.currentRowKey 当前操作行的 rowKey 值
     * @param options.currentRowData 当前操作行的 行数据
     * @returns {void}
     */
    const handleSelectChange = (selectedRowKeys: (number | string)[], options: SelectOptions<unknown>) => {
      emit('selectChange', selectedRowKeys, options);
    };

    /**
     * @description 表格每页条数变化时的回调
     * @param {number} size 每页条数
     * @returns {void}
     */
    const handlePageSizeChange = (size: number) => {
      emit('pageSizeChange', size);
    };

    /**
     * @description 表格列展示配置变化时的回调
     * @param {CheckboxGroupValue} displayColFields 可展示的列字段
     * @returns {void}
     */
    const handleDisplayColFieldsChange = (displayColFields: CheckboxGroupValue) => {
      emit('displayColFieldsChange', displayColFields as string[]);
    };

    /**
     * @description 表头筛选变化
     * @param {FilterValue} value
     */
    const handleFilterChange = (value: FilterValue) => {
      emit('filterChange', value);
    };
    /**
     * @description 表格高亮行变化回调：不写内部状态，原样透传 PrimaryTable onActiveChange 的参数，
     *              受控 / 非受控的状态归集由调用方自行处理
     * @param {Array<string | number>} rowKeys 高亮行 keys
     * @param {unknown} context 高亮上下文（activeRowList / currentRowData / type）
     */
    const handleActiveChange = (rowKeys: Array<number | string>, context?: unknown) => {
      emit('activeChange', rowKeys, context);
    };
    /**
     * @description 表格列宽拖拽变化时的回调
     * @param {ColumnResizeContext} context 包含列宽映射的上下文对象
     * @returns {void}
     */
    const handleColumnResizeChange = (context: ColumnResizeContext) => {
      emit('columnResizeChange', context);
    };

    /**
     * @description 表格最后一行渲染方法(默认填充一个 div 占位)
     * @returns {SlotReturnValue} 表格最后一行dom内容
     */
    const tableLastFullRowRender = (): SlotReturnValue => {
      if (!props.lastFullRow) {
        return (<div />) as unknown as SlotReturnValue;
      }
      return props.lastFullRow();
    };

    /**
     * @description 表格空数据渲染方法
     * @returns {SlotReturnValue} 表格空数据dom内容
     */
    const tableEmptyRender = (): SlotReturnValue => {
      if (typeof props.empty === 'function') {
        return props.empty();
      }
      return (
        <Exception
          class='common-table-empty'
          description={props.empty?.emptyText || t('搜索为空')}
          scene='part'
          type={props.empty?.type || 'search-empty'}
        />
      ) as unknown as SlotReturnValue;
    };

    /** 初始化表格省略号事件监听器（绑定到包裹层，表格重建时无需重新初始化） */
    onMounted(() => {
      nextTick(() => initEllipsisListeners());
    });

    return {
      tableColumns,
      displayedData,
      showLoadingRows,
      tableSort,
      showPagination,
      tableSkeletonConfig,
      isControlledActiveRowKeys,
      tableCellRender,
      handleSortChange,
      handleCurrentPageChange,
      handleSelectChange,
      handlePageSizeChange,
      handleDisplayColFieldsChange,
      handleColumnResizeChange,
      tableLastFullRowRender,
      tableEmptyRender,
      handleFilterChange,
      handleActiveChange,
    };
  },
  render() {
    return (
      <div
        class={[
          'common-table-wrapper',
          {
            'fill-remaining-space': this.autoFillSpace && (!this.showLoadingRows || !!this.data.length),
            'is-loading-rows': this.showLoadingRows,
          },
        ]}
        aria-busy={this.loading}
      >
        {/* 事件委托包裹层：避免 PrimaryTable 销毁重建时事件委托丢失 */}
        <div
          ref='wrapperRef'
          class='common-table-event-root'
          inert={this.loadingCell && this.loading ? true : undefined}
        >
          <PrimaryTable
            key={this.refreshKey}
            ref='tableRef'
            class={`common-table ${this.tableSkeletonConfig?.tableClass}`}
            v-slots={{
              empty: this.tableEmptyRender,
            }}
            /**
             * 受控高亮行透传：仅父级传了 activeRowKeys（含显式 undefined，判定见 setup）才把 key 透传给 PrimaryTable，
             * 与 TDesign 受控判定保持一致；非受控时携带该 key 会被 PrimaryTable 误判为受控，故用条件展开。
             * 受控时骨架态强制清空（骨架行为假数据 key，真实高亮 key 本就不会命中，此处仅与历史行为保持一致）
             */
            {...(this.isControlledActiveRowKeys
              ? { activeRowKeys: this.showLoadingRows ? [] : this.activeRowKeys }
              : {})}
            activeRowType={this.activeRowType || undefined}
            bkUiSettings={this.tableSettings}
            bordered={this.bordered}
            columns={this.tableColumns}
            data={this.displayedData}
            defaultActiveRowKeys={this.defaultActiveRowKeys}
            disableDataPage={true}
            filterValue={this.filterValue}
            firstFullRow={this.showLoadingRows ? null : this.firstFullRow}
            headerAffixedTop={this.headerAffixedTop}
            horizontalScrollAffixedBottom={this.horizontalScrollAffixedBottom}
            hover={true}
            lastFullRow={!this.showLoadingRows && this.data?.length ? this.tableLastFullRowRender : null}
            maxHeight={this.maxHeight}
            needCustomScroll={false}
            reserveSelectedRowOnPaginate={false}
            resizable={this.resizable}
            rowClassName={this.showLoadingRows ? 'alarm-loading-row' : this.rowClassName}
            rowKey={this.rowKey}
            scroll={this.scroll}
            selectedRowKeys={this.showLoadingRows ? [] : this.selectedRowKeys}
            showSortColumnBgColor={true}
            size={this.tableSize}
            sort={this.tableSort}
            tableLayout='fixed'
            onActiveChange={this.handleActiveChange}
            onColumnResizeChange={this.handleColumnResizeChange}
            onDisplayColumnsChange={this.handleDisplayColFieldsChange}
            onFilterChange={this.handleFilterChange}
            onSelectChange={this.handleSelectChange}
            onSortChange={this.handleSortChange}
          />
        </div>
        {!this.loadingCell && (
          <TableSkeleton class={`common-table-skeleton ${this.tableSkeletonConfig?.skeletonClass}`} />
        )}

        {this.showPagination ? (
          <Pagination
            align={'right'}
            count={this.pagination?.total}
            layout={['total', 'limit', 'list']}
            limit={this.pagination?.pageSize || DEFAULT_TABLE_CONFIG.pagination.pageSize}
            location={'right'}
            modelValue={this.pagination?.currentPage || DEFAULT_TABLE_CONFIG.pagination.currentPage}
            small={true}
            onChange={this.handleCurrentPageChange}
            onLimitChange={this.handlePageSizeChange}
          />
        ) : null}
      </div>
    );
  },
});
