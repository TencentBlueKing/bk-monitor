/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
  onBeforeUnmount,
  onMounted,
  reactive,
  shallowRef,
  toRef,
  useTemplateRef,
  watch,
} from 'vue';

import { type SortInfo, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { $bkPopover, Loading } from 'bkui-vue';

import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import ExploreFieldSetting from '../explore-field-setting/explore-field-setting';
import FieldTypeIcon from '../field-type-icon';
import StatisticsList from '../statistics-list';
import ExploreConditionMenu from './components/explore-condition-menu';
import ExploreTableEmpty from './components/explore-table-empty';
import {
  CAN_TABLE_SORT_FIELD_TYPES,
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
} from './constants';
import { useExploreColumnConfig } from './hooks/use-explore-column-config';
import { useExploreDataCache } from './hooks/use-explore-data-cache';
import { useTableCell } from './hooks/use-table-cell';
import { useTableEllipsis, useTableHeaderDescription, useTablePopover } from './hooks/use-table-popover';
import { type ActiveConditionMenuTarget, type ExploreTableColumn, ExploreTableLoadingEnum } from './typing';
import { isEllipsisActiveSingleLine } from './utils/dom-helper';

import type { ISpanListItem, ITraceListItem } from '../../../../typings';
import type { ConditionChangeEvent, ICommonParams, IDimensionField, IDimensionFieldTreeItem } from '../../typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './trace-explore-table.scss';

/** 默认滚动容器选择器 */
const DEFAULT_SCROLL_CONTAINER_SELECTOR = '.trace-explore-view';

export default defineComponent({
  name: 'TraceExploreTable',
  props: {
    /** 是否显示操作按钮 */
    showOperation: {
      type: Boolean,
      default: true,
    },
    /** 滚动容器选择器 */
    scrollContainerSelector: {
      type: String,
      default: DEFAULT_SCROLL_CONTAINER_SELECTOR,
    },
    /** 当前视角是否为 Span 视角 */
    mode: {
      type: String as PropType<'span' | 'trace'>,
    },
    /** 当前选中的应用 Name */
    appName: {
      type: String,
    },
    /** 接口请求配置参数 */
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    /** 需要显示渲染的列名数组 */
    displayFields: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 缓存的列宽配置 */
    fieldsWidthConfig: {
      type: Object as PropType<Record<string, number>>,
      default: () => ({}),
    },
    /** 表格所有列字段配置数组(接口原始结构) */
    sourceFieldConfigs: {
      type: Array as PropType<IDimensionField[]>,
      default: () => [],
    },
    /** 表格数据 */
    tableData: {
      type: Array as PropType<ISpanListItem[] | ITraceListItem[]>,
      default: () => [],
    },
    /** 判断当前数据是否需要触底加载更多 */
    tableHasScrollLoading: {
      type: Boolean,
      default: false,
    },
    /** table loading 配置 */
    tableLoading: {
      type: Object as PropType<{
        [ExploreTableLoadingEnum.BODY_SKELETON]: boolean;
        [ExploreTableLoadingEnum.HEADER_SKELETON]: boolean;
        [ExploreTableLoadingEnum.SCROLL]: boolean;
      }>,
      default: () => ({
        [ExploreTableLoadingEnum.BODY_SKELETON]: false,
        [ExploreTableLoadingEnum.HEADER_SKELETON]: false,
        [ExploreTableLoadingEnum.SCROLL]: false,
      }),
    },
    /** 表格列排序配置 */
    sortContainer: {
      type: Object as PropType<SortInfo>,
      default: () => ({
        sortBy: '',
        descending: null,
      }),
    },
    /** 支持排序的字段类型 */
    canSortFieldTypes: {
      type: [Set, Array] as PropType<Set<string> | string[]>,
      default: () => CAN_TABLE_SORT_FIELD_TYPES,
    },
    /** 是否启用点击弹出操作下拉菜单 */
    enabledClickMenu: {
      type: Boolean,
      default: true,
    },
    /** 是否启用可配置表格渲染列字段功能 */
    enabledDisplayFieldSetting: {
      type: Boolean,
      default: true,
    },
    /** 是否启用字段分析统计面板功能 */
    enableStatistics: {
      type: Boolean,
      default: true,
    },
    /** 是否显示列头图标 */
    showHeaderIcon: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    /** 筛选条件改变后触发的回调 */
    conditionChange: (conditionEvent: ConditionChangeEvent) => conditionEvent,
    /** 清除检索过滤 */
    clearRetrievalFilter: () => true,
    /** 显示列字段变化 */
    displayFieldChange: (displayFields: string[]) => Array.isArray(displayFields),
    /** 列宽变化 */
    columnResize: (context: { columnsWidth: { [colKey: string]: number } }) => !!context,
    /** 排序变化 */
    sortChange: (sortEvent: TableSort) => !!sortEvent,
    /** 触底加载更多 */
    scrollToEnd: () => true,
    /** 打开详情抽屉页展示状态(traceID | spanID 点击后回调) */
    sliderShow: (openMode: '' | 'span' | 'trace', activeId: string) => openMode && activeId,
  },
  setup(props, { emit }) {
    /** 滚动容器元素 */
    let scrollContainer: HTMLElement = null;
    /** 滚动结束后回调逻辑执行计时器  */
    let scrollPointerEventsTimer = null;
    /** 统计弹窗实例 */
    let statisticsPopoverInstance = null;

    const tableRef = useTemplateRef<InstanceType<typeof PrimaryTable>>('tableRef');
    const conditionMenuRef = useTemplateRef<InstanceType<typeof ExploreConditionMenu>>('conditionMenuRef');
    const statisticsListRef = useTemplateRef<InstanceType<typeof StatisticsList>>('statisticsListRef');

    /** 统计面板的 抽屉页展示状态 */
    let statisticsSliderShow = false;
    /** 字段分析弹窗 popover 显隐 */
    const showStatisticsPopover = shallowRef(false);
    /** 当前激活字段分析弹窗面板展示的字段 */
    const activeStatisticsField = shallowRef('');
    /** click弹出 conditionMenu popover组件所需参数 */
    const activeConditionMenuTarget = reactive({
      rowId: '',
      colId: '',
      conditionValue: '',
      /** 除公共菜单项外需要自定义菜单项列表 */
      customMenuList: [],
    });

    /** 表格行可用作 唯一主键值 的字段名 */
    const tableRowKeyField = computed(() => (props.mode === 'span' ? 'span_id' : 'trace_id'));

    /** 数据缓存 hook，用于表格单元格交互 */
    const { cacheRows, getCellComplexValue, clearCache } = useExploreDataCache(tableRowKeyField);

    /** 表格功能单元格内容溢出弹出 popover 功能 */
    const { initListeners: initEllipsisListeners, handlePopoverHide: ellipsisPopoverHide } = useTableEllipsis(
      tableRef,
      {
        trigger: {
          selector: `.${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`,
        },
      }
    );

    /** 表格功能单元格内容溢出弹出 popover 功能 */
    const { initListeners: initHeaderDescritionListeners, handlePopoverHide: descriptionPopoverHide } =
      useTableHeaderDescription(tableRef, {
        trigger: {
          selector: `.${ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME}`,
        },
      });

    const {
      initListeners: initConditionMenuListeners,
      handlePopoverShow: conditionMenuPopoverShow,
      handlePopoverHide: conditionMenuPopoverHide,
    } = useTablePopover(tableRef, {
      trigger: {
        selector: `.${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`,
        eventType: 'click',
        delay: 0,
      },
      getContentOptions: triggerDom => {
        const oldRowId = activeConditionMenuTarget.rowId;
        const oldColId = activeConditionMenuTarget.colId;
        setActiveConditionMenu();
        if (triggerDom.dataset.rowId === oldRowId && triggerDom.dataset.colId === oldColId) {
          return;
        }
        const sourceValue = getCellComplexValue(triggerDom.dataset.rowId, triggerDom.dataset.colId, {
          index: triggerDom.dataset.index ? Number(triggerDom.dataset.index) : null,
        });
        setActiveConditionMenu({
          rowId: triggerDom.dataset.rowId,
          colId: triggerDom.dataset.colId,
          conditionValue: Array.isArray(sourceValue) ? JSON.stringify(sourceValue) : String(sourceValue),
        });
        const { isEllipsisActive } = isEllipsisActiveSingleLine(triggerDom.parentElement);
        return {
          content: conditionMenuRef.value.$el,
          popoverTarget: isEllipsisActive ? triggerDom.parentElement : triggerDom,
        };
      },
      onHide: () => {
        setActiveConditionMenu();
      },
      popoverOptions: {
        theme: 'light padding-0',
        placement: 'bottom',
        interactive: true,
        duration: [50, null],
      },
    });

    const { tableCellRender, renderContext } = useTableCell({
      rowKeyField: tableRowKeyField,
      customDefaultGetRenderValue: (row, column) => {
        const alias = row?.[column.colKey];
        if (typeof alias !== 'object' || alias == null) {
          return alias;
        }
        return JSON.stringify(alias);
      },
    });
    const { tableColumns, tableDisplayColumns } = useExploreColumnConfig({
      appName: toRef(props, 'appName'),
      displayFields: toRef(props, 'displayFields'),
      fieldsWidthConfig: toRef(props, 'fieldsWidthConfig'),
      mode: toRef(props, 'mode'),
      rowKeyField: tableRowKeyField,
      sortContainer: toRef(props, 'sortContainer'),
      sourceFieldConfigs: toRef(props, 'sourceFieldConfigs'),
      enabledClickMenu: toRef(props, 'enabledClickMenu'),
      canSortFieldTypes: toRef(props, 'canSortFieldTypes'),
      renderContext,
      tableHeaderCellRender: (...args) => tableHeaderCellRender(...args),
      tableCellRender,
      handleConditionMenuShow: (...args) => handleConditionMenuShow(...args),
      handleSliderShowChange: (...args) => handleSliderShowChange(...args),
      handleSortChange: (sortInfo: TableSort) => handleSortChange(sortInfo),
    });

    const tableSkeletonConfig = computed(() => {
      const loading = props.tableLoading[ExploreTableLoadingEnum.BODY_SKELETON];
      if (!loading) return null;
      const config = {
        tableClass: 'explore-table-hidden-body',
        skeletonClass: 'explore-skeleton-show-body',
      };
      return config;
    });

    /**
     * @description 滚动触底加载更多
     */
    const handleScrollToEnd = (target: HTMLElement) => {
      if (!props.tableHasScrollLoading) {
        return;
      }
      const { scrollHeight, scrollTop, clientHeight } = target;
      const isEnd = !!scrollTop && Math.abs(scrollHeight - scrollTop - clientHeight) <= 1;
      const noScrollBar = scrollHeight <= clientHeight + 1;
      const shouldRequest = noScrollBar || isEnd;
      if (!shouldRequest) return;
      if (
        !(
          props.tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] ||
          props.tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] ||
          props.tableLoading[ExploreTableLoadingEnum.SCROLL]
        )
      ) {
        emit('scrollToEnd');
      }
      target.scrollTo({
        top: scrollHeight - 100,
        behavior: 'smooth',
      });
    };

    /**
     * @description 配置表格是否能够触发事件target
     */
    const updateTablePointEvents = (val: 'auto' | 'none') => {
      const tableDom = tableRef?.value?.$el;
      if (!tableDom) return;
      tableDom.style.pointerEvents = val;
    };

    /**
     * @description 滚动触发事件
     */
    const handleScroll = (event: Event) => {
      if (!props.tableData?.length) {
        return;
      }
      updateTablePointEvents('none');
      ellipsisPopoverHide();
      descriptionPopoverHide();
      conditionMenuPopoverHide();
      handleScrollToEnd(event.target as HTMLElement);
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      scrollPointerEventsTimer = setTimeout(() => {
        updateTablePointEvents('auto');
      }, 600);
    };

    /**
     * @description 移除滚动监听
     */
    const removeScrollListener = () => {
      if (!scrollContainer) return;
      scrollContainer.removeEventListener('scroll', handleScroll);
      scrollContainer = null;
    };

    /**
     * @description 添加滚动监听
     */
    const addScrollListener = () => {
      removeScrollListener();
      scrollContainer = document.querySelector(props.scrollContainerSelector);
      if (!scrollContainer) return;
      scrollContainer.addEventListener('scroll', handleScroll);
    };

    /**
     * @description: 修改条件菜单所需数据
     */
    const setActiveConditionMenu = (item: Partial<ActiveConditionMenuTarget> = {}) => {
      activeConditionMenuTarget.rowId = item.rowId || '';
      activeConditionMenuTarget.colId = item.colId || '';
      activeConditionMenuTarget.conditionValue = item.conditionValue || '';
      activeConditionMenuTarget.customMenuList = item.customMenuList || [];
    };

    /**
     * @description: 显示条件菜单
     */
    const handleConditionMenuShow = (triggerDom: HTMLElement, conditionMenuTarget: ActiveConditionMenuTarget) => {
      const oldRowId = activeConditionMenuTarget.rowId;
      const oldColId = activeConditionMenuTarget.colId;
      conditionMenuPopoverHide();
      setActiveConditionMenu();
      if (conditionMenuTarget.rowId === oldRowId && conditionMenuTarget.colId === oldColId) {
        return;
      }
      setActiveConditionMenu(conditionMenuTarget);
      const { isEllipsisActive } = isEllipsisActiveSingleLine(triggerDom.parentElement);
      conditionMenuPopoverShow(isEllipsisActive ? triggerDom.parentElement : triggerDom, conditionMenuRef.value.$el);
    };

    /**
     * @description 表格排序回调
     * @param {string} sortEvent.sortBy 排序字段名
     * @param {boolean} sortEvent.descending 排序方式
     */
    const handleSortChange = (sortEvent: TableSort) => {
      if (Array.isArray(sortEvent)) {
        return;
      }
      emit('sortChange', sortEvent);
    };

    /**
     * @description 表格空数据显示中的 数据源配置 点击回调
     */
    const handleDataSourceConfigClick = () => {
      const { appName } = props;
      if (!appName) {
        return;
      }
      const hash = `#/apm/application/config/${appName}?active=dataStatus`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };

    /**
     * @description TraceId/SpanId 点击触发回调
     */
    const handleSliderShowChange = (openMode: '' | 'span' | 'trace', activeId: string) => {
      emit('sliderShow', openMode, activeId);
    };

    /**
     * @description 字段分析统计弹窗改变filter条件回调
     */
    const handleConditionChange = (value: ConditionChangeEvent) => {
      emit('conditionChange', value);
    };

    /**
     * @description 字段分析统计菜单项点击后回调
     */
    const handleMenuClick = () => {
      setActiveConditionMenu();
      conditionMenuPopoverHide();
    };

    /**
     * @description 字段分析统计弹窗中 更多抽屉页 展示/消失 状态回调
     */
    const handleStatisticsSliderShow = (sliderShow: boolean) => {
      statisticsSliderShow = sliderShow;
      if (!sliderShow) {
        handleStatisticsPopoverHide();
      }
    };

    /**
     * @description 关闭字段分析统计弹窗
     * @param {boolean} resetActiveStatisticsField 是否重置当前激活字段分析弹窗面板展示的字段
     */
    const handleStatisticsPopoverHide = (resetActiveStatisticsField = true) => {
      showStatisticsPopover.value = false;
      statisticsPopoverInstance?.hide(0);
      statisticsPopoverInstance?.close();
      statisticsPopoverInstance = null;
      if (resetActiveStatisticsField) {
        activeStatisticsField.value = '';
      }
    };

    /**
     * @description 打开字段分析统计弹窗
     */
    const handleStatisticsPopoverShow = async (e: Event, item: IDimensionFieldTreeItem) => {
      e.stopPropagation();
      handleStatisticsPopoverHide();
      activeStatisticsField.value = item.name;
      if (!item.is_dimensions) return;
      statisticsPopoverInstance = $bkPopover({
        target: e.currentTarget as HTMLDivElement,
        content: statisticsListRef.value.$refs.dimensionPopover as HTMLDivElement,
        trigger: 'click',
        placement: 'right',
        theme: 'light',
        arrow: true,
        boundary: 'viewport',
        extCls: 'statistics-dimension-popover-cls',
        width: 405,
        // @ts-expect-error
        distance: -5,
        onHide() {
          showStatisticsPopover.value = false;
          if (!statisticsSliderShow) {
            activeStatisticsField.value = '';
          }
        },
      });
      setTimeout(() => {
        showStatisticsPopover.value = true;
        statisticsPopoverInstance.show();
      }, 100);
    };

    /**
     * @description 字段分析组件渲染方法
     */
    const statisticsDomRender = () => {
      if (!props.enableStatistics) return;
      const fieldOptions = tableColumns.value?.fieldMap?.[activeStatisticsField.value];
      return [
        <StatisticsList
          key='statisticsList'
          ref='statisticsListRef'
          commonParams={props.commonParams}
          fieldType={fieldOptions?.type}
          isShow={showStatisticsPopover.value}
          selectField={fieldOptions?.name}
          onConditionChange={handleConditionChange}
          onShowMore={() => handleStatisticsPopoverHide(false)}
          onSliderShowChange={handleStatisticsSliderShow}
        />,
      ];
    };

    /**
     * @description table 带有列描述的表头渲染方法
     * @param title 列名
     * @param tipText 列描述
     */
    const tableHeaderCellRender = (title: string, tipText: string, column: ExploreTableColumn) => {
      const fieldOptions = tableColumns.value?.fieldMap?.[column.colKey];
      const fieldType = fieldOptions?.type || '';
      const chartIconActive = column.colKey === activeStatisticsField.value ? 'active-statistics-field' : '';
      return () =>
        (
          <div
            key={title}
            class={`explore-header-col ${chartIconActive}`}
          >
            {props.showHeaderIcon && (
              <FieldTypeIcon
                class='col-type-icon'
                type={fieldType}
              />
            )}

            <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
              <span
                class={`th-label ${ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME}`}
                data-col-description={tipText}
              >
                {title}
              </span>
            </div>
            {props.enableStatistics && fieldOptions?.is_dimensions ? (
              <i
                class='icon-monitor icon-Chart statistics-icon'
                onClick={e => handleStatisticsPopoverShow(e, fieldOptions)}
              />
            ) : null}
          </div>
        ) as unknown as SlotReturnValue;
    };

    // 监听 tableData 变化，更新缓存并触发触底加载逻辑兼容
    watch(
      () => props.tableData,
      (newData, oldData) => {
        // 更新数据缓存
        if (newData?.length) {
          // 如果是新数据（长度变小或完全不同），清空缓存重新缓存
          if (!oldData?.length || newData.length < oldData.length) {
            clearCache();
          }
          cacheRows(newData as Record<string, unknown>[]);
        } else {
          clearCache();
        }
        requestAnimationFrame(() => {
          // 触底加载逻辑兼容屏幕过大或dpr很小的边际场景处理
          handleScrollToEnd(document.querySelector(props.scrollContainerSelector));
        });
      },
      { immediate: true }
    );

    onMounted(() => {
      addScrollListener();
      setTimeout(() => {
        initEllipsisListeners();
        initHeaderDescritionListeners();
        props.enabledClickMenu && initConditionMenuListeners();
      }, 300);
    });

    onBeforeUnmount(() => {
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      removeScrollListener();
    });

    return {
      tableRowKeyField,
      tableColumns,
      tableDisplayColumns,
      tableSkeletonConfig,
      activeConditionMenuTarget,
      handleSortChange,
      handleDataSourceConfigClick,
      statisticsDomRender,
      handleMenuClick,
      handleConditionChange,
    };
  },

  render() {
    return (
      <div
        style={{
          // 消除表格组件实现吸底效果时候吸底虚拟滚动条组件marginTop 多处理了 1px 的副作用
          marginTop: this.tableData?.length ? 0 : '-1px',
        }}
        class='trace-explore-table'
      >
        <PrimaryTable
          ref='tableRef'
          class={`explore-table ${this.tableSkeletonConfig?.tableClass}`}
          v-slots={{
            empty: () => (
              <ExploreTableEmpty
                showOperation={this.showOperation}
                onClearFilter={() => this.$emit('clearRetrievalFilter')}
                onDataSourceConfigClick={this.handleDataSourceConfigClick}
              />
            ),
          }}
          // @ts-expect-error
          columns={[
            ...this.tableDisplayColumns,
            ...(this.enabledDisplayFieldSetting
              ? [
                  {
                    width: '32px',
                    minWidth: '32px',
                    fixed: 'right',
                    align: 'center',
                    resizable: false,
                    thClassName: '__table-custom-setting-col__',
                    colKey: '__col_setting__',
                    title: () => {
                      return (
                        <ExploreFieldSetting
                          class='table-field-setting'
                          fixedDisplayList={[this.tableRowKeyField]}
                          sourceList={this.tableColumns.fieldList}
                          sourceMap={this.tableColumns.fieldMap}
                          targetList={this.displayFields}
                          onConfirm={displayFields => this.$emit('displayFieldChange', displayFields)}
                        />
                      );
                    },
                    cell: () => undefined,
                  },
                ]
              : []),
          ]}
          headerAffixedTop={{
            container: this.scrollContainerSelector,
          }}
          horizontalScrollAffixedBottom={{
            container: this.scrollContainerSelector,
          }}
          // @ts-expect-error
          lastFullRow={
            this.tableData.length
              ? () => (
                  <Loading
                    style={{ display: this.tableHasScrollLoading ? 'inline-flex' : 'none' }}
                    class='scroll-end-loading'
                    loading={true}
                    mode='spin'
                    size='mini'
                    theme='primary'
                    title={window.i18n.t('加载中...')}
                  />
                )
              : undefined
          }
          rowspanAndColspan={
            this.enabledDisplayFieldSetting
              ? ({ colIndex }) => {
                  return {
                    rowspan: 1,
                    colspan: colIndex === this.tableDisplayColumns.length - 1 ? 2 : 1,
                  };
                }
              : undefined
          }
          activeRowType='single'
          data={this.tableData}
          hover={true}
          needCustomScroll={false}
          resizable={true}
          rowKey={this.tableRowKeyField}
          showSortColumnBgColor={true}
          size='small'
          sort={this.sortContainer}
          stripe={false}
          tableLayout='fixed'
          onColumnResizeChange={context => this.$emit('columnResize', context)}
          onSortChange={this.handleSortChange}
        />

        <TableSkeleton class={`explore-table-skeleton ${this.tableSkeletonConfig?.skeletonClass}`} />

        <div style='display: none'>
          <ExploreConditionMenu
            ref='conditionMenuRef'
            conditionKey={this.activeConditionMenuTarget.colId}
            conditionValue={this.activeConditionMenuTarget.conditionValue}
            customMenuList={this.activeConditionMenuTarget.customMenuList}
            onConditionChange={this.handleConditionChange}
            onMenuClick={this.handleMenuClick}
          />
        </div>
        {this.statisticsDomRender()}
      </div>
    );
  },
});
