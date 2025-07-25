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
  defineAsyncComponent,
  defineComponent,
  KeepAlive,
  onBeforeUnmount,
  onMounted,
  reactive,
  readonly,
  shallowRef,
  toRef,
  unref,
  useTemplateRef,
  watch,
} from 'vue';

import { type SortInfo, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { useDebounceFn } from '@vueuse/core';
import { $bkPopover, Loading } from 'bkui-vue';

import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { useTraceExploreStore } from '../../../../store/modules/explore';
import ExploreFieldSetting from '../explore-field-setting/explore-field-setting';
const ExploreSpanSlider = defineAsyncComponent(() => import('../explore-span-slider/explore-span-slider'));
const ExploreTraceSlider = defineAsyncComponent(() => import('../explore-trace-slider/explore-trace-slider'));

import FieldTypeIcon from '../field-type-icon';
import StatisticsList from '../statistics-list';
import ExploreConditionMenu from './components/explore-condition-menu';
import ExploreTableEmpty from './components/explore-table-empty';
import {
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
} from './constants';
import { useExploreColumnConfig } from './hooks/use-explore-column-config';
import { useExploreDataCache } from './hooks/use-explore-data-cache';
import { useTableCell } from './hooks/use-table-cell';
import { useTableEllipsis, useTableHeaderDescription, useTablePopover } from './hooks/use-table-popover';
import { type ActiveConditionMenuTarget, type ExploreTableColumn, ExploreTableLoadingEnum } from './typing';
import { getTableList } from './utils/api-utils';
import { isEllipsisActiveSingleLine } from './utils/dom-helper';

import type { ConditionChangeEvent, ExploreFieldList, ICommonParams, IDimensionFieldTreeItem } from '../../typing';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './trace-explore-table.scss';

const SCROLL_ELEMENT_CLASS_NAME = '.trace-explore-view';

export default defineComponent({
  name: 'TraceExploreTable',
  props: {
    /** 当前视角是否为 Span 视角 */
    mode: {
      type: String as PropType<'span' | 'trace'>,
    },
    /** 当前选中的应用 Name */
    appName: {
      type: String,
    },
    /** 当前选中的应用 Name */
    timeRange: {
      type: Array as PropType<string[]>,
    },
    /** 是否立即刷新 */
    refreshImmediate: {
      type: String,
    },
    /** 接口请求配置参数 */
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    /** 不同视角下维度字段的列表 */
    fieldListMap: {
      type: Object as PropType<ExploreFieldList>,
      default: () => ({
        trace: [],
        span: [],
      }),
    },
  },
  emits: {
    backTop: () => true,

    conditionChange: (val: ConditionChangeEvent) => true,
    clearRetrievalFilter: () => true,
    setUrlParams: () => true,
  },
  setup(props, { emit }) {
    const store = useTraceExploreStore();

    /** 表格单页条数 */
    const limit = 30;
    /** 表格logs数据请求中止控制器 */
    let abortController: AbortController = null;
    /** 滚动容器元素 */
    let scrollContainer: HTMLElement = null;
    /** 滚动结束后回调逻辑执行计时器  */
    let scrollPointerEventsTimer = null;
    /** 统计弹窗实例 */
    let statisticsPopoverInstance = null;

    const tableRef = useTemplateRef<InstanceType<typeof PrimaryTable>>('tableRef');
    const conditionMenuRef = useTemplateRef<InstanceType<typeof ExploreConditionMenu>>('conditionMenuRef');
    const statisticsListRef = useTemplateRef<InstanceType<typeof StatisticsList>>('statisticsListRef');

    /** 当前需要打开的抽屉类型(trace详情抽屉/span详情抽屉) */
    const sliderMode = shallowRef<'' | 'span' | 'trace'>('');
    /** 打开抽屉所需的数据Id(traceId/spanId) */
    const activeSliderId = shallowRef('');
    /** 判断table数据是否还有数据可以获取 */
    const tableHasMoreData = shallowRef(false);
    /** table loading 配置 */
    const tableLoading = reactive({
      /** table body部分 骨架屏 loading */
      [ExploreTableLoadingEnum.BODY_SKELETON]: false,
      /** table header部分 骨架屏 loading */
      [ExploreTableLoadingEnum.HEADER_SKELETON]: false,
      /** 表格触底加载更多 loading  */
      [ExploreTableLoadingEnum.SCROLL]: false,
    });
    /** 表格列排序配置 */
    const sortContainer = readonly<SortInfo>(unref(toRef(store, 'tableSortContainer')));

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

    /** 当前视角是否为 Span 视角 */
    const isSpanVisual = computed(() => props.mode === 'span');
    /** 表格行可用作 唯一主键值 的字段名 */
    const tableRowKeyField = computed(() => (isSpanVisual.value ? 'span_id' : 'trace_id'));

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

    const { tableCellRender } = useTableCell(tableRowKeyField);
    const {
      tableColumns,
      displayColumnFields,
      tableDisplayColumns,
      getCustomDisplayColumnFields,
      handleDisplayColumnFieldsChange,
      handleDisplayColumnResize,
    } = useExploreColumnConfig({
      props,
      isSpanVisual,
      rowKeyField: tableRowKeyField,
      sortContainer,
      tableHeaderCellRender,
      tableCellRender,
      handleConditionMenuShow,
      handleSliderShowChange,
      handleSortChange,
    });

    /** 当前是否进行了本地 "耗时" 的筛选操作 */
    const isLocalFilterMode = computed(() => store?.filterTableList?.length);
    /** table 数据（所有请求返回的数据） */
    const tableData = computed(() => store.tableList);
    /** 当前表格需要渲染的数据(根据图标耗时统计面板过滤后的数据) */
    const tableViewData = computed(() => (isLocalFilterMode.value ? store.filterTableList : tableData.value));
    /** 判断当前数据是否需要触底加载更多 */
    const tableHasScrollLoading = computed(() => !isLocalFilterMode.value && tableHasMoreData.value);

    /** 请求参数 */
    const queryParams = computed(() => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { mode, query_string, ...params } = props.commonParams;
      const [start_time, end_time] = handleTransformToTimestamp(props.timeRange);

      let sort = [];
      if (sortContainer.sortBy) {
        sort = [`${sortContainer.descending ? '-' : ''}${sortContainer.sortBy}`];
      }

      return {
        ...params,
        start_time,
        end_time,
        query: query_string,
        sort,
      };
    });

    const tableSkeletonConfig = computed(() => {
      const loading = tableLoading[ExploreTableLoadingEnum.BODY_SKELETON];
      if (!loading) return null;
      // const headerLoading = tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON];
      const config = {
        tableClass: 'explore-table-hidden-body',
        skeletonClass: 'explore-skeleton-show-body',
      };
      // if (headerLoading) {
      //   config = {
      //     tableClass: 'explore-table-hidden-all',
      //     skeletonClass: 'explore-skeleton-show-all',
      //   };
      // }
      return config;
    });

    watch(
      [
        () => isSpanVisual.value,
        () => props.appName,
        () => props.timeRange,
        () => props.refreshImmediate,
        () => sortContainer.sortBy,
        () => sortContainer.descending,
        () => props.commonParams.filters,
        () => props.commonParams.query_string,
      ],
      (nVal, oVal) => {
        tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = true;
        tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = true;
        store.updateTableList([]);
        emit('backTop');

        if (nVal[0] !== oVal[0] || nVal[1] !== oVal[1]) {
          handleSortChange({
            sortBy: '',
            descending: null,
          });
          getCustomDisplayColumnFields();
        }
        debouncedGetExploreList();
      }
    );

    onMounted(() => {
      getCustomDisplayColumnFields();
      // debouncedGetExploreList();
      addScrollListener();
      setTimeout(() => {
        initEllipsisListeners();
        initHeaderDescritionListeners();
        initConditionMenuListeners();
      }, 300);
    });

    onBeforeUnmount(() => {
      scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
      removeScrollListener();
      abortController?.abort?.();
      abortController = null;
      store.updateTableList([]);
      store.updateTableSortContainer({ sortBy: '', descending: null });
    });

    /**
     * @description 添加滚动监听
     */
    function addScrollListener() {
      removeScrollListener();
      scrollContainer = document.querySelector(SCROLL_ELEMENT_CLASS_NAME);
      if (!scrollContainer) return;
      scrollContainer.addEventListener('scroll', handleScroll);
    }

    /**
     * @description 移除滚动监听
     */
    function removeScrollListener() {
      if (!scrollContainer) return;
      scrollContainer.removeEventListener('scroll', handleScroll);
      scrollContainer = null;
    }

    /**
     * @description 滚动触发事件
     *
     */
    function handleScroll(event: Event) {
      if (!tableData.value?.length) {
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
    }

    /**
     * @description 滚动触底加载更多
     *
     */
    function handleScrollToEnd(target: HTMLElement) {
      if (!tableHasScrollLoading.value) {
        return;
      }
      const { scrollHeight, scrollTop, clientHeight } = target;
      const isEnd = !!scrollTop && Math.abs(scrollHeight - scrollTop - clientHeight) <= 1;
      const noScrollBar = scrollHeight <= clientHeight + 1;
      const shouldRequest = noScrollBar || isEnd;
      if (!shouldRequest) return;
      if (
        !(
          tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] ||
          tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] ||
          tableLoading[ExploreTableLoadingEnum.SCROLL]
        )
      ) {
        getExploreList(ExploreTableLoadingEnum.SCROLL);
      }
      target.scrollTo({
        top: scrollHeight - 100,
        behavior: 'smooth',
      });
    }

    /**
     * @description 配置表格是否能够触发事件target
     *
     */
    function updateTablePointEvents(val: 'auto' | 'none') {
      const tableDom = tableRef?.value?.$el;
      if (!tableDom) return;
      tableDom.style.pointerEvents = val;
    }

    /**
     * @description: 获取 table 表格数据
     *
     */
    async function getExploreList(loadingType = ExploreTableLoadingEnum.BODY_SKELETON) {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { app_name, start_time, end_time } = queryParams.value;
      if (!app_name || !start_time || !end_time) {
        store.updateTableList([]);
        clearCache();
        tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
        tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
        tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
        return;
      }
      // 检测排序字段是否在字段列表中，不在则忽略该字段的排序规则
      const shouldIgnoreSortField = sortContainer.sortBy && !tableColumns.value?.fieldMap?.[sortContainer.sortBy];
      if (shouldIgnoreSortField) {
        handleSortChange({ sortBy: '', descending: null });
        return;
      }
      if (loadingType === ExploreTableLoadingEnum.BODY_SKELETON) {
        store.updateTableList([]);
        clearCache();
      }

      tableLoading[loadingType] = true;
      const requestParam = {
        ...queryParams.value,
        limit: limit,
        offset: tableData.value?.length || 0,
      };
      abortController = new AbortController();
      store.updateTableLoading(true);
      const res = await getTableList(requestParam, isSpanVisual.value, {
        signal: abortController.signal,
      });
      store.updateTableLoading(false);
      if (res?.isAborted) {
        tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
        return;
      }
      tableLoading[loadingType] = false;
      tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
      // 更新表格数据
      if (loadingType === ExploreTableLoadingEnum.BODY_SKELETON) {
        store.updateTableList(res.data);
      } else {
        store.updateTableList([...tableData.value, ...res.data]);
      }
      cacheRows(res.data);
      tableHasMoreData.value = res.data?.length >= limit;
      requestAnimationFrame(() => {
        // 触底加载逻辑兼容屏幕过大或dpr很小的边际场景处理
        // 由于这里判断是否还有数据不是根据total而是根据接口返回数据是否为空判断
        // 所以该场景处理只能通过多次请求的方案来兼容，不能通过首次请求加大页码的方式来兼容
        // 否则在某些边界场景下会出现首次请求返回的不为空数据已经是全部数据了
        // 还是但未出现滚动条，导致无法触发触底逻辑再次请求接口判断是否已是全部数据
        // 从而导致触底loading一直存在但实际已没有更多数据
        handleScrollToEnd(document.querySelector(SCROLL_ELEMENT_CLASS_NAME));
      });
    }
    const debouncedGetExploreList = useDebounceFn(getExploreList, 200);

    /**
     * @description: 修改条件菜单所需数据
     *
     */
    function setActiveConditionMenu(item: Partial<ActiveConditionMenuTarget> = {}) {
      activeConditionMenuTarget.rowId = item.rowId || '';
      activeConditionMenuTarget.colId = item.colId || '';
      activeConditionMenuTarget.conditionValue = item.conditionValue || '';
      activeConditionMenuTarget.customMenuList = item.customMenuList || [];
    }

    /**
     * @description: 显示条件菜单
     *
     */
    function handleConditionMenuShow(triggerDom: HTMLElement, conditionMenuTarget: ActiveConditionMenuTarget) {
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
    }

    /**
     * @description 表格排序回调
     * @param {string} sortEvent.sortBy 排序字段名
     * @param {boolean} sortEvent.descending 排序方式
     *
     */
    function handleSortChange(sortEvent: TableSort) {
      if (Array.isArray(sortEvent)) {
        return;
      }
      store.updateTableSortContainer(sortEvent);
      emit('setUrlParams');
    }

    /**
     * @description 表格空数据显示中的 数据源配置 点击回调
     *
     */
    function handleDataSourceConfigClick() {
      const { appName } = props;
      if (!appName) {
        return;
      }
      const hash = `#/apm/application/config/${appName}?active=dataStatus`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    /**
     * @description TraceId/SpanId 点击触发回调
     *
     */
    function handleSliderShowChange(openMode: '' | 'span' | 'trace', activeId: string) {
      activeSliderId.value = activeId;
      sliderMode.value = openMode;
    }

    /**
     * @description 字段分析统计弹窗改变filter条件回调
     *
     */
    function handleConditionChange(value: ConditionChangeEvent) {
      emit('conditionChange', value);
    }

    /**
     * @description 字段分析统计菜单项点击后回调
     *
     */
    function handleMenuClick() {
      setActiveConditionMenu();
      conditionMenuPopoverHide();
    }

    /**
     * @description 打开字段分析统计弹窗
     *
     */
    async function handleStatisticsPopoverShow(e: Event, item: IDimensionFieldTreeItem) {
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
        // @ts-ignore
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
    }

    /**
     * @description 关闭字段分析统计弹窗
     * @param {boolean} resetActiveStatisticsField 是否重置当前激活字段分析弹窗面板展示的字段
     *
     */
    function handleStatisticsPopoverHide(resetActiveStatisticsField = true) {
      showStatisticsPopover.value = false;
      statisticsPopoverInstance?.hide(0);
      statisticsPopoverInstance?.close();
      statisticsPopoverInstance = null;
      if (resetActiveStatisticsField) {
        activeStatisticsField.value = '';
      }
    }

    /**
     * @description 字段分析统计弹窗中 更多抽屉页 展示/消失 状态回调
     */
    function handleStatisticsSliderShow(sliderShow: boolean) {
      statisticsSliderShow = sliderShow;
      if (!sliderShow) {
        handleStatisticsPopoverHide();
      }
    }

    /**
     * @description 字段分析组件渲染方法
     *
     */
    function statisticsDomRender() {
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
    }

    /**
     * @description table 带有列描述的表头渲染方法
     * @param title 列名
     * @param tipText 列描述
     *
     */
    function tableHeaderCellRender(title: string, tipText: string, column: ExploreTableColumn) {
      const fieldOptions = tableColumns.value?.fieldMap?.[column.colKey];
      const fieldType = fieldOptions?.type || '';
      const chartIconActive = column.colKey === activeStatisticsField.value ? 'active-statistics-field' : '';
      return () =>
        (
          <div
            key={title}
            class={`explore-header-col ${chartIconActive}`}
          >
            <FieldTypeIcon
              class='col-type-icon'
              type={fieldType}
            />
            <div class={`${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
              <span
                class={`th-label ${ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME}`}
                data-col-description={tipText}
              >
                {title}
              </span>
            </div>
            {fieldOptions?.is_dimensions ? (
              <i
                class='icon-monitor icon-Chart statistics-icon'
                onClick={e => handleStatisticsPopoverShow(e, fieldOptions)}
              />
            ) : null}
          </div>
        ) as unknown as SlotReturnValue;
    }

    function handleClearRetrievalFilter() {
      emit('clearRetrievalFilter');
    }

    return {
      tableRowKeyField,
      displayColumnFields,
      tableColumns,
      tableLoading,
      tableHasScrollLoading,
      sortContainer,
      tableDisplayColumns,
      tableData,
      tableViewData,
      tableSkeletonConfig,
      sliderMode,
      activeSliderId,
      activeConditionMenuTarget,
      handleSortChange,
      handleDataSourceConfigClick,
      handleDisplayColumnFieldsChange,
      handleDisplayColumnResize,
      statisticsDomRender,
      handleSliderShowChange,
      handleClearRetrievalFilter,
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
          class={this.tableSkeletonConfig?.tableClass}
          v-slots={{
            empty: () => (
              <ExploreTableEmpty
                onClearFilter={this.handleClearRetrievalFilter}
                onDataSourceConfigClick={this.handleDataSourceConfigClick}
              />
            ),
          }}
          columns={[
            // @ts-ignore
            ...this.tableDisplayColumns,
            {
              width: '32px',
              minWidth: '32px',
              fixed: 'right',
              align: 'center',
              resizable: false,
              thClassName: '__table-custom-setting-col__',
              colKey: '__col_setting__',
              // @ts-ignore
              title: () => {
                return (
                  <ExploreFieldSetting
                    class='table-field-setting'
                    fixedDisplayList={[this.tableRowKeyField]}
                    sourceList={this.tableColumns.fieldList}
                    sourceMap={this.tableColumns.fieldMap}
                    targetList={this.displayColumnFields}
                    onConfirm={this.handleDisplayColumnFieldsChange}
                  />
                );
              },
              cell: () => undefined,
            },
          ]}
          headerAffixedTop={{
            container: SCROLL_ELEMENT_CLASS_NAME,
          }}
          horizontalScrollAffixedBottom={{
            container: SCROLL_ELEMENT_CLASS_NAME,
          }}
          // @ts-ignore
          lastFullRow={
            this.tableViewData.length
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
          rowspanAndColspan={({ colIndex }) => {
            return {
              rowspan: 1,
              colspan: colIndex === this.tableDisplayColumns.length - 1 ? 2 : 1,
            };
          }}
          activeRowType='single'
          data={this.tableViewData}
          hover={true}
          resizable={true}
          rowKey={this.tableRowKeyField}
          showSortColumnBgColor={true}
          size='small'
          sort={this.sortContainer}
          stripe={false}
          tableLayout='fixed'
          onColumnResizeChange={this.handleDisplayColumnResize}
          onSortChange={this.handleSortChange}
        />
        <TableSkeleton class={`explore-table-skeleton ${this.tableSkeletonConfig?.skeletonClass}`} />
        <KeepAlive include={['ExploreTraceSlider', 'ExploreSpanSlider', 'AsyncComponentWrapper']}>
          <div>
            {this.sliderMode === 'trace' && (
              <ExploreTraceSlider
                appName={this.appName}
                isShow={this.sliderMode === 'trace'}
                traceId={this.activeSliderId}
                onSliderClose={() => this.handleSliderShowChange('', '')}
              />
            )}
            {this.sliderMode === 'span' && (
              <ExploreSpanSlider
                appName={this.appName}
                isShow={this.sliderMode === 'span'}
                spanId={this.activeSliderId}
                onSliderClose={() => this.handleSliderShowChange('', '')}
              />
            )}
          </div>
        </KeepAlive>
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
