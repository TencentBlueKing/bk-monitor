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
import { defineComponent, shallowRef, computed, reactive } from 'vue';
import { useI18n } from 'vue-i18n';

import { Table, TableColumn } from '@blueking/table';
import { OverflowTitle } from 'bkui-vue';
import Checkbox from 'bkui-vue/lib/checkbox';

import { formatDate, formatDuration, formatTime } from '../../../../components/trace-view/utils/date';
import {
  type ExploreTableColumn,
  ExploreTableColumnTypeEnum,
  type GetTableCellRenderValue,
  type TableFilterChangeEvent,
  type TableSort,
} from './typing';
import { SERVICE_STATUS_COLOR_MAP, TABLE_DEFAULT_CONFIG, TABLE_MOCK_DATA } from './utils';

import './trace-explore-table.scss';

/** 快速过滤项(包含) */
enum TableCheckBoxFiltersEnum {
  EntrySpan = 'entry',
  Error = 'error',
  RootSpan = 'root_span',
}

export default defineComponent({
  name: 'TraceExploreTable',
  props: {
    appName: {
      type: String,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { tableConfig: defaultTableConfig, traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;

    const visualMode = shallowRef('span');
    const checkboxFilters = reactive([]);

    const tableData = shallowRef(TABLE_MOCK_DATA);

    const tableColumns = computed(() => {
      const columnMap = getTableColumnMapByVisualMode();
      const defaultColumnsConfig = isSpanVisual.value ? spanConfig : traceConfig;
      // 需要展示的字段列名数组
      const displayColumns = defaultColumnsConfig?.displayFields || [];
      return displayColumns.map(field => columnMap[field]).filter(Boolean);
    });

    /** 当前视角是否为 Span 视角 */
    const isSpanVisual = computed(() => visualMode.value === 'span');
    /** 表格行可用作 唯一主键值 的字段名 */
    const tableRowKeyField = computed(() => {
      return isSpanVisual.value ? 'span_id' : 'trace_id';
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
            clickCallback: handleOpenSlider,
          },
          span_name: {
            type: ExploreTableColumnTypeEnum.TEXT,
            field: 'span_name',
            alias: t('接口名称'),
            minWidth: 180,
            filter: [],
          },
          start_time: {
            type: ExploreTableColumnTypeEnum.TIME,
            field: 'start_time',
            alias: t('开始时间'),
            minWidth: 160,
            sortable: true,
          },
          end_time: {
            type: ExploreTableColumnTypeEnum.TIME,
            field: 'end_time',
            alias: t('结束时间'),
            minWidth: 160,
            sortable: true,
          },
          elapsed_time: {
            type: ExploreTableColumnTypeEnum.DURATION,
            field: 'elapsed_time',
            alias: t('耗时'),
            minWidth: 140,
            sortable: true,
          },
          'status.code': {
            type: ExploreTableColumnTypeEnum.PREFIX_ICON,
            field: 'status.code',
            alias: t('状态'),
            minWidth: 140,
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
            minWidth: 140,
            filter: [],
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
            minWidth: 160,
            clickCallback: handleOpenSlider,
          },
        };
      }
      return {
        trace_id: {
          type: ExploreTableColumnTypeEnum.CLICK,
          field: 'trace_id',
          alias: t('Trace ID'),
          minWidth: 160,
          clickCallback: handleOpenSlider,
        },
        min_start_time: {
          type: ExploreTableColumnTypeEnum.TIME,
          field: 'min_start_time',
          alias: t('开始时间'),
          minWidth: 160,
        },
        root_span_name: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_span_name',
          alias: t('根Span'),
          minWidth: 180,
          filter: [],
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_service',
          alias: t('入口服务'),
          minWidth: 180,
          filter: [],
          getRenderValue: row => getJumpToApmLinkItem(row?.root_service),
        },
        root_service_span_name: {
          type: ExploreTableColumnTypeEnum.LINK,
          field: 'root_service_span_name',
          alias: t('入口接口'),
          minWidth: 180,
          filter: [],
          getRenderValue: getJumpToApmApplicationLinkItem,
        },
        root_service_category: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'root_service_category',
          alias: t('调用类型'),
          minWidth: 140,
          filter: [],
          getRenderValue: row => row?.root_service_category?.text,
        },
        root_service_status_code: {
          type: ExploreTableColumnTypeEnum.TAGS,
          field: 'root_service_status_code',
          alias: t('状态码'),
          minWidth: 140,
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
          minWidth: 140,
          sortable: true,
        },
        'kind_statistics.sync': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.sync',
          alias: t('同步Span数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.sync || 0,
        },
        'kind_statistics.async': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.async',
          alias: t('异步Span数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.async || 0,
        },
        'kind_statistics.interval': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.interval',
          alias: t('内部Span数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.interval || 0,
        },
        'kind_statistics.unspecified': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'kind_statistics.unspecified',
          alias: t('未知Span数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.kind_statistics?.unspecified || 0,
        },
        'category_statistics.db': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.db',
          alias: t('DB 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.db || 0,
        },
        'category_statistics.messaging': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.messaging',
          alias: t('Messaging 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.messaging || 0,
        },
        'category_statistics.http': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.http',
          alias: t('HTTP 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.http || 0,
        },
        'category_statistics.rpc': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.rpc',
          alias: t('RPC 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.rpc || 0,
        },
        'category_statistics.async_backend': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.async_backend',
          alias: t('Async 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.async_backend || 0,
        },
        'category_statistics.other': {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'category_statistics.other',
          alias: t('Other 数量'),
          minWidth: 140,
          sortable: true,
          getRenderValue: row => row?.category_statistics?.other || 0,
        },
        span_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'span_count',
          alias: t('Span 数量'),
          minWidth: 140,
          sortable: true,
        },
        hierarchy_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'hierarchy_count',
          alias: t('Span 层数'),
          minWidth: 140,
          sortable: true,
        },
        service_count: {
          type: ExploreTableColumnTypeEnum.TEXT,
          field: 'service_count',
          alias: t('服务数量'),
          minWidth: 140,
          sortable: true,
        },
      };
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

    function handleSpanTypeChange() {}

    /**
     * @description 表格排序回调
     * @param {string} sortEvent.field 排序字段名
     * @param {'asc' | 'desc' | null} sortEvent.order 排序方式
     *
     */
    function handleSortChange(sortEvent: TableSort) {
      console.log('================ sortEvent ================', sortEvent);
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
     * @description TraceId/SpanId 点击打开抽屉页
     * @param e
     *
     */
    function handleOpenSlider(e) {
      console.log('================ openSlider ================', e);
    }

    /**
     * @description table上方快捷筛选操作区域（ “包含” 区域中的 复选框组） 渲染方法
     *
     */
    function filtersCheckBoxGroupRender() {
      return (
        <Checkbox.Group
          v-model={checkboxFilters}
          onChange={handleSpanTypeChange}
        >
          <Checkbox
            v-bk-tooltips={{
              content: t('整个Trace的第一个Span'),
              placement: 'top',
              theme: 'light',
            }}
            label={TableCheckBoxFiltersEnum.RootSpan}
          >
            {t('根Span')}
          </Checkbox>
          <Checkbox
            v-bk-tooltips={{
              content: t('每个Service的第一个Span'),
              placement: 'top',
              theme: 'light',
            }}
            label={TableCheckBoxFiltersEnum.EntrySpan}
          >
            {t('入口Span')}
          </Checkbox>
          <Checkbox label={TableCheckBoxFiltersEnum.Error}>{t('错误')}</Checkbox>
        </Checkbox.Group>
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
    function clickColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>) {
      return ({ row }) => {
        const alias = getTableCellRenderValue(row, column);

        return (
          <div class='explore-col explore-click-col'>
            <OverflowTitle
              class='explore-click-text'
              placement='top'
              type='tips'
            >
              <span onClick={() => column?.clickCallback?.(row, column)}>{alias}</span>
            </OverflowTitle>
          </div>
        );
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.PREFIX_ICON  带有前置 icon 列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function iconColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.PREFIX_ICON>) {
      return ({ row }) => {
        const item = getTableCellRenderValue(row, column);
        const { alias, prefixIcon } = item;
        if (alias == null || alias === '') {
          const textColumn = {
            ...column,
            getRenderValue: () => alias,
          };
          return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>)(row);
        }

        return (
          <div class='explore-col explore-prefix-icon-col'>
            <i class={`prefix-icon ${prefixIcon}`} />
            <span>{alias}</span>
          </div>
        );
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.ELAPSED_TIME 日期时间列渲染方法 (将 时间戳 转换为 YYYY-MM-DD HH:mm:ss)
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function timeColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TIME>) {
      return ({ row }) => {
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
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.DURATION 持续时间列渲染方法 (将 时间戳 自适应转换为 带单位的时间-例如 10s、10ms...)
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function durationColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.DURATION>) {
      return ({ row }) => {
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
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.LINK  点击链接跳转列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function linkColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.LINK>) {
      return ({ row }) => {
        const item = getTableCellRenderValue(row, column);
        // 当url为空时，使用textColumnFormatter渲染为普通 text 文本样式
        if (!item?.url) {
          const textColumn = {
            ...column,
            getRenderValue: () => item?.alias,
          };
          return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>)(row);
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
                {item.alias}
              </a>
            </OverflowTitle>
            <i class='icon-monitor icon-mc-goto' />
          </div>
        );
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.TAGS 类型文本类型表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function tagsColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TAGS>) {
      return ({ row }) => {
        const tags = getTableCellRenderValue(row, column);
        if (!tags?.length) {
          const textColumn = {
            ...column,
            getRenderValue: () => defaultTableConfig.emptyPlaceholder,
          };
          return textColumnFormatter(textColumn as unknown as ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>)(row);
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
      };
    }

    /**
     * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function textColumnFormatter(column: ExploreTableColumn<ExploreTableColumnTypeEnum.TEXT>) {
      return ({ row }) => {
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
      };
    }

    /**
     * @description 根据列类型，获取对应的表格列渲染方法
     * @param {ExploreTableColumn} column 当前列配置项
     *
     */
    function handleSetFormatter(column) {
      switch (column.type) {
        case ExploreTableColumnTypeEnum.CLICK:
          return clickColumnFormatter(column);
        case ExploreTableColumnTypeEnum.PREFIX_ICON:
          return iconColumnFormatter(column);
        case ExploreTableColumnTypeEnum.TIME:
          return timeColumnFormatter(column);
        case ExploreTableColumnTypeEnum.DURATION:
          return durationColumnFormatter(column);
        case ExploreTableColumnTypeEnum.LINK:
          return linkColumnFormatter(column);
        case ExploreTableColumnTypeEnum.TAGS:
          return tagsColumnFormatter(column);
        default:
          return textColumnFormatter(column);
      }
    }

    /**
     * @description 表格列渲染方法
     * @param column 列配置项
     *
     */
    function transformColumn(column: ExploreTableColumn<ExploreTableColumnTypeEnum>) {
      if (!column?.field) {
        return null;
      }
      const { showOverflow, align } = defaultTableConfig;
      return (
        <TableColumn
          key={`explore_table_${column.field}`}
          width={column.width}
          v-slots={{ default: handleSetFormatter(column) }}
          align={column.align || align}
          field={column.field}
          filterMultiple={column.filterMultiple}
          filters={column.filter}
          fixed={column.fixed}
          minWidth={column.minWidth}
          showOverflow={column.showOverflow || showOverflow}
          sortable={column.sortable}
          title={column.alias}
        />
      );
    }
    return {
      defaultTableConfig,
      tableRowKeyField,
      tableColumns,
      tableData,
      transformColumn,
      filtersCheckBoxGroupRender,
      handleSortChange,
      handleFilterChange,
    };
  },

  render() {
    return (
      <div class='trace-explore-table'>
        <div class='trace-explore-table-filter'>
          <span class='filter-label'>{this.$t('包含')}：</span>
          {this.filtersCheckBoxGroupRender()}
        </div>
        <div class='trace-explore-table-main'>
          {/* @ts-ignore */}
          <Table
            rowConfig={{
              useKey: true,
              isCurrent: true,
              keyField: this.tableRowKeyField,
            }}
            sortConfig={{
              remote: true,
              orders: ['asc', 'desc', 'null'],
            }}
            autoResize={true}
            border='inner'
            columnConfig={{ useKey: true }}
            data={this.tableData}
            filter-config={{ remote: true }}
            row-height={this.defaultTableConfig.lineHeight}
            size='mini'
            onFilterChange={this.handleFilterChange}
            onSortChange={this.handleSortChange}
          >
            {this.tableColumns.map(column => this.transformColumn(column))}
          </Table>
        </div>
      </div>
    );
  },
});
