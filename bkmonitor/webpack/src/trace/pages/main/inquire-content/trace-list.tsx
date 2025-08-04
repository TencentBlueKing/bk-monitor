/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
  KeepAlive,
  nextTick,
  onBeforeUnmount,
  onMounted,
  onUnmounted,
  provide,
  reactive,
  ref,
  shallowRef,
  toRefs,
  watch,
} from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Checkbox, Loading, Popover, Radio, Sideslider, Table } from 'bkui-vue';
import { CancelToken } from 'monitor-api/cancel';
import { listOptionValues, spanDetail, traceDetail } from 'monitor-api/modules/apm_trace';
import { random } from 'monitor-common/utils/utils';
import { echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import transformTraceTree from '../../../components/trace-view/model/transform-trace-data';
import { formatDate, formatDuration, formatTime } from '../../../components/trace-view/utils/date';
import TimeSeries from '../../../plugins/charts/time-series/time-series';
import { useTimeRangeInject } from '../../../plugins/hooks';
import { QUERY_TRACE_RELATION_APP, SPAN_KIND_MAPS } from '../../../store/constant';
import { useSearchStore } from '../../../store/modules/search';
import { type ListType, useTraceStore } from '../../../store/modules/trace';
import SpanDetails from '../span-details';
// import SimpleList from './simple-list/simple-list';
import TraceDetail from './trace-detail';
import TraceDetailHeader from './trace-detail-header';

import type { PanelModel } from '../../../plugins/typings';
import type { IAppItem, ISpanListItem, ITraceListItem } from '../../../typings';

import './trace-list.scss';

type AliasMapType = {
  [key: string]: string;
};

const fieldQueryKeyMaps: AliasMapType = {
  entryService: 'root_service',
  entryEndpoint: 'root_service_span_name',
  statusCode: 'root_service_status_code',
  type: 'root_service_category',
  service_name: 'resource.service.name',
  status_code: 'status.code',
};

enum SpanFilter {
  EntrySpan = 'entry_span',
  Error = 'error',
  RootSpan = 'root_span',
  // 第二期：后端未提供该参数，先占个位。
  ThirdPart = '3',
}

enum TraceFilter {
  Error = 'error',
}

export type TraceListType = {
  // 属于 Span 列表的
  kind: any[];
  'resource.bk.instance.id': any[];
  'resource.service.name': any[];
  'resource.telemetry.sdk.version': any[];
  // 属于 Trace 列表的
  root_service: any[];
  root_service_category: any[];
  root_service_span_name: any[];
  root_service_status_code: any[];
  root_span_name: any[];
  span_name: any[];
  'status.code': any[];
};

export default defineComponent({
  name: 'TraceList',
  props: {
    tableLoading: {
      type: Boolean,
      default: false,
    },
    appName: {
      type: String,
      required: true,
    },
    appList: {
      type: Array as PropType<IAppItem[]>,
      default: () => [],
    },
    traceColumnFilters: {
      type: Object as PropType<Record<string, string[]>>,
      default: () => {},
    },
  },
  emits: [
    'scrollBottom',
    'statusChange',
    'sortChange',
    'columnFilterChange',
    'listTypeChange',
    'columnSortChange',
    'traceTypeChange',
    'spanTypeChange',
    'interfaceStatisticsChange',
    'serviceStatisticsChange',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 取消请求方法 */
    let listOptionCancelFn = () => {};
    let searchCancelFn = () => {};
    const route = useRoute();
    const router = useRouter();
    const store = useTraceStore();
    const searchStore = useSearchStore();
    const statusList = [
      { id: 'have_root_span', name: 'root span', tips: t('包含根span的trace') },
      { id: 'have_service_span', name: 'entry span', tips: t('包含至少一个服务的trace') },
    ];
    const state = reactive({
      total: 24,
      duration: 207,
      collapseActive: true,
      currentStatus: 'all',
    });
    const traceTableMain = ref<HTMLDivElement>();
    const traceListWrapper = ref<HTMLDivElement>();
    const chartContent = ref<HTMLDivElement>();
    const traceTableElem = ref<HTMLDivElement>();
    const traceTableContainer = ref<HTMLDivElement>();
    const traceDetailElem = ref(TraceDetail);
    // const simpleListElem = ref(SimpleList);
    const isFullscreen = ref(false);
    const height = ref<number>(0);
    const curTraceId = ref<string>('');
    const curTraceIndex = ref<number>(-1);
    const renderKey = ref<string>(random(6));
    const shouldResetTable = ref<boolean>(false);
    const columnFilters = ref<Record<string, string[]>>({});
    const selectedTraceType = ref([]);
    const selectedSpanType = ref([]);
    /** 侧栏全屏 */
    const slideFullScreen = shallowRef(false);
    const timeRange = useTimeRangeInject();
    provide('isFullscreen', isFullscreen);

    const selectedListType = computed(() => store.listType);
    /* 表格数据 */
    const tableData = computed(() => store.traceList);
    const filterSpanTableData = computed(() => store.filterSpanList);
    const tableDataOfSpan = computed(() =>
      filterSpanTableData.value?.length ? filterSpanTableData.value : store.spanList
    );
    const filterTableData = computed(() => store.filterTraceList);
    const localTableData = computed(() => (filterTableData.value?.length ? filterTableData.value : tableData.value));
    const simpleTraceList = computed(() => {
      return (localTableData.value || []).map(item => ({
        id: item.trace_id,
        duration: item.duration,
        startTime: `${formatDate(item.min_start_time)} ${formatTime(item.min_start_time)}`,
        isError: item.error,
      }));
    });
    const showTraceDetail = computed(() => store.showTraceDetail);
    const totalCount = computed(() => store.totalCount);
    const isPreCalculationMode = computed(() => store.traceListMode === 'pre_calculation');
    const tableColumns = computed(() => [
      {
        label: () => (
          <div class='trace-id-column-head'>
            <Popover
              content='trace_id'
              placement='right'
              popoverDelay={[500, 0]}
              theme='light'
            >
              <span class='th-label'>Trace ID</span>
            </Popover>
          </div>
        ),
        // settingsLabel 字段为非官方字段，这里先保留，后续优化代码会用到。20230510
        settingsLabel: 'Trace ID',
        settingsDisabled: true,
        field: 'traceID',
        width: showTraceDetail.value ? 248 : 160,
        render: ({ cell, data, index }: { cell: string; data: ITraceListItem; index: number }) => (
          <div
            style={`width:${showTraceDetail.value ? '232px' : 'auto'}`}
            class='trace-id-column'
            onClick={() => handleTraceDetail(data.trace_id, index)}
          >
            <div
              class='trace-id link-text'
              title={cell}
            >
              {cell}
            </div>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='min_start_time'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('开始时间')}</span>
          </Popover>
        ),
        width: 160,
        field: 'min_start_time',

        render: ({ cell }: { cell: number }) => (
          <div>
            <span>{`${formatDate(cell)} ${formatTime(cell)}`}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content={t('整个 Trace 的第一个 Span')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('根 Span')}</span>
          </Popover>
        ),
        field: 'root_span_name',
        filter: isPreCalculationMode.value
          ? {
              list: traceListFilter.root_span_name,
              filterFn: () => true as any,
              // btnSave: !!traceListFilter.root_span_name.length ? t('确定') : false
            }
          : false,

        render: ({ cell, data }: { cell: string; data: ITraceListItem }) => (
          <div class='link-column'>
            <span
              class='link-text link-server'
              onClick={() => handleOpenEndpoint(cell, data?.root_service)}
            >
              <span title={cell}>{cell}</span>
            </span>
            <i class='icon-monitor icon-fenxiang' />
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content={t('服务端进程的第一个 Service')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('入口服务')}</span>
          </Popover>
        ),
        settingsLabel: `${t('入口服务')}`,
        field: 'entryService',
        filter: isPreCalculationMode.value
          ? {
              list: traceListFilter.root_service,
              filterFn: () => true as any,
              // btnSave: !!traceListFilter.root_service.length ? t('确定') : false
            }
          : false,
        render: ({ cell, data }: { cell: string; data: ITraceListItem }) => [
          cell ? (
            <div
              key={cell}
              class='link-column'
            >
              <span
                class='link-text link-server'
                onClick={() => handleOpenService(cell)}
              >
                {data.error ? <span class='icon-monitor icon-mind-fill' /> : undefined}
                <span title={cell}>{cell}</span>
              </span>
              <i class='icon-monitor icon-fenxiang' />
            </div>
          ) : (
            '--'
          ),
        ],
      },
      {
        label: () => (
          <Popover
            content={t('入口服务的第一个接口')}
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('入口接口')}</span>
          </Popover>
        ),
        settingsLabel: `${t('入口接口')}`,
        field: 'root_service_span_name',
        filter: isPreCalculationMode.value
          ? {
              list: traceListFilter.root_service_span_name,
              filterFn: () => true as any,
              // btnSave: !!traceListFilter.root_service_span_name.length ? t('确定') : false
            }
          : false,
        render: ({ cell, data }: { cell: string; data: ITraceListItem }) => [
          cell ? (
            <div
              key={cell}
              class='link-column'
            >
              <span
                class='link-text link-server'
                onClick={() => handleOpenEndpoint(cell, data?.root_service)}
              >
                <span title={cell}>{cell}</span>
              </span>
              <i class='icon-monitor icon-fenxiang' />
            </div>
          ) : (
            '--'
          ),
        ],
      },
      {
        label: () => (
          <Popover
            content='root_service_category'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('调用类型')}</span>
          </Popover>
        ),
        settingsLabel: `${t('调用类型')}`,
        field: 'root_service_category',
        width: 120,

        render: ({ cell, data }: { cell: { text: string; value: string }; data: ITraceListItem }) => (
          <div>{cell.text || '--'}</div>
        ),
        filter: isPreCalculationMode.value
          ? {
              list: traceListFilter.root_service_category,
              filterFn: () => true as any,
              // btnSave: !!traceListFilter.root_service_category.length ? t('确定') : false
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='root_service_status_code'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('状态码')}</span>
          </Popover>
        ),
        settingsLabel: `${t('状态码')}`,
        width: 120,
        field: 'statusCode',
        filter: {
          list: traceListFilter.root_service_status_code,
          filterFn: () => true as any,
          // btnSave: !!traceListFilter.root_service_status_code.length ? t('确定') : false
        },

        render: ({ cell, data }: { cell: number; data: ITraceListItem }) => (
          <div class={`status-code status-${data.root_service_status_code?.type}`}>
            {data.root_service_status_code?.value || '--'}
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='trace_duration'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('耗时')}</span>
          </Popover>
        ),
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
        settingsLabel: `${t('耗时')}`,
        field: 'trace_duration',

        render: ({ cell, data }: { cell: number; data: ITraceListItem }) => (
          <div>
            <span>{formatDuration(cell)}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='kind_statistics.sync'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('同步Span数量')}</span>
          </Popover>
        ),
        // minWidth 的作用是强行撑开整个 label ，不然由于组件 bug 的存在，会导致全部字段在展示时会把这类字段内容给遮挡
        minWidth: 120,
        settingsLabel: `${t('同步Span数量')}`,
        field: 'kind_statistics.sync',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='kind_statistics.async'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('异步Span数量')}</span>
          </Popover>
        ),
        minWidth: 120,
        settingsLabel: `${t('异步Span数量')}`,
        field: 'kind_statistics.async',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='kind_statistics.interval'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('内部Span数量')}</span>
          </Popover>
        ),
        minWidth: 120,
        settingsLabel: `${t('内部Span数量')}`,
        field: 'kind_statistics.interval',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='kind_statistics.unspecified'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('未知Span数量')}</span>
          </Popover>
        ),
        minWidth: 120,
        settingsLabel: `${t('未知Span数量')}`,
        field: 'kind_statistics.unspecified',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.db'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('DB 数量')}</span>
          </Popover>
        ),
        settingsLabel: `${t('DB 数量')}`,
        field: 'category_statistics.db',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.messaging'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Messaging 数量')}</span>
          </Popover>
        ),
        minWidth: 120,
        settingsLabel: `${t('Messaging 数量')}`,
        field: 'category_statistics.messaging',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.http'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('HTTP 数量')}</span>
          </Popover>
        ),
        settingsLabel: `${t('HTTP 数量')}`,
        field: 'category_statistics.http',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.rpc'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('RPC 数量')}</span>
          </Popover>
        ),
        settingsLabel: `${t('RPC 数量')}`,
        field: 'category_statistics.rpc',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.async_backend'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Async 数量')}</span>
          </Popover>
        ),
        minWidth: 120,
        settingsLabel: `${t('Async 数量')}`,
        field: 'category_statistics.async_backend',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='category_statistics.other'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Other 数量')}</span>
          </Popover>
        ),
        settingsLabel: `${t('Other 数量')}`,
        field: 'category_statistics.other',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='span_count'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Span 数量')}</span>
          </Popover>
        ),
        settingsLabel: `${t('Span 数量')}`,
        field: 'span_count',
        width: 120,
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='hierarchy_count'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('Span 层数')}</span>
          </Popover>
        ),
        width: 120,
        settingsLabel: `${t('Span 层数')}`,
        field: 'hierarchy_count',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
      {
        label: () => (
          <Popover
            content='service_count'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('服务数量')}</span>
          </Popover>
        ),
        width: 120,
        settingsLabel: `${t('服务数量')}`,
        field: 'service_count',
        sort: isPreCalculationMode.value
          ? {
              sortFn: () => false,
            }
          : false,
      },
    ]);
    const chartList = computed<PanelModel[]>(() => searchStore.chartPanelList);
    const isListLoading = computed<boolean>(() => store.loading);

    onUnmounted(() => {
      echartsDisconnect(searchStore.dashboardId);
      listOptionCancelFn();
    });

    const handleFullscreenChange = (flag: boolean) => {
      slideFullScreen.value = flag;
    };

    watch(
      () => route.query,
      () => {
        const selectedType = JSON.parse((route.query.selectedType as string) || '[]');
        switch (store.listType) {
          case 'trace':
            selectedTraceType.value = selectedType;
            break;
          case 'span':
            selectedSpanType.value = selectedType;
            break;
        }
        if (!route.query.incident_query) return;
        const spanInfo = JSON.parse(decodeURIComponent((route.query.incident_query as string) || '{}'));
        if (spanInfo.trace_id !== '') {
          // 打开trace详情侧滑
          nextTick(() => {
            isFullscreen.value = true;
            getTraceDetails(spanInfo.trace_id);
            setTimeout(() => {
              document.getElementById(spanInfo.span_id)?.scrollIntoView({ behavior: 'smooth' });
              console.log(spanInfo, document.getElementById(spanInfo.span_id));
            }, 2000);
          });
        }
      },
      { immediate: true }
    );

    // 当在 table header 上选择筛选并确定后执行的回调方法。
    const handleSpanFilter = (options: any) => {
      const {
        checked,
        column: { field },
      } = options;
      if (field === 'traceID') {
        // 第二期结束可以删掉该逻辑块
        const kind = checked.length > 1 || !checked.length ? 'all' : checked.toString();
        handleStatusChange(kind);
      } else {
        const key = fieldQueryKeyMaps[field] || field;
        if (columnFilters.value[key] && !checked.length) {
          delete columnFilters.value[key];
        } else if (!checked.length) {
          // 20230830由于组件不支持把 筛选的确认按钮 禁用，这里不处理未选择筛选项的情况。
          return;
        } else {
          columnFilters.value[key] = checked;
        }
        emit('columnFilterChange', columnFilters.value);
      }
    };
    const handleCollapse = () => {
      state.collapseActive = !state.collapseActive;
      nextTick(() => {
        handleClientResize();
      });
    };
    const handleStatusChange = (val: string) => {
      state.currentStatus = val;
      emit('statusChange', val);
    };
    const handleTraceDetail = async (traceId: string, index) => {
      // 当前全屏状态且点击的是当前trace
      if (traceId === curTraceId.value && isFullscreen.value) return;
      if (!isFullscreen.value) {
        // 当前未在全屏，则打开全屏弹窗
        curTraceIndex.value = index;
        isFullscreen.value = true;

        nextTick(() => getTraceDetails(traceId));
      } else {
        // 当前在全屏下则直接请求trace详情
        getTraceDetails(traceId);
      }
    };
    const getTraceDetails = async (traceId: string) => {
      searchCancelFn();
      curTraceId.value = traceId;
      store.setTraceDetail(true);
      store.setTraceLoaidng(true);

      const params: any = {
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        trace_id: traceId,
      };

      if (
        traceDetailElem.value?.activePanel !== 'statistics' &&
        (store.traceViewFilters.length > 1 ||
          (store.traceViewFilters.length === 1 && !store.traceViewFilters.includes('duration')))
      ) {
        const selects = store.traceViewFilters.filter(item => item !== 'duration' && item !== QUERY_TRACE_RELATION_APP); // 排除 耗时、跨应用追踪 选项
        params.displays = ['source_category_opentelemetry'].concat(selects);
      }
      if (traceDetailElem.value?.activePanel === 'timeline') {
        params[QUERY_TRACE_RELATION_APP] = store.traceViewFilters.includes(QUERY_TRACE_RELATION_APP);
      }
      await traceDetail(params, {
        cancelToken: new CancelToken((c: any) => (searchCancelFn = c)),
      })
        .then(async data => {
          await store.setTraceData({ ...data, appName: props.appName, trace_id: traceId });
          store.setTraceLoaidng(false);
        })
        .catch(() => null);
    };
    const handleCloseDetail = () => {
      if (!isFullscreen.value) return;
      handleDialogClose();
    };
    /** 新开页签入口服务 */
    const handleOpenService = (service: string) => {
      const hash = `#/apm/service?filter-service_name=${service}&filter-app_name=${props.appName}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    /** 新开页签接口 */
    const handleOpenEndpoint = (endpoint: string, service?: string) => {
      const hash = `#/apm/application?filter-service_name=${service}&filter-app_name=${props.appName}&sceneId=apm_application&sceneType=detail&dashboardId=endpoint&filter-endpoint_name=${endpoint}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    };
    const handleDialogClose = () => {
      isFullscreen.value = false;
      curTraceId.value = '';
      curTraceIndex.value = -1;
      console.log('handleDialogClose');
      // TODO: 开发模式下会卡一下，这里设置一秒后执行可以减缓这种情况。
      store.setTraceDetail(false);

      handleFullscreenChange(false);

      // 弹窗关闭时重置路由
      route.query?.incident_query &&
        router.replace({
          path: '/trace/home',
          query: {
            app_name: route.query?.app_name,
            refreshInterval: '-1',
            sceneMode: 'trace',
            start_time: 'now-1h',
            end_time: 'now',
            query: route.query?.query,
            filterMode: 'queryString',
          },
        });
    };
    const traceListFilter = reactive<TraceListType>({
      // 属于 Trace 列表的
      root_service: [],
      root_service_span_name: [],
      root_service_status_code: [],
      root_service_category: [],
      root_span_name: [],
      // 属于 Span 列表的
      kind: [],
      'resource.bk.instance.id': [],
      'resource.service.name': [],
      'resource.telemetry.sdk.version': [],
      span_name: [],
      'status.code': [],
    });
    /** 获取列表表头过滤候选值 */
    const getFilterValues = () => {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange?.value as string[]);
      // 由于 接口统计 的候选值和 span 视角一样，这里做一次转换。
      const modeMapping = {
        trace: 'trace',
        span: 'span',
      };
      const params = {
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        start_time: startTime,
        end_time: endTime,
        mode: modeMapping[selectedListType.value],
      };
      listOptionValues(params, {
        cancelToken: new CancelToken((c: any) => {
          listOptionCancelFn = c;
        }),
      }).then(res => {
        Object.keys(res).forEach(key => {
          // 该列表是全量获取的，每次添加时需要重置一下 filter 。
          if (traceListFilter[key]?.length) traceListFilter[key].length = 0;
          traceListFilter[key]?.push(...res[key]);
        });
      });
    };
    getFilterValues();
    function handleScrollBottom(arg: { bottom: number }) {
      // TODO：这里貌似不太严谨，会导致重复调用 scrollBottotm 事件。
      if (arg.bottom <= 2 || arg?.[0]?.bottom <= 2) {
        /* 到底了 */
        emit('scrollBottom');
      }
    }
    function handleClientResize() {
      const containerRect = traceListWrapper.value?.getBoundingClientRect();
      const chartRect = chartContent.value?.getBoundingClientRect();
      // 剩余放置表格内容的高度
      if (containerRect && chartRect) {
        const remainHeight = containerRect?.height - chartRect?.height;
        // // 如果剩余高度大于10行高度 或 表格无数据 则表格高度自适应剩余区域
        // if (remainHeight > LIMIT_TABLE_HEIGHT || !(localTableData.value?.length)) {
        //   height.value = remainHeight - 12; // 16是 margin 距离
        // } else { // 否则
        //   height.value = LIMIT_TABLE_HEIGHT;
        // }
        height.value = remainHeight - 24; // 24是 margin padding 距离;
      }
    }
    function handleSourceData() {
      const { appList, appName } = props;
      const name = appList.find(app => app.app_name === appName)?.app_name || '';
      if (name) {
        const hash = `#/apm/application/config/${name}?active=dataStatus`;
        const url = location.href.replace(location.hash, hash);
        window.open(url, '_blank');
      }
    }

    /**
     * Trace 或 Span 列表类型切换
     * 重新发起列表查询。
     */
    function handleListTypeChange(v: ListType) {
      if (!store.isTraceLoading) {
        store.setTraceLoading(true);
      }
      store.setListType(v);
      selectedTraceType.value.length = 0;
      // span 类型重置
      selectedSpanType.value.length = 0;
      // 表头筛选重置
      const filters = (props.traceColumnFilters[v] || []).filter(item => item.value?.length > 0) || [];
      const columnFiltersValue = filters.reduce((acc, item) => {
        acc[item.key] = item.value;
        return acc;
      }, {});

      columnFilters.value = filters.length > 0 ? columnFiltersValue : {};
      store.resetTable();
      emit('listTypeChange');
      getFilterValues();
    }

    function handleTraceTypeChange(v: string[]) {
      emit('traceTypeChange', v);
    }

    function handleSpanTypeChange(v: string[]) {
      emit('spanTypeChange', v);
    }

    watch(
      () => filterTableData.value,
      () => store.setTraceDetail(false)
    );
    watch(
      () => localTableData.value,
      () => handleClientResize(),
      { immediate: true }
    );
    watch([() => props.appName, () => timeRange?.value], () => {
      shouldResetTable.value = true;
      getFilterValues();
    });
    watch(
      () => isListLoading.value,
      () => {
        traceTableElem.value?.scrollTo?.({ top: 0 });
        if (shouldResetTable.value) {
          renderKey.value = random(6);
          shouldResetTable.value = false;
        }
      }
    );

    const handleListPageKeydown = (evt: KeyboardEvent) => {
      if (evt.code === 'Escape') handleCloseDetail();
    };

    onMounted(() => {
      handleClientResize();
      addListener(traceListWrapper.value as HTMLDivElement, handleClientResize);
      traceListWrapper.value?.addEventListener('keydown', handleListPageKeydown);
    });

    onBeforeUnmount(() => {
      removeListener(traceListWrapper.value as HTMLDivElement, handleClientResize);
      traceListWrapper.value?.removeEventListener('keydown', handleListPageKeydown);
    });

    // Span List 相关
    const tableColumnOfSpan = [
      {
        label: () => (
          <Popover
            content='span_id'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>Span ID</span>
          </Popover>
        ),
        width: 140,
        field: 'span_id',
        sort: {
          sortFn: () => false,
        },

        render: ({ cell, data }: { cell: string; data: any[] }) => (
          <div
            class='link-column'
            onClick={() => handleShowSpanDetail(data)}
          >
            <span
              class='link-text'
              title={cell}
            >
              {cell}
            </span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='span_name'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('接口名称')}</span>
          </Popover>
        ),
        field: 'span_name',
        filter: {
          list: traceListFilter.span_name,
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: string; data: ISpanListItem }) => (
          <div>
            <span title={cell}>{cell}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='start_time'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('开始时间')}</span>
          </Popover>
        ),
        field: 'start_time',
        sort: {
          sortFn: () => false,
        },

        render: ({ cell, data }: { cell: number; data: ISpanListItem }) => (
          <div>
            <span>{`${formatDate(cell)} ${formatTime(cell)}`}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='end_time'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('结束时间')}</span>
          </Popover>
        ),
        field: 'end_time',
        sort: {
          sortFn: () => false,
        },

        render: ({ cell, data }: { cell: number; data: ISpanListItem }) => (
          <div>
            <span>{`${formatDate(cell)} ${formatTime(cell)}`}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='elapsed_time'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('耗时')}</span>
          </Popover>
        ),
        field: 'elapsed_time',
        width: 120,
        sort: {
          sortFn: () => false,
        },

        render: ({ cell, data }: { cell: number; data: ISpanListItem }) => (
          <div>
            <span>{formatDuration(cell, ' ')}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='status_code'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('状态')}</span>
          </Popover>
        ),
        field: 'status_code',
        width: 120,
        filter: {
          list: traceListFilter['status.code'],
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: number; data: ISpanListItem }) => (
          // TODO: 需要补上 圆点 样式
          <div style='display: flex; align-items: center'>
            <span class={`span-status-code-${data.status_code.type}`} />
            <span>{data.status_code.value}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='kind'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('类型')}</span>
          </Popover>
        ),
        field: 'kind',
        width: 150,
        filter: {
          list: traceListFilter.kind,
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: number; data: ISpanListItem }) => (
          <div>
            <span>{SPAN_KIND_MAPS[data.kind]}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='resource.service.name'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('所属服务')}</span>
          </Popover>
        ),
        field: 'resource.service.name',
        filter: {
          list: traceListFilter['resource.service.name'],
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: string; data: ISpanListItem }) => (
          <div
            class='link-column'
            onClick={() => handleOpenService(data.resource['service.name'])}
          >
            <span title={data.resource['service.name']}>{data.resource['service.name']}</span>
            <i class='icon-monitor icon-fenxiang' />
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='resource.bk.instance.id'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('实例 ID')}</span>
          </Popover>
        ),
        field: 'resource.bk.instance.id',
        filter: {
          list: traceListFilter['resource.bk.instance.id'],
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: string; data: ISpanListItem }) => (
          <div>
            {/* // eslint-disable-next-line @typescript-eslint/quotes */}
            <span title={data.resource['bk.instance.id']}>{data.resource['bk.instance.id']}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='resource.telemetry.sdk.name'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('SDK 名称')}</span>
          </Popover>
        ),
        field: 'resource.telemetry.sdk.name',

        render: ({ cell, data }: { cell: string; data: ISpanListItem }) => (
          <div>
            {/* // eslint-disable-next-line @typescript-eslint/quotes */}
            <span title={data.resource['telemetry.sdk.name']}>{data.resource['telemetry.sdk.name']}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='resource.telemetry.sdk.version'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('SDK 版本')}</span>
          </Popover>
        ),
        field: 'resource.telemetry.sdk.version',
        filter: {
          list: traceListFilter['resource.telemetry.sdk.version'],
          filterFn: () => true as any,
        },

        render: ({ cell, data }: { cell: string; data: ISpanListItem }) => (
          <div>
            {/* // eslint-disable-next-line @typescript-eslint/quotes */}
            <span title={data.resource['telemetry.sdk.version']}>{data.resource['telemetry.sdk.version']}</span>
          </div>
        ),
      },
      {
        label: () => (
          <Popover
            content='trace_id'
            placement='right'
            popoverDelay={[500, 0]}
            theme='light'
          >
            <span class='th-label'>{t('所属 Trace')}</span>
          </Popover>
        ),
        field: 'trace_id',

        render: ({ cell, data }: { cell: string; data: any[] }) => (
          <div class='link-column'>
            <span
              class='link-text'
              title={cell}
              onClick={() => handleToTraceQuery(cell)}
            >
              {cell}
            </span>
            <i class='icon-monitor icon-fenxiang' />
          </div>
        ),
      },
    ];

    const isSpanDetailLoading = ref(false);
    const isShowSpanDetail = ref(false);
    const spanDetails = reactive({});
    async function handleShowSpanDetail(span: any) {
      const params = {
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        span_id: span.span_id,
      };
      isShowSpanDetail.value = true;
      isSpanDetailLoading.value = true;
      await spanDetail(params)
        .then(result => {
          // TODO：这里是东凑西凑出来的数据，代码并不严谨，后期需要调整。
          store.setSpanDetailData(result);

          result.trace_tree.traceID = result?.trace_tree?.spans?.[0]?.traceID;
          Object.assign(spanDetails, transformTraceTree(result.trace_tree)?.spans?.[0]);
        })
        .catch(() => {})
        .finally(() => {
          isSpanDetailLoading.value = false;
        });
    }

    function handleTraceColumnSort(option: any) {
      emit('columnSortChange', {
        type: option.type,
        column: option.column,
      });
    }

    /** 跳转traceId精确查询 */
    function handleToTraceQuery(traceId: string) {
      const hash = `#/trace/home?app_name=${props.appName}&trace_id=${traceId}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank');
    }

    function handleTraceTableSettingsChange(settings: { checked: string[]; height: number; size: string }) {
      store.tableSettings.trace.checked = settings.checked;
      window.localStorage.setItem('traceCheckedSettings', JSON.stringify(settings.checked));
    }

    function handleSpanTableSettingsChange(settings: { checked: string[]; height: number; size: string }) {
      store.tableSettings.span.checked = settings.checked;
      window.localStorage.setItem('spanCheckedSettings', JSON.stringify(settings.checked));
    }

    return {
      ...toRefs(state),
      ...toRefs(props),
      tableColumns,
      traceListWrapper,
      height,
      chartContent,
      traceTableMain,
      traceTableElem,
      traceDetailElem,
      // simpleListElem,
      traceTableContainer,
      statusList,
      handleSpanFilter,
      handleCollapse,
      handleStatusChange,
      handleCloseDetail,
      handleScrollBottom,
      handleSourceData,
      chartList,
      isFullscreen,
      localTableData,
      simpleTraceList,
      curTraceId,
      showTraceDetail,
      totalCount,
      isListLoading,
      renderKey,
      selectedListType,
      selectedSpanType,
      handleListTypeChange,
      handleSpanTypeChange,
      tableColumnOfSpan,
      tableDataOfSpan,
      isSpanDetailLoading,
      isShowSpanDetail,
      spanDetails,
      slideFullScreen,
      handleFullscreenChange,
      handleTraceColumnSort,
      handleDialogClose,
      traceListFilter,
      selectedTraceType,
      handleTraceTypeChange,
      handleTraceTableSettingsChange,
      handleSpanTableSettingsChange,
      store,
      handleTraceDetail,
      t,
    };
  },

  render() {
    const tableEmptyContent = () => (
      <EmptyStatus type='search-empty'>
        <div class='search-empty-content'>
          <div class='tips'>{this.t('您可以按照以下方式优化检索结果')}</div>
          <div class='description'>
            1. {this.t('检查')}
            <span
              class='link'
              onClick={() => this.handleSourceData()}
            >
              {this.t('数据源配置')}
            </span>
            {this.t('情况')}
          </div>
          <div class='description'>2. {this.t('检查右上角的时间范围')}</div>
          <div class='description'>3. {this.t('是否启用了采样，采样不保证全量数据')}</div>
          <div class='description'>
            4. {this.t('优化查询语句')}
            <div class='sub-description'>{`${this.t('带字段全文检索更高效')}：log:abc`}</div>
            <div class='sub-description'>{`${this.t('模糊检索使用通配符')}：log:abc* ${this.t('或')} log:ab?c`}</div>
            <div class='sub-description'>{`${this.t('双引号匹配完整字符串')}: log:"ERROR MSG"`}</div>
            <div class='sub-description'>{`${this.t('数值字段范围匹配')}: count:[1 TO 5]`}</div>
            <div class='sub-description'>{`${this.t('正则匹配')}：name:/joh?n(ath[oa]n/`}</div>
            <div class='sub-description'>{`${this.t('组合检索注意大写')}：log: (error OR info)`}</div>
          </div>
          <div
            style='margin-top: 8px'
            class='description link'
          >
            {this.t('查看更多语法规则')}
            <span class='icon-monitor icon-fenxiang' />
          </div>
        </div>
      </EmptyStatus>
    );
    const traceTableContent = () => (
      <div
        key={this.renderKey}
        ref='traceTableContainer'
        class={`trace-content-table-wrap ${this.showTraceDetail ? 'is-show-detail' : ' '}`}
      >
        <KeepAlive>
          {this.store.isTraceLoading && !this.tableLoading ? (
            <TableSkeleton />
          ) : (
            <Table
              ref='traceTableElem'
              style='height: 100%'
              height='100%'
              class='trace-table'
              v-slots={{ empty: () => tableEmptyContent() }}
              rowStyle={(row: { traceID: string[] }) => {
                if (this.showTraceDetail && row?.traceID?.[0] === this.curTraceId) return { background: '#EDF4FF' };
                return {};
              }}
              // rowHeight={40}
              border={this.isFullscreen ? '' : ['outer']}
              columns={this.tableColumns}
              data={this.localTableData}
              scroll-loading={this.tableLoading}
              settings={this.store.tableSettings.trace}
              tabindex={-1}
              onColumnFilter={this.handleSpanFilter}
              onColumnSort={this.handleTraceColumnSort}
              onScrollBottom={this.handleScrollBottom}
              onSettingChange={this.handleTraceTableSettingsChange}
            />
          )}
        </KeepAlive>
      </div>
    );
    const spanTableContent = () => (
      <div class='trace-content-table-wrap'>
        <KeepAlive>
          {this.store.isTraceLoading && !this.tableLoading ? (
            <TableSkeleton />
          ) : (
            <Table
              ref='tableSpanElem'
              style='height: 100%'
              height='100%'
              class='table-span'
              border={['outer']}
              columns={this.tableColumnOfSpan}
              data={this.tableDataOfSpan}
              rowHeight={40}
              scroll-loading={this.tableLoading}
              settings={this.store.tableSettings.span}
              tabindex={-1}
              onColumnFilter={this.handleSpanFilter}
              onColumnSort={this.handleTraceColumnSort}
              onScrollBottom={this.handleScrollBottom}
              onSettingChange={this.handleSpanTableSettingsChange}
              // TODO：后期确认空数据的设计样式
              // v-slots={{ empty: () => tableEmptyContent() }}
            />
          )}
        </KeepAlive>
      </div>
    );

    return (
      <div
        ref='traceListWrapper'
        class='trace-list-wrapper'
      >
        <div
          ref='chartContent'
          class='chart-content'
        >
          <div
            class={`collapse-title ${this.collapseActive ? 'collapse-active' : ''}`}
            onClick={this.handleCollapse}
          >
            <span class='icon-monitor icon-mc-triangle-down' />
            <span>{this.t('总览')}</span>
          </div>
          {this.collapseActive && (
            <div class='chart-list'>
              {this.chartList.map(panel => (
                <TimeSeries
                  key={panel.id}
                  class='chart-list-item'
                  panel={panel}
                  isUseAlone
                  needChartLoading
                />
              ))}
            </div>
          )}
        </div>
        <div
          ref='traceTableMain'
          style={`height: ${this.height}px`}
          class={['trace-table-main', { 'is-fullscreen': this.isFullscreen }]}
        >
          <Loading
            class={`full-screen-loading ${this.isFullscreen ? 'is-active' : ''}`}
            loading={this.isFullscreen && this.isListLoading}
          >
            <div class='table-filter'>
              <Radio.Group
                v-model={this.selectedListType}
                onChange={this.handleListTypeChange}
              >
                <Radio.Button label='trace'>{this.t('Trace 视角')}</Radio.Button>
                <Radio.Button label='span'>{this.t('Span 视角')}</Radio.Button>
              </Radio.Group>

              {/* 20230816 列表的每一个子项都添加 key ，解决切换列表时可能会渲染异常的问题，这里用静态 key ，因为触发 checkbox.group 时会重新执行动态 key ，避免再一次重新渲染。  */}
              {this.selectedListType === 'trace' && (
                <div
                  key='trace-filter'
                  class='trace-filter'
                >
                  <span style='margin-right: 6px;'>{this.t('包含')}：</span>
                  <Checkbox.Group
                    v-model={this.selectedTraceType}
                    onChange={this.handleTraceTypeChange}
                  >
                    <Checkbox label={TraceFilter.Error}>{this.t('错误')}</Checkbox>
                  </Checkbox.Group>
                </div>
              )}

              {this.selectedListType === 'span' && (
                <div
                  key='span-filter'
                  class='span-filter'
                >
                  {/* 第二期没有 第三方、错误  */}
                  <span style='margin-right: 6px;'>{this.t('包含')}：</span>
                  <Checkbox.Group
                    v-model={this.selectedSpanType}
                    onChange={this.handleSpanTypeChange}
                  >
                    <Popover
                      content={this.t('整个 Trace 的第一个 Span')}
                      placement='top'
                      theme='light'
                    >
                      <Checkbox label={SpanFilter.RootSpan}>{this.t('根 Span')}</Checkbox>
                    </Popover>
                    <Popover
                      content={this.t('每个 Service 的第一个 Span')}
                      placement='top'
                      theme='light'
                    >
                      <Checkbox label={SpanFilter.EntrySpan}>{this.t('入口 Span')}</Checkbox>
                    </Popover>
                    {/* 20230816 后端未上线勿删 */}
                    {/* <Checkbox
                      label={SpanFilter.ThirdPart}
                      key={random(6)}
                    >
                      {this.t('第三方')}
                    </Checkbox> */}
                    <Checkbox label={SpanFilter.Error}>{this.t('错误')}</Checkbox>
                  </Checkbox.Group>
                </div>
              )}
            </div>
            {this.selectedListType === 'trace' && traceTableContent()}
            {this.selectedListType === 'span' && spanTableContent()}
          </Loading>
        </div>

        <SpanDetails
          isFullscreen={this.isFullscreen}
          isPageLoading={this.isSpanDetailLoading}
          show={this.isShowSpanDetail}
          spanDetails={this.spanDetails}
          onShow={v => (this.isShowSpanDetail = v)}
        />

        {/* <Dialog
          class='trace-info-fullscreen-dialog'
          esc-close={false}
          is-show={this.isFullscreen}
          fullscreen
          multi-instance
          onClosed={this.handleDialogClose}
        >
          <div style='height: 100%'>
            <SimpleList
              ref='simpleListElem'
              data={this.simpleTraceList}
              loading={this.tableLoading}
              selectedId={this.curTraceId}
              onChange={this.handleTraceDetail}
              onLoadMore={() => this.$emit('scrollBottom')}
            />
            <div class='detail-box fullsreen-box'>
              <TraceDetail
                ref='traceDetailElem'
                appName={appName}
                traceID={this.curTraceId}
                isInTable
                onClose={this.handleCloseDetail}
              />
            </div>
          </div>
        </Dialog> */}
        <Sideslider
          width={this.slideFullScreen ? '100%' : '85%'}
          class='trace-info-sideslider'
          v-slots={{
            header: () => (
              <TraceDetailHeader
                appName={this.appName}
                fullscreen={this.slideFullScreen}
                traceId={this.curTraceId}
                isInTable
                onFullscreenChange={this.handleFullscreenChange}
              />
            ),
          }}
          esc-close={false}
          is-show={this.isFullscreen}
          multi-instance
          transfer
          onClosed={this.handleDialogClose}
        >
          {/* <SimpleList
            ref='simpleListElem'`
            data={this.simpleTraceList}
            loading={this.tableLoading}
            selectedId={this.curTraceId}
            onChange={this.handleTraceDetail}
            onLoadMore={() => this.$emit('scrollBottom')}
          /> */}
          <div class='detail-box'>
            <TraceDetail
              ref='traceDetailElem'
              appName={this.appName}
              traceID={this.curTraceId}
              isInTable
              onClose={this.handleCloseDetail}
            />
          </div>
        </Sideslider>
      </div>
    );
  },
});
