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

import { type VNode, computed, reactive } from 'vue';
import type { DeepReadonly, MaybeRef } from 'vue';

import { get } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import useUserConfig from '../../../../../hooks/useUserConfig';
import { useTraceExploreStore } from '../../../../../store/modules/explore';
import {
  CAN_TABLE_SORT_FIELD_TYPES,
  SERVICE_CATEGORY_MAP,
  SERVICE_STATUS_COLOR_MAP,
  SPAN_KIND_MAPS,
  SPAN_STATUS_CODE_MAP,
  TABLE_DEFAULT_CONFIG,
  TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX,
} from '../constants';
import {
  type ActiveConditionMenuTarget,
  type CustomDisplayColumnFieldsConfig,
  type ExploreTableColumn,
  type GetTableCellRenderValue,
  ExploreTableColumnTypeEnum,
} from '../typing';

import type { IDimensionField } from '../../../typing';
import type { SortInfo, TableSort } from '@blueking/tdesign-ui';
import type { SlotReturnValue } from 'tdesign-vue-next';

interface UseExploreTableColumnConfig {
  isSpanVisual: MaybeRef<boolean>;
  props: Record<string, any>;
  rowKeyField: MaybeRef<string>;
  sortContainer: DeepReadonly<SortInfo>;
  handleConditionMenuShow: (triggerDom: HTMLElement, conditionMenuTarget: ActiveConditionMenuTarget) => void;
  handleSliderShowChange: (mode: 'span' | 'trace', id: string) => void;
  handleSortChange: (sortEvent: TableSort) => void;
  tableCellRender: (column: ExploreTableColumn, row: Record<string, any>) => SlotReturnValue;
  tableHeaderCellRender: (title: string, tipText: string, column: ExploreTableColumn) => () => SlotReturnValue;
}

/**
 * @description 检索表格列配置相关逻辑 hook
 *
 */
export function useExploreColumnConfig({
  props,
  isSpanVisual,
  rowKeyField,
  sortContainer,
  tableHeaderCellRender,
  tableCellRender,
  handleConditionMenuShow,
  handleSliderShowChange,
  handleSortChange,
}: UseExploreTableColumnConfig) {
  /** table 默认配置项 */
  const { tableConfig: defaultTableConfig, traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;
  const { t } = useI18n();
  const store = useTraceExploreStore();
  const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

  /** 用户自定义配置 table 显示列后缓存的显示列配置数据 */
  const customDisplayColumnFieldsConfig = reactive<CustomDisplayColumnFieldsConfig>({
    /** 展示的列 */
    displayFields: [],
    /** 列宽度集合 */
    fieldsWidth: {},
  });

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

  /** table 列配置本地缓存时的 key */
  const customDisplayColumnFieldsCacheKey = computed(
    () => `${props.mode}_${props.appName}_${TABLE_DISPLAY_COLUMNS_FIELD_SUFFIX}`
  );

  /** table 显示列配置 */
  const displayColumnFields = computed(() => {
    // 前端写死的兜底默认显示列配置(优先级：userConfig -> appList -> defaultConfig)
    const defaultColumnsConfig = get(isSpanVisual) ? spanConfig : traceConfig;
    const applicationColumnConfig = store?.currentApp?.view_config?.[`${props.mode}_config`]?.display_columns || [];
    // 需要展示的字段列名数组
    return customDisplayColumnFieldsConfig.displayFields?.length
      ? customDisplayColumnFieldsConfig.displayFields
      : applicationColumnConfig?.length
        ? applicationColumnConfig
        : ((defaultColumnsConfig?.displayFields || []) as string[]);
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
        column.width = customDisplayColumnFieldsConfig.fieldsWidth?.[colKey] || column.width;
        // 表格列表头渲染方法
        const tableHeaderTitle = tableHeaderCellRender(column.title as string, tipText, column);
        // 表格单元格渲染方法
        const tableCell = (_, { row }) => tableCellRender(column, row);

        return {
          ...defaultTableConfig,
          ...column,
          title: tableHeaderTitle,
          cell: tableCell,
          attrs: column.sorter
            ? {
                // 扩大排序点击热区范围
                onClick(e: MouseEvent & { currentTarget: Element; target: Element }) {
                  if (
                    column.colKey &&
                    e.currentTarget.tagName.toLocaleLowerCase() === 'th' &&
                    !['svg', 'path'].includes(e.target.tagName.toLocaleLowerCase()) &&
                    e.currentTarget?.classList.contains(`t-table__th-${column.colKey}`)
                  ) {
                    let sortBy = sortContainer.sortBy;
                    let descending = sortContainer.descending;
                    if (sortBy === column.colKey) {
                      const sortDescValueList = [false, true, null];
                      const sortIndex = sortDescValueList.findIndex(v => descending === v);
                      descending = sortDescValueList.at((sortIndex + 1) % sortDescValueList.length);
                      if (descending === null) {
                        sortBy = '';
                      }
                    } else {
                      sortBy = column.colKey;
                      descending = false;
                    }
                    handleSortChange({ sortBy, descending });
                  }
                },
              }
            : undefined,
        };
      })
      .filter(Boolean);
  });

  /**
   * @description: 获取 table 表格列配置
   *
   */
  async function getCustomDisplayColumnFields() {
    customDisplayColumnFieldsConfig.displayFields = [];
    customDisplayColumnFieldsConfig.fieldsWidth = {};
    if (!props.appName || !props.mode) return;
    const customCacheConfig = (await handleGetUserConfig<string[]>(customDisplayColumnFieldsCacheKey.value)) || {
      displayFields: [],
      fieldsWidth: {},
    };
    // 原来只缓存了展示字段，且是数组结构，目前改为对象结构需向前兼容
    if (Array.isArray(customCacheConfig)) {
      customDisplayColumnFieldsConfig.displayFields = customCacheConfig;
      return;
    }
    customDisplayColumnFieldsConfig.displayFields = customCacheConfig.displayFields;
    customDisplayColumnFieldsConfig.fieldsWidth = customCacheConfig.fieldsWidth;
  }

  /**
   * @description 表格列显示配置项变更回调
   *
   */
  function handleDisplayColumnFieldsChange(displayFields: string[]) {
    customDisplayColumnFieldsConfig.displayFields = displayFields;
    // 缓存列配置
    handleSetUserConfig(JSON.stringify(customDisplayColumnFieldsConfig));
  }

  function handleDisplayColumnResize(context: { columnsWidth: { [colKey: string]: number } }) {
    customDisplayColumnFieldsConfig.fieldsWidth = context?.columnsWidth || {};
    // 缓存列配置
    handleSetUserConfig(JSON.stringify(customDisplayColumnFieldsConfig));
  }

  /**
   * @description 获取新开页跳转至apm页 概览tab 的 LINK 类型表格列所需数据格式
   *
   */
  function getJumpToApmLinkItem(row, column): GetTableCellRenderValue<ExploreTableColumnTypeEnum.LINK> {
    const alias = row?.[column.colKey];
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

  /**
   * @description 服务 或 接口 列点击后回调
   *
   */
  function handleServiceOrApiColumnClick(row, column, e, customMenu) {
    const colKey = column.colKey;
    handleConditionMenuShow(e.target, {
      rowId: row?.[get(rowKeyField)] || '',
      colId: colKey,
      conditionValue: row[colKey],
      customMenuList: customMenu,
    });
  }

  /**
   * @description 查看详情 回调
   *
   */
  function handleLink(linkUrl) {
    if (!linkUrl) {
      return;
    }
    window.open(linkUrl, '_blank');
  }

  /**
   * @description 根据当前激活的视角(trace/span)获取对应的table表格列配置
   *
   */
  function getTableColumnMapByVisualMode(): Record<string, ExploreTableColumn> {
    if (get(isSpanVisual)) {
      return {
        span_id: {
          renderType: ExploreTableColumnTypeEnum.CLICK,
          colKey: 'span_id',
          title: t('Span ID'),
          width: 160,
          fixed: 'left',
          suffixSlot: row =>
            (
              <i
                class='icon-monitor icon-Tracing'
                v-bk-tooltips={{ content: t('查看关联 Trace'), delay: 400 }}
                onClick={() => handleSliderShowChange('trace', row.trace_id)}
              />
            ) as unknown as VNode,
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
          renderType: ExploreTableColumnTypeEnum.CLICK,
          colKey: 'resource.service.name',
          title: t('所属服务'),
          width: 160,
          clickCallback: (row, column, e) => {
            const item = getJumpToApmLinkItem(row, column);
            const customMenu = [
              {
                id: 'service-link',
                name: t('查看服务详情'),
                icon: 'icon-chakan',
                onClick: () => handleLink(item.url),
                suffixRender: () => <i class={'icon-monitor icon-mc-goto'} />,
              },
            ];
            handleServiceOrApiColumnClick(row, column, e, customMenu);
          },
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
        title: 'Trace ID',
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
        renderType: ExploreTableColumnTypeEnum.CLICK,
        colKey: 'root_span_name',
        headerDescription: t('整个 Trace 的第一个 Span'),
        title: t('根 Span'),
        width: 160,
        clickCallback: (row, column, e) => {
          const item = getJumpToApmApplicationLinkItem(row, column);
          const customMenu = [
            {
              id: 'api-link',
              name: t('查看接口详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => <i class={'icon-monitor icon-mc-goto'} />,
            },
          ];
          handleServiceOrApiColumnClick(row, column, e, customMenu);
        },
      },
      root_service: {
        renderType: ExploreTableColumnTypeEnum.CLICK,
        colKey: 'root_service',
        headerDescription: t('服务端进程的第一个 Service'),
        title: t('入口服务'),
        width: 160,
        clickCallback: (row, column, e) => {
          const item = getJumpToApmLinkItem(row, column);
          const customMenu = [
            {
              id: 'api-link',
              name: t('查看服务详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => <i class={'icon-monitor icon-mc-goto'} />,
            },
          ];
          handleServiceOrApiColumnClick(row, column, e, customMenu);
        },
      },
      root_service_span_name: {
        renderType: ExploreTableColumnTypeEnum.CLICK,
        colKey: 'root_service_span_name',
        headerDescription: t('入口服务的第一个接口'),
        title: t('入口接口'),
        width: 160,
        clickCallback: (row, column, e) => {
          const item = getJumpToApmApplicationLinkItem(row, column);
          const customMenu = [
            {
              id: 'api-link',
              name: t('查看接口详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => <i class={'icon-monitor icon-mc-goto'} />,
            },
          ];
          handleServiceOrApiColumnClick(row, column, e, customMenu);
        },
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
          const value = row?.root_service_status_code as string;
          if (!value) return [];
          const type = row?.root_service_status_code === 200 ? 'normal' : 'error';
          return [
            {
              alias: value,
              value,
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
      'collections.kind': {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        colKey: 'collections.kind',
        title: t('状态码'),
        width: 120,
        getRenderValue: row => {
          let value = row?.['collections.kind'];
          if (!value) return [];
          if (!Array.isArray(value)) value = [value];
          return value.map(v => ({
            alias: SPAN_KIND_MAPS[v]?.alias,
            value: v,
            tagColor: '#63656e',
            tagBgColor: 'rgba(151,155,165,.1)',
          }));
        },
      },
    };
  }

  return {
    tableColumns,
    displayColumnFields,
    tableDisplayColumns,
    getCustomDisplayColumnFields,
    handleDisplayColumnFieldsChange,
    handleDisplayColumnResize,
  };
}
