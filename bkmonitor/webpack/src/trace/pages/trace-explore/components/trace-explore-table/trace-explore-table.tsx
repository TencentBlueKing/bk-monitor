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
  defineComponent,
  ref as deepRef,
  shallowRef,
  computed,
  reactive,
  onMounted,
  type PropType,
  watch,
  onBeforeUnmount,
  useTemplateRef,
  // KeepAlive,
  defineAsyncComponent,
  KeepAlive,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { PrimaryTable, type SortInfo, type TableSort } from '@blueking/tdesign-ui';
import { useDebounceFn } from '@vueuse/core';
import { $bkPopover, Loading } from 'bkui-vue';

import ChartFiltering from '../../../../components/chart-filtering/chart-filtering';
import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { formatDuration, formatTraceTableDate } from '../../../../components/trace-view/utils/date';
import useUserConfig from '../../../../hooks/useUserConfig';
import { useTraceExploreStore } from '../../../../store/modules/explore';
import ExploreFieldSetting from '../explore-field-setting/explore-field-setting';
const ExploreSpanSlider = defineAsyncComponent(() => import('../explore-span-slider/explore-span-slider'));
const ExploreTraceSlider = defineAsyncComponent(() => import('../explore-trace-slider/explore-trace-slider'));

import StatisticsList from '../statistics-list';
import ExploreConditionMenu from './components/explore-condition-menu';
import ExploreTableEmpty from './components/explore-table-empty';
import {
  CAN_TABLE_SORT_FIELD_TYPES,
  ENABLED_TABLE_CONDITION_MENU_CLASS_NAME,
  ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME,
  ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME,
  SERVICE_CATEGORY_MAP,
  SERVICE_STATUS_COLOR_MAP,
  SPAN_KIND_MAPS,
  SPAN_STATUS_CODE_MAP,
  TABLE_DEFAULT_CONFIG,
  TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX,
} from './constants';
import { useTableEllipsis, useTableHeaderDescription, useTablePopover } from './hooks/use-table-popover';
import {
  type ExploreTableColumn,
  ExploreTableColumnTypeEnum,
  ExploreTableLoadingEnum,
  type GetTableCellRenderValue,
} from './typing';
import { getTableList } from './utils/api-utils';
import { isEllipsisActiveSingleLine } from './utils/dom-helper';

import type {
  ConditionChangeEvent,
  ExploreFieldList,
  ICommonParams,
  IDimensionField,
  IDimensionFieldTreeItem,
} from '../../typing';

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
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    conditionChange: (val: ConditionChangeEvent) => true,
    clearRetrievalFilter: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();

    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

    /** table 默认配置项 */
    const { tableConfig: defaultTableConfig, traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;
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
    const durationPopover = useTemplateRef<HTMLDivElement>('durationPopoverRef');

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

    const { initListeners: initConditionMenuListeners, handlePopoverHide: conditionMenuPopoverHide } = useTablePopover(
      tableRef,
      {
        trigger: {
          selector: `.${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`,
          eventType: 'click',
          delay: 0,
        },
        getContentOptions: triggerDom => {
          if (
            triggerDom.dataset.colKey === activeConditionMenuTarget.conditionKey &&
            triggerDom.dataset.cellSource === activeConditionMenuTarget.conditionValue
          ) {
            setActiveConditionMenu();
            return;
          }
          setActiveConditionMenu(triggerDom.dataset.colKey, triggerDom.dataset.cellSource);
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
        },
      }
    );

    /** table 显示列配置 */
    const displayColumnFields = deepRef<string[]>([]);
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
    const sortContainer = reactive<SortInfo>({
      /** 排序字段 */
      sortBy: '',
      /** 排序顺序 */
      descending: null,
    });
    /** 统计面板的 抽屉页展示状态 */
    let statisticsSliderShow = false;
    /** 字段分析弹窗 popover 显隐 */
    const showStatisticsPopover = shallowRef(false);
    /** 当前激活字段分析弹窗面板展示的字段 */
    const activeStatisticsField = shallowRef('');
    /** click弹出 conditionMenu popover组件所需参数 */
    const activeConditionMenuTarget = reactive({
      conditionKey: '',
      conditionValue: '',
    });

    /** 当前视角是否为 Span 视角 */
    const isSpanVisual = computed(() => props.mode === 'span');
    /** 表格行可用作 唯一主键值 的字段名 */
    const tableRowKeyField = computed(() => (isSpanVisual.value ? 'span_id' : 'trace_id'));
    /** table 列配置本地缓存时的 key */
    const displayColumnFieldsCacheKey = computed(
      () => `${props.mode}_${props.appName}_${TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX}`
    );
    /** 当前是否进行了本地 "耗时" 的筛选操作 */
    const isLocalFilterMode = computed(() => store?.filterTableList?.length);
    /** table 数据（所有请求返回的数据） */
    const tableData = computed(() => store.tableList);
    /** 当前表格需要渲染的数据(根据图标耗时统计面板过滤后的数据) */
    const tableViewData = computed(() => (isLocalFilterMode.value ? store.filterTableList : tableData.value));
    /** 判断当前数据是否需要触底加载更多 */
    const tableHasScrollLoading = computed(() => !isLocalFilterMode.value && tableHasMoreData.value);
    /** 过滤出 can_displayed 为 true 的 fieldList 及 kv 映射集合 */
    const canDisplayFieldListMap = computed(() => {
      const getCanDisplayFieldList = (
        mode: 'span' | 'trace'
      ): {
        fieldList: IDimensionField[];
        fieldMap: Record<string, IDimensionField>;
      } => {
        return props.fieldListMap?.[mode].reduce(
          (prev, curr) => {
            if (!curr.can_displayed) {
              return prev;
            }
            prev.fieldList.push(curr);
            prev.fieldMap[curr.name] = curr;
            return prev;
          },
          { fieldList: [], fieldMap: {} }
        );
      };
      return {
        trace: getCanDisplayFieldList('trace'),
        span: getCanDisplayFieldList('span'),
      };
    });
    /** table 所有列字段信息(字段设置使用) */
    const tableColumns = computed(() => {
      return canDisplayFieldListMap.value[props.mode];
    });
    /** table 显示列配置 */
    const tableDisplayColumns = computed<ExploreTableColumn[]>(() => {
      const fieldMap = tableColumns.value.fieldMap;
      const columnMap = getTableColumnMapByVisualMode();
      return displayColumnFields.value
        .map(colKey => {
          const fieldItem = fieldMap[colKey];
          let column = columnMap[colKey];
          if (!column && !fieldItem) return null;
          if (!column) {
            column = {
              renderType: ExploreTableColumnTypeEnum.TEXT,
              colKey: fieldItem?.name,
              title: fieldItem?.alias,
              headerDescription: fieldItem?.name,
              width: 130,
            };
          } else {
            column.title = fieldItem?.alias || column.title;
          }
          const tipText = column.headerDescription || column.colKey;
          column.sorter = column.sorter != null ? column.sorter : CAN_TABLE_SORT_FIELD_TYPES.has(fieldItem?.type);
          // 表格列表头渲染方法
          const tableHeaderTitle = tableDescriptionHeaderRender(column.title, tipText, column);
          // 表格单元格渲染方法
          const tableCell = (_, { row }) => handleSetFormatter(column, row);

          return {
            ...defaultTableConfig,
            ...column,
            title: tableHeaderTitle,
            cell: tableCell,
            attrs: column.sorter
              ? {
                  // 扩大排序点击热区范围
                  onClick(e: MouseEvent & { target: Element; currentTarget: Element }) {
                    if (
                      column.colKey &&
                      e.currentTarget.tagName.toLocaleLowerCase() === 'th' &&
                      !['svg', 'path'].includes(e.target.tagName.toLocaleLowerCase()) &&
                      e.currentTarget?.classList.contains(`t-table__th-${column.colKey}`)
                    ) {
                      if (sortContainer.sortBy === column.colKey) {
                        const sortDescValueList = [true, false, null];
                        const sortIndex = sortDescValueList.findIndex(v => sortContainer.descending === v);
                        sortContainer.descending = sortDescValueList.at((sortIndex + 1) % sortDescValueList.length);
                        if (sortContainer.descending === null) {
                          sortContainer.sortBy = '';
                        }
                        return;
                      }
                      sortContainer.sortBy = column.colKey;
                      sortContainer.descending = true;
                    }
                  },
                }
              : undefined,
          };
        })
        .filter(Boolean);
    });

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
      () => displayColumnFieldsCacheKey.value,
      () => {
        getDisplayColumnFields();
      }
    );

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
        if (nVal[0] !== oVal[0]) {
          sortContainer.sortBy = '';
          sortContainer.descending = null;
        }
        debouncedGetExploreList();
      }
    );

    onMounted(() => {
      getDisplayColumnFields();
      debouncedGetExploreList();
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
      if (
        !(
          tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] ||
          tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] ||
          tableLoading[ExploreTableLoadingEnum.SCROLL]
        ) &&
        shouldRequest
      ) {
        getExploreList(ExploreTableLoadingEnum.SCROLL);
      }
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
     * @description 根据当前激活的视角(trace/span)获取对应的table表格列配置
     *
     */
    function getTableColumnMapByVisualMode(): Record<string, ExploreTableColumn> {
      if (isSpanVisual.value) {
        return {
          span_id: {
            renderType: ExploreTableColumnTypeEnum.CLICK,
            colKey: 'span_id',
            title: t('Span ID'),
            width: 160,
            fixed: 'left',
            clickCallback: row => handleSliderShowChange('span', row.span_id),
          },
          span_name: {
            renderType: ExploreTableColumnTypeEnum.TEXT,
            colKey: 'span_name',
            title: t('接口名称'),
            width: 200,
          },
          time: {
            renderType: ExploreTableColumnTypeEnum.TIME,
            colKey: 'time',
            title: t('时间'),
            width: 160,
          },
          start_time: {
            renderType: ExploreTableColumnTypeEnum.TIME,
            colKey: 'start_time',
            title: t('开始时间'),
            width: 180,
          },
          end_time: {
            renderType: ExploreTableColumnTypeEnum.TIME,
            colKey: 'end_time',
            title: t('结束时间'),
            width: 180,
          },
          elapsed_time: {
            renderType: ExploreTableColumnTypeEnum.DURATION,
            colKey: 'elapsed_time',
            title: t('耗时'),
            width: 100,
          },
          'status.code': {
            renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
            colKey: 'status.code',
            headerDescription: 'status_code',
            title: t('状态'),
            width: 100,
            getRenderValue: (row, column) => SPAN_STATUS_CODE_MAP[row?.[column.colKey]],
          },
          kind: {
            renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
            colKey: 'kind',
            title: t('类型'),
            width: 100,
            getRenderValue: (row, column) => SPAN_KIND_MAPS[row?.[column.colKey]],
          },
          'resource.service.name': {
            renderType: ExploreTableColumnTypeEnum.LINK,
            colKey: 'resource.service.name',
            title: t('所属服务'),
            width: 160,
            getRenderValue: row => getJumpToApmLinkItem(row?.['resource.service.name']),
          },
          trace_id: {
            renderType: ExploreTableColumnTypeEnum.CLICK,
            colKey: 'trace_id',
            title: t('所属 Trace'),
            width: 240,
            clickCallback: row => handleSliderShowChange('trace', row.trace_id),
          },
        };
      }
      return {
        trace_id: {
          renderType: ExploreTableColumnTypeEnum.CLICK,
          colKey: 'trace_id',
          title: t('Trace ID'),
          width: 240,
          fixed: 'left',
          clickCallback: row => handleSliderShowChange('trace', row.trace_id),
        },
        min_start_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
          colKey: 'min_start_time',
          title: t('开始时间'),
          width: 140,
        },
        max_end_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
          colKey: 'max_end_time',
          title: t('结束时间'),
          width: 140,
        },
        root_span_name: {
          renderType: ExploreTableColumnTypeEnum.LINK,
          colKey: 'root_span_name',
          headerDescription: t('整个 Trace 的第一个 Span'),
          title: t('根 Span'),
          width: 160,
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service: {
          renderType: ExploreTableColumnTypeEnum.LINK,
          colKey: 'root_service',
          headerDescription: t('服务端进程的第一个 Service'),
          title: t('入口服务'),
          width: 160,
          getRenderValue: row => getJumpToApmLinkItem(row?.root_service),
        },
        root_service_span_name: {
          renderType: ExploreTableColumnTypeEnum.LINK,
          colKey: 'root_service_span_name',
          headerDescription: t('入口服务的第一个接口'),
          title: t('入口接口'),
          width: 160,
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service_category: {
          renderType: ExploreTableColumnTypeEnum.TEXT,
          colKey: 'root_service_category',
          title: t('调用类型'),
          width: 120,
          getRenderValue: (row, column) => SERVICE_CATEGORY_MAP[row?.[column.colKey]],
        },
        root_service_status_code: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
          colKey: 'root_service_status_code',
          title: t('状态码'),
          width: 100,
          getRenderValue: row => {
            const alias = row?.root_service_status_code as string;
            if (!alias) return [];
            const type = row?.root_service_status_code === 200 ? 'normal' : 'error';
            return [
              {
                alias: alias,
                ...SERVICE_STATUS_COLOR_MAP[type],
              },
            ];
          },
        },
        trace_duration: {
          renderType: ExploreTableColumnTypeEnum.DURATION,
          colKey: 'trace_duration',
          title: t('耗时'),
          width: 100,
        },
        hierarchy_count: {
          renderType: ExploreTableColumnTypeEnum.TEXT,
          colKey: 'hierarchy_count',
          title: t('Span 层数'),
          width: 110,
        },
        service_count: {
          renderType: ExploreTableColumnTypeEnum.TEXT,
          colKey: 'service_count',
          title: t('服务数量'),
          width: 100,
        },
        kind: {
          renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
          colKey: 'kind',
          title: t('类型'),
          width: 100,
          getRenderValue: (row, column) => SPAN_KIND_MAPS[row?.[column.colKey]],
        },
        root_span_kind: {
          renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
          colKey: 'root_span_kind',
          title: t('根 Span 类型'),
          width: 100,
          getRenderValue: (row, column) => SPAN_KIND_MAPS[row?.[column.colKey]],
        },
        root_service_kind: {
          renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
          colKey: 'root_service_kind',
          title: t('入口服务类型'),
          width: 100,
          getRenderValue: (row, column) => SPAN_KIND_MAPS[row?.[column.colKey]],
        },
        'status.code': {
          renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
          colKey: 'status.code',
          headerDescription: 'status_code',
          title: t('状态'),
          width: 100,
          getRenderValue: (row, column) => SPAN_STATUS_CODE_MAP[row?.[column.colKey]],
        },
      };
    }

    /**
     * @description: 获取 table 表格列配置
     *
     */
    async function getDisplayColumnFields() {
      if (!props.appName || !props.mode) return;
      const defaultColumnsConfig = isSpanVisual.value ? spanConfig : traceConfig;
      const cacheColumns = (await handleGetUserConfig<string[]>(displayColumnFieldsCacheKey.value)) || [];
      // 需要展示的字段列名数组
      displayColumnFields.value = cacheColumns?.length
        ? cacheColumns
        : ((defaultColumnsConfig?.displayFields || []) as string[]);
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
        tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
        tableLoading[ExploreTableLoadingEnum.BODY_SKELETON] = false;
        tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
        return;
      }
      let updateTableDataFn = list => {
        store.updateTableList([...tableData.value, ...list]);
      };

      if (loadingType === ExploreTableLoadingEnum.BODY_SKELETON) {
        store.updateTableList([]);
        updateTableDataFn = list => {
          store.updateTableList(list);
        };
      }

      tableLoading[loadingType] = true;
      const requestParam = {
        ...queryParams.value,
        limit: limit,
        offset: tableData.value?.length || 0,
      };
      abortController = new AbortController();
      const res = await getTableList(requestParam, isSpanVisual.value, {
        signal: abortController.signal,
      });
      if (res?.isAborted) {
        tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
        return;
      }
      tableLoading[loadingType] = false;
      tableLoading[ExploreTableLoadingEnum.HEADER_SKELETON] = false;
      updateTableDataFn(res.data);
      tableHasMoreData.value = res.data?.length === limit;
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
     * @description 获取新开页跳转至apm页 概览tab 的 LINK 类型表格列所需数据格式
     *
     */
    function getJumpToApmLinkItem(alias): GetTableCellRenderValue<ExploreTableColumnTypeEnum.LINK> {
      const hash = `#/apm/service?filter-service_name=${alias}&filter-app_name=${props.appName}`;
      let url = '';
      if (alias) {
        url = location.href.replace(location.hash, hash);
      }
      return {
        alias: alias,
        url: url,
      };
    }

    /**
     * @description 获取新开页跳转至 apm 页 接口tab 的 LINK 类型表格列所需数据格式
     *
     */
    function getJumpToApmApplicationLinkItem(row, column): GetTableCellRenderValue<ExploreTableColumnTypeEnum.LINK> {
      const service = row?.root_service;
      const alias = row?.[column.colKey];
      const hash = `#/apm/application?filter-service_name=${service}&filter-app_name=${props.appName}&sceneId=apm_application&sceneType=detail&dashboardId=endpoint&filter-endpoint_name=${alias}`;
      let url = '';
      if (alias && service) {
        url = location.href.replace(location.hash, hash);
      }
      return {
        alias: alias,
        url: url,
      };
    }

    function setActiveConditionMenu(colKey = '', cellSource = '') {
      activeConditionMenuTarget.conditionKey = colKey;
      activeConditionMenuTarget.conditionValue = cellSource;
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
      let sortBy = sortEvent?.sortBy;
      let descending = sortEvent?.descending;
      if (!sortBy) {
        sortBy = '';
        descending = null;
      }
      sortContainer.sortBy = sortBy;
      sortContainer.descending = descending;
    }

    /**
     * @description 表格列显示配置项变更回调
     *
     */
    function handleDisplayColumnFieldsChange(displayFields: string[]) {
      displayColumnFields.value = displayFields;
      // 缓存列配置
      handleSetUserConfig(JSON.stringify(displayFields));
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
      const isDuration = ['trace_duration', 'elapsed_time'].includes(item.name);
      if (!item.is_dimensions) return;
      statisticsPopoverInstance = $bkPopover({
        target: e.currentTarget as HTMLDivElement,
        content: isDuration
          ? durationPopover.value
          : (statisticsListRef.value.$refs.dimensionPopover as HTMLDivElement),
        trigger: 'click',
        placement: 'right',
        theme: 'light',
        arrow: true,
        boundary: 'viewport',
        extCls: isDuration ? 'duration-popover-cls' : 'statistics-dimension-popover-cls',
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
        if (!isDuration) {
          showStatisticsPopover.value = true;
        }
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
     * @description 耗时分析统计弹窗中 筛选时间范围列表数据 回调
     *
     */
    function handleFilterListChange(list) {
      store.updateFilterTableList(list);
    }

    /**
     * @description traceId详情抽屉 渲染方法
     *
     */
    // function traceSliderRender() {
    //   return (
    //     <ExploreTraceSlider
    //       appName={props.appName}
    //       isShow={sliderMode.value === 'trace'}
    //       traceId={activeSliderId.value}
    //       onSliderClose={() => handleSliderShowChange('', '')}
    //     />
    //   );
    // }

    // /**
    //  * @description spanId详情抽屉 渲染方法
    //  *
    //  */
    // function spanSliderRender() {
    //   return (
    //     <ExploreSpanSlider
    //       appName={props.appName}
    //       isShow={sliderMode.value === 'span'}
    //       spanId={activeSliderId.value}
    //       onSliderClose={() => handleSliderShowChange('', '')}
    //     />
    //   );
    // }

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
          isDimensions={fieldOptions?.is_dimensions}
          isShow={showStatisticsPopover.value}
          selectField={fieldOptions?.name}
          onConditionChange={handleConditionChange}
          onShowMore={() => handleStatisticsPopoverHide(false)}
          onSliderShowChange={handleStatisticsSliderShow}
        />,
        <div
          key='chartFiltering'
          style='display: none;'
        >
          <div
            ref='durationPopoverRef'
            class='duration-popover'
          >
            {tableData.value.length ? (
              <ChartFiltering
                filterList={store.filterTableList}
                isShowSlider={false}
                list={tableData.value}
                listType={props.commonParams.mode}
                onFilterListChange={handleFilterListChange}
              />
            ) : (
              <EmptyStatus type='empty' />
            )}
          </div>
        </div>,
      ];
    }

    /**
     * @description table 带有列描述的表头渲染方法
     * @param title 列名
     * @param tipText 列描述
     *
     */
    function tableDescriptionHeaderRender(title, tipText, column) {
      const fieldOptions = tableColumns.value?.fieldMap?.[column.colKey];
      const chartIconActive = column.colKey === activeStatisticsField.value ? 'active-statistics-field' : '';
      return () => (
        <div
          key={title}
          class={`explore-header-col ${chartIconActive}`}
        >
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
      );
    }

    /**
     * @description 获取表格单元格渲染值（允许列通过 getRenderValue 自定义获取值逻辑）
     * @param row 当前行数据
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function getTableCellRenderValue<T extends ExploreTableColumnTypeEnum>(
      row,
      column: ExploreTableColumn<T>
    ): GetTableCellRenderValue<T> {
      const defaultGetRenderValue = row => {
        const alias = row?.[column.colKey];
        if (typeof alias !== 'object' || alias == null) {
          return alias;
        }
        return JSON.stringify(alias);
      };
      const getRenderValue = column?.getRenderValue || defaultGetRenderValue;
      return getRenderValue(row, column);
    }

    /**
     * @description ExploreTableColumnTypeEnum.CLICK  可点击触发回调 列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function clickColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>, row) {
      const alias = getTableCellRenderValue(row, column);
      return (
        <div class={`explore-col explore-click-col ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
          <span
            class='explore-click-text '
            onClick={event => column?.clickCallback?.(row, column, event)}
          >
            {alias}
          </span>
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.PREFIX_ICON  带有前置 icon 列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function iconColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>, row) {
      const item = getTableCellRenderValue(row, column) || { alias: '', prefixIcon: '' };
      const { alias, prefixIcon } = item;
      if (alias == null || alias === '') {
        const textColumn = {
          ...column,
          getRenderValue: () => alias,
        };
        return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
      }
      const value = row?.[column.colKey];
      return (
        <div class='explore-col explore-prefix-icon-col'>
          <i class={`prefix-icon ${prefixIcon}`} />
          <span
            class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-cell-source={value}
            data-col-key={column.colKey}
          >
            {alias}
          </span>
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.ELAPSED_TIME 日期时间列渲染方法 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ss)
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function timeColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TIME>, row) {
      const timestamp = getTableCellRenderValue(row, column);
      const alias = formatTraceTableDate(timestamp);
      const value = row?.[column.colKey];
      return (
        <div class={`explore-col explore-time-col ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
          <span
            class={`explore-time-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-cell-source={value}
            data-col-key={column.colKey}
          >
            {alias}
          </span>
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.DURATION 持续时间列渲染方法 (将 时间戳 自适应转换为 带单位的时间-例如 10s、10ms...)
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function durationColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.DURATION>, row) {
      const timestamp = getTableCellRenderValue(row, column);
      const alias = formatDuration(+timestamp);
      const value = row?.[column.colKey];
      return (
        <div class={`explore-col explore-duration-col ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
          <span
            class={`explore-duration-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-cell-source={value}
            data-col-key={column.colKey}
          >
            {alias}
          </span>
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.LINK  点击链接跳转列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function linkColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.LINK>, row) {
      const item = getTableCellRenderValue(row, column);
      // 当url为空时，使用textColumnFormatter渲染为普通 text 文本样式
      if (!item?.url) {
        const textColumn = {
          ...column,
          getRenderValue: () => item?.alias,
        };
        return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
      }
      return (
        <div class='explore-col explore-link-col '>
          <a
            style={{ color: 'inherit' }}
            href={item.url}
            rel='noreferrer'
            target='_blank'
          >
            <div class={`explore-link-text ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
              <span>{item.alias}</span>
            </div>
            <i class='icon-monitor icon-mc-goto' />
          </a>
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.TAGS 类型文本类型表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function tagsColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>, row) {
      const tags = getTableCellRenderValue(row, column);
      if (!tags?.length) {
        const textColumn = {
          ...column,
          getRenderValue: () => defaultTableConfig.emptyPlaceholder,
        };
        return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row);
      }
      return (
        <div class='explore-col explore-tags-col '>
          {tags.map(tag => (
            <div
              key={tag.alias}
              style={{
                '--tag-color': tag.tagColor,
                '--tag-bg-color': tag.tagBgColor,
              }}
              class='tag-item'
            >
              <span
                class={`${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
                data-cell-source={tag.alias}
                data-col-key={column.colKey}
              >
                {tag.alias}
              </span>
            </div>
          ))}
        </div>
      );
    }

    /**
     * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function textColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row) {
      const alias = getTableCellRenderValue(row, column);
      const value = row?.[column.colKey];
      return (
        <div class={`explore-col explore-text-col ${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}`}>
          <span
            class={`explore-col-text ${ENABLED_TABLE_CONDITION_MENU_CLASS_NAME}`}
            data-cell-source={JSON.stringify(value || '')}
            data-col-key={column.colKey}
          >
            {alias == null || alias === '' ? defaultTableConfig.emptyPlaceholder : alias}
          </span>
        </div>
      );
    }

    /**
     * @description 根据列类型，获取对应的表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function handleSetFormatter(column, row) {
      switch (column.renderType) {
        case ExploreTableColumnTypeEnum.CLICK:
          return clickColumnFormatter(column, row);
        case ExploreTableColumnTypeEnum.PREFIX_ICON:
          return iconColumnFormatter(column, row);
        case ExploreTableColumnTypeEnum.TIME:
          return timeColumnFormatter(column, row);
        case ExploreTableColumnTypeEnum.DURATION:
          return durationColumnFormatter(column, row);
        case ExploreTableColumnTypeEnum.LINK:
          return linkColumnFormatter(column, row);
        case ExploreTableColumnTypeEnum.TAGS:
          return tagsColumnFormatter(column, row);
        default:
          return textColumnFormatter(column, row);
      }
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
            ...this.tableDisplayColumns,
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
            conditionKey={this.activeConditionMenuTarget.conditionKey}
            conditionValue={this.activeConditionMenuTarget.conditionValue}
            onConditionChange={this.handleConditionChange}
            onMenuClick={this.handleMenuClick}
          />
        </div>
        {this.statisticsDomRender()}
      </div>
    );
  },
});
