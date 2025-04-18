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
import { defineComponent, ref as deepRef, shallowRef, computed, reactive, onMounted, type PropType, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { OverflowTitle } from 'bkui-vue';
import { PrimaryTable } from 'tdesign-vue-next';

import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { formatDate, formatDuration, formatTime } from '../../../../components/trace-view/utils/date';
import { useTraceExploreStore } from '../../../../store/modules/explore';
import ExploreFieldSetting from '../explore-field-setting/explore-field-setting';
import ExploreSpanSlider from '../explore-span-slider/explore-span-slider';
import ExploreTraceSlider from '../explore-trace-slider/explore-trace-slider';
import ExploreTableEmpty from './explore-table-empty';
import {
  type ExploreTableColumn,
  ExploreTableColumnTypeEnum,
  ExploreTableLoadingEnum,
  type GetTableCellRenderValue,
  type TableFilterChangeEvent,
  type TableSort,
} from './typing';
import { getTableList, SERVICE_STATUS_COLOR_MAP, SPAN_KIND_MAPS, TABLE_DEFAULT_CONFIG } from './utils';

import type { ICommonParams } from '../../typing';

import './trace-explore-table.scss';

export default defineComponent({
  name: 'TraceExploreTable',
  props: {
    /** 当前激活的视角（trace/span） */
    mode: {
      type: String as PropType<'span' | 'trace'>,
      required: true,
    },
    /** 当前选中的应用 Name */
    appName: {
      type: String,
    },
    /** 当前选中的应用 Name */
    timeRange: {
      type: Array as PropType<string[]>,
    },
    /** 接口请求配置参数 */
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    /** table 默认配置项 */
    const { tableConfig: defaultTableConfig, traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;
    /** 表格单页条数 */
    const limit = 50;
    /** 表格logs数据请求中止控制器 */
    let abortController: AbortController = null;

    /** table 数据总条数 */
    const tableTotal = shallowRef(0);
    /** table 显示列配置 */
    const displayColumnFields = deepRef<string[]>([]);
    /** 当前需要打开的抽屉类型(trace详情抽屉/span详情抽屉) */
    const sliderMode = shallowRef<'' | 'span' | 'trace'>('');
    /** 打开抽屉所需的数据Id(traceId/spanId) */
    const activeSliderId = shallowRef('');
    /** 表格行可用作 唯一主键值 的字段名 */
    const tableRowKeyField = shallowRef('trace_id');
    /** table loading 配置 */
    const tableLoading = reactive({
      /** table 骨架屏 loading */
      [ExploreTableLoadingEnum.REFRESH]: false,
      /** 表格触底加载更多 loading  */
      [ExploreTableLoadingEnum.SCROLL]: false,
    });
    /** 表格列排序配置 */
    const sortContainer = reactive<TableSort>({
      field: '',
      order: null,
    });

    /** 当前视角是否为 Span 视角 */
    const isSpanVisual = computed(() => props.mode === 'span');
    /** table 数据（所有请求返回的数据） */
    const tableData = computed(() => store.tableList);
    /** 当前表格需要渲染的数据(根据图标耗时统计面板过滤后的数据) */
    const tableViewData = computed(() => store.tableList);
    /** 判断当前数据是否需要触底加载更多 */
    const tableHasScrollLoading = computed(() => tableData.value?.length < tableTotal.value);
    /** table 所有列配置(字段设置使用) */
    const tableColumns = computed(() => {
      const columnMap = getTableColumnMapByVisualMode();
      return Object.values(columnMap);
    });
    /** table 显示列配置 */
    const tableDisplayColumns = computed<ExploreTableColumn<ExploreTableColumnTypeEnum>[]>(() => {
      const columnMap = getTableColumnMapByVisualMode();
      return displayColumnFields.value.map(field => columnMap[field]).filter(Boolean);
    });
    /** 请求参数 */
    const queryParams = computed(() => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const [start_time, end_time] = handleTransformToTimestamp(props.timeRange);
      if (!props.commonParams?.app_name || !start_time || !end_time) {
        return null;
      }
      let sort = [];
      if (sortContainer.field && sortContainer.order) {
        sort = [`${sortContainer.order === 'desc' ? '-' : ''}${sortContainer.field}`];
      }
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { mode, query_string, ...params } = props.commonParams;
      return {
        ...params,
        query: query_string,
        sort,
        start_time,
        end_time,
      };
    });

    watch(
      () => isSpanVisual.value,
      () => {
        store.updateTableList([]);
        tableRowKeyField.value = isSpanVisual.value ? 'span_id' : 'trace_id';
        getColumn();
      }
    );

    watch(
      () => queryParams.value,
      () => {
        getExploreList();
      }
    );

    onMounted(() => {
      getColumn();
      getExploreList();
    });

    /**
     * @description 根据当前激活的视角(trace/span)获取对应的table表格列配置
     *
     */
    function getTableColumnMapByVisualMode(): Record<string, ExploreTableColumn<ExploreTableColumnTypeEnum>> {
      if (isSpanVisual.value) {
        return {
          span_id: {
            type: ExploreTableColumnTypeEnum.CLICK,
            field: 'span_id',
            alias: t('Span ID'),
            minWidth: 160,
            sortable: true,
            clickCallback: row => handleSliderShowChange('span', row.span_id),
          },
          span_name: {
            type: ExploreTableColumnTypeEnum.TEXT,
            field: 'span_name',
            alias: t('接口名称'),
            minWidth: 200,
            filter: [],
          },
          start_time: {
            type: ExploreTableColumnTypeEnum.TIME,
            field: 'start_time',
            alias: t('开始时间'),
            minWidth: 140,
            sortable: true,
          },
          end_time: {
            type: ExploreTableColumnTypeEnum.TIME,
            field: 'end_time',
            alias: t('结束时间'),
            minWidth: 140,
            sortable: true,
          },
          elapsed_time: {
            type: ExploreTableColumnTypeEnum.DURATION,
            field: 'elapsed_time',
            alias: t('耗时'),
            minWidth: 100,
            sortable: true,
          },
          'status.code': {
            type: ExploreTableColumnTypeEnum.PREFIX_ICON,
            field: 'status.code',
            alias: t('状态'),
            minWidth: 100,
            filter: [],
            getRenderValue: row => {
              const alias = row?.status_code?.value;
              const type = row?.status_code?.type;
              return {
                alias,
                prefixIcon: `status-code-icon-${type}`,
              };
            },
          },
          kind: {
            type: ExploreTableColumnTypeEnum.PREFIX_ICON,
            field: 'kind',
            alias: t('类型'),
            minWidth: 100,
            filter: [],
            getRenderValue: row => SPAN_KIND_MAPS[row.kind],
          },
          'resource.service.name': {
            type: ExploreTableColumnTypeEnum.LINK,
            field: 'resource.service.name',
            alias: t('所属服务'),
            minWidth: 160,
            filter: [],
            getRenderValue: row => getJumpToApmLinkItem(row?.resource?.['service.name']),
          },
          'resource.bk.instance.id': {
            type: ExploreTableColumnTypeEnum.TEXT,
            field: 'resource.bk.instance.id',
            alias: t('实例 ID'),
            minWidth: 160,
            filter: [],
            getRenderValue: row => row?.resource?.['bk.instance.id'],
          },
          'resource.telemetry.sdk.name': {
            type: ExploreTableColumnTypeEnum.TEXT,
            field: 'resource.telemetry.sdk.name',
            alias: t('SDK 名称'),
            minWidth: 160,
            getRenderValue: row => row?.resource?.['telemetry.sdk.name'],
          },
          'resource.telemetry.sdk.version': {
            type: ExploreTableColumnTypeEnum.TEXT,
            field: 'resource.telemetry.sdk.version',
            alias: t('SDK 版本'),
            minWidth: 160,
            filter: [],
            getRenderValue: row => row?.resource?.['telemetry.sdk.version'],
          },
          trace_id: {
            type: ExploreTableColumnTypeEnum.CLICK,
            field: 'trace_id',
            alias: t('所属Trace'),
            minWidth: 240,
            clickCallback: row => handleSliderShowChange('trace', row.trace_id),
          },
        };
      }
      return {
        trace_id: {
          type: ExploreTableColumnTypeEnum.CLICK,
          field: 'trace_id',
          alias: t('Trace ID'),
          minWidth: 240,
          clickCallback: row => handleSliderShowChange('trace', row.trace_id),
        },
        min_start_time: {
          type: ExploreTableColumnTypeEnum.TIME,
          field: 'min_start_time',
          alias: t('开始时间'),
          minWidth: 140,
        },
        root_span_name: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_span_name',
          alias: t('根Span'),
          minWidth: 160,
          filter: [],
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_service',
          alias: t('入口服务'),
          minWidth: 160,
          filter: [],
          getRenderValue: row => getJumpToApmLinkItem(row?.root_service),
        },
        root_service_span_name: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_service_span_name',
          alias: t('入口接口'),
          minWidth: 160,
          filter: [],
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service_category: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'root_service_category',
          alias: t('调用类型'),
          minWidth: 120,
          filter: [],
          getRenderValue: row => row?.root_service_category?.text,
        },
        root_service_status_code: {
          type: ExploreTableColumnTypeEnum.TAGS,
          field: 'root_service_status_code',
          alias: t('状态码'),
          minWidth: 100,
          filter: [],
          getRenderValue: row => {
            const alias = row?.root_service_status_code?.value as string;
            if (!alias) return [];
            const type = row?.root_service_status_code?.type;
            return [
              {
                alias: alias,
                ...SERVICE_STATUS_COLOR_MAP[type],
              },
            ];
          },
        },
        trace_duration: {
          type: ExploreTableColumnTypeEnum.DURATION,
          field: 'trace_duration',
          alias: t('耗时'),
          minWidth: 100,
          sortable: true,
        },
        'kind_statistics.sync': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.sync',
          alias: t('同步Span数量'),
          minWidth: 130,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.sync || 0,
        },
        'kind_statistics.async': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.async',
          alias: t('异步Span数量'),
          minWidth: 130,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.async || 0,
        },
        'kind_statistics.interval': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.interval',
          alias: t('内部Span数量'),
          minWidth: 130,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.interval || 0,
        },
        'kind_statistics.unspecified': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.unspecified',
          alias: t('未知Span数量'),
          minWidth: 130,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.unspecified || 0,
        },
        'category_statistics.db': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.db',
          alias: t('DB 数量'),
          minWidth: 100,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.db || 0,
        },
        'category_statistics.messaging': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.messaging',
          alias: t('Messaging 数量'),
          minWidth: 136,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.messaging || 0,
        },
        'category_statistics.http': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.http',
          alias: t('HTTP 数量'),
          minWidth: 110,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.http || 0,
        },
        'category_statistics.rpc': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.rpc',
          alias: t('RPC 数量'),
          minWidth: 100,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.rpc || 0,
        },
        'category_statistics.async_backend': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.async_backend',
          alias: t('Async 数量'),
          minWidth: 110,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.async_backend || 0,
        },
        'category_statistics.other': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.other',
          alias: t('Other 数量'),
          minWidth: 110,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.other || 0,
        },
        span_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'span_count',
          alias: t('Span 数量'),
          minWidth: 110,
          sortable: true,
        },
        hierarchy_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'hierarchy_count',
          alias: t('Span 层数'),
          minWidth: 110,
          sortable: true,
        },
        service_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'service_count',
          alias: t('服务数量'),
          minWidth: 100,
          sortable: true,
        },
      };
    }

    /**
     * @description: 获取 table 表格列配置
     *
     */
    function getColumn() {
      const defaultColumnsConfig = isSpanVisual.value ? spanConfig : traceConfig;
      // 需要展示的字段列名数组
      displayColumnFields.value = (defaultColumnsConfig?.displayFields || []) as string[];
    }

    /**
     * @description: 获取 table 表格数据
     *
     */
    async function getExploreList(loadingType = ExploreTableLoadingEnum.REFRESH) {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      if (!queryParams.value) {
        store.updateTableList([]);
        return;
      }
      let updateTableDataFn = list => {
        store.updateTableList([...tableData.value, ...list]);
      };

      if (loadingType === ExploreTableLoadingEnum.REFRESH) {
        store.updateTableList([]);
        updateTableDataFn = list => {
          store.updateTableList(list);
        };
      } else if (!tableHasScrollLoading.value) {
        return;
      }

      tableLoading[loadingType] = true;
      const requestParam = {
        ...queryParams.value,
        limit: limit,
        offset: tableData.value?.length || 0,
      };
      abortController = new AbortController();
      const res = await getTableList(requestParam, props.mode, {
        signal: abortController.signal,
      });

      tableLoading[loadingType] = false;

      updateTableDataFn(res.data);
    }

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
      const alias = row?.[column.field];
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

    /**
     * @description 表格排序回调
     * @param {string} sortEvent.field 排序字段名
     * @param {'asc' | 'desc' | null} sortEvent.order 排序方式
     *
     */
    function handleSortChange(sortEvent: TableSort) {
      let field = sortEvent.field;
      let order = sortEvent.order;
      if (!sortEvent.field || !sortEvent.order) {
        field = '';
        order = null;
      }
      sortContainer.field = field;
      sortContainer.order = order;
    }

    /**
     * @description 表格筛选回调
     * @param {string} filterChangeEvent.field 过滤字段名
     * @param {Array<boolean | number | string>} filterChangeEvent.values 过滤值
     *
     */
    function handleFilterChange(filterChangeEvent: TableFilterChangeEvent) {
      console.log('================ filterChangeEvent ================', filterChangeEvent);
    }

    /**
     * @description 表格列显示配置项变更回调
     *
     */
    function handleDisplayColumnFieldsChange(displayFields: string[]) {
      displayColumnFields.value = displayFields;
    }

    /**
     * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function textColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>, row) {
      const alias = getTableCellRenderValue(row, column);
      return (
        <div class='explore-col explore-text-col '>
          <OverflowTitle
            class='explore-col-text'
            placement='top'
            type='tips'
          >
            <span>{alias == null || alias === '' ? defaultTableConfig.emptyPlaceholder : alias}</span>
          </OverflowTitle>
        </div>
      );
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
     * @param e
     *
     */
    function handleSliderShowChange(openMode: '' | 'span' | 'trace', activeId: string) {
      activeSliderId.value = activeId;
      sliderMode.value = openMode;
    }

    /**
     * @description traceId详情抽屉 渲染方法
     *
     */
    function traceSliderRender() {
      return (
        <ExploreTraceSlider
          appName={props.appName}
          isShow={sliderMode.value === 'trace'}
          traceId={activeSliderId.value}
          onSliderClose={() => handleSliderShowChange('', '')}
        />
      );
    }

    /**
     * @description spanId详情抽屉 渲染方法
     *
     */
    function spanSliderRender() {
      return (
        <ExploreSpanSlider
          appName={props.appName}
          isShow={sliderMode.value === 'span'}
          spanId={activeSliderId.value}
          onSliderClose={() => handleSliderShowChange('', '')}
        />
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
      const getRenderValue = column?.getRenderValue || (row => row?.[column.field]);
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
        <div class='explore-col explore-click-col'>
          <OverflowTitle
            class='explore-click-text'
            placement='top'
            type='tips'
          >
            <span onClick={event => column?.clickCallback?.(row, column, event)}>{alias}</span>
          </OverflowTitle>
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

      return (
        <div class='explore-col explore-prefix-icon-col'>
          <i class={`prefix-icon ${prefixIcon}`} />
          <span>{alias}</span>
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
      const value = `${formatDate(+timestamp)} ${formatTime(+timestamp)}`;
      return (
        <div class='explore-col explore-time-col '>
          <OverflowTitle
            class='explore-time-text'
            placement='top'
            type='tips'
          >
            <span>{value}</span>
          </OverflowTitle>
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
      const value = formatDuration(+timestamp);
      return (
        <div class='explore-col explore-duration-col '>
          <OverflowTitle
            class='explore-duration-text'
            placement='top'
            type='tips'
          >
            <span>{value}</span>
          </OverflowTitle>
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
          <OverflowTitle
            class='explore-link-text'
            placement='top'
            type='tips'
          >
            <a
              style={{ color: 'inherit' }}
              href={item.url}
              rel='noreferrer'
              target='_blank'
            >
              {item.alias}
            </a>
          </OverflowTitle>
          <i class='icon-monitor icon-mc-goto' />
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
              <span>{tag.alias}</span>
            </div>
          ))}
        </div>
      );
    }

    /**
     * @description 根据列类型，获取对应的表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function handleSetFormatter(column, row) {
      switch (column.type) {
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
    return {
      defaultTableConfig,
      tableRowKeyField,
      displayColumnFields,
      tableColumns,
      tableDisplayColumns,
      tableViewData,
      traceSliderRender,
      spanSliderRender,
      handleSortChange,
      handleFilterChange,
      handleDataSourceConfigClick,
      handleSetFormatter,
      handleDisplayColumnFieldsChange,
    };
  },

  render() {
    return (
      <div class='trace-explore-table'>
        <ExploreFieldSetting
          fieldMap={{}}
          sourceList={this.tableColumns}
          targetList={this.displayColumnFields}
          onConfirm={this.handleDisplayColumnFieldsChange}
        />
        <PrimaryTable
          v-slots={{
            empty: () => <ExploreTableEmpty onDataSourceConfigClick={this.handleDataSourceConfigClick} />,
          }}
          columns={this.tableDisplayColumns.map(column => {
            return {
              ...column,
              colKey: column.field,
              title: column.alias,
              width: column.minWidth,
              sorter: column.sortable,
              sortType: column.sortable ? 'all' : undefined,
              ellipsis: false,
              resizable: true,
              filter: {
                list: Array(10)
                  .fill(1)
                  .map(i => ({
                    label: `filter-${i}`,
                    value: `filter-${i}`,
                  })),
                type: column.filterMultiple ? 'multiple' : 'single',
              },
              cell: (h, { row }) => {
                return this.handleSetFormatter(column, row);
              },
            };
          })}
          activeRowType='single'
          data={this.tableViewData}
          headerAffixedTop={true}
          hover={true}
          resizable={true}
          rowKey={this.tableRowKeyField}
          size='small'
          stripe={false}
          tableLayout='fixed'
        />
        {this.traceSliderRender()}
        {this.spanSliderRender()}
      </div>
    );
  },
});
