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

import { type MaybeRef, type VNode, computed } from 'vue';

import { get } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import { useTraceStore } from '../../../../../store/modules/trace';
import {
  CAN_TABLE_SORT_FIELD_TYPES,
  SERVICE_CATEGORY_MAP,
  SERVICE_STATUS_COLOR_MAP,
  SPAN_KIND_MAPS,
  SPAN_STATUS_CODE_MAP,
  TABLE_DEFAULT_CONFIG,
} from '../constants';
import {
  type ActiveConditionMenuTarget,
  type ExploreConditionMenuItem,
  type ExploreTableColumn,
  type GetTableCellRenderValue,
  type TableCellRenderContext,
  type TableCellRenderer,
  ExploreTableColumnTypeEnum,
} from '../typing';

import type { IDimensionField } from '../../../typing';
import type { SortInfo, TableSort } from '@blueking/tdesign-ui';
import type { SlotReturnValue } from 'tdesign-vue-next';

interface UseExploreTableColumnConfig {
  /** 当前选中的应用 Name */
  appName: MaybeRef<string>;
  /** 支持排序的字段类型 */
  canSortFieldTypes: MaybeRef<Set<string> | string[]>;
  /** 需要显示渲染的列名数组 */
  displayFields: MaybeRef<string[]>;
  /** 是否启用点击弹出操作下拉菜单 */
  enabledClickMenu: MaybeRef<boolean>;
  /** 缓存的列宽配置 */
  fieldsWidthConfig: MaybeRef<Record<string, number>>;
  /** 当前激活的视角(span | trace)  */
  mode: MaybeRef<'span' | 'trace'>;
  /** 表格渲染上下文 */
  renderContext: TableCellRenderContext;
  /** 表格行数据唯一 key 字段 */
  rowKeyField: MaybeRef<string>;
  /** 表格排序信息 */
  sortContainer: MaybeRef<SortInfo>;
  /** 表格所有列字段配置数组(接口原始结构) */
  sourceFieldConfigs: MaybeRef<IDimensionField[]>;
  /** 表格单元格渲染 */
  tableCellRender: TableCellRenderer;
  /** 点击显示下拉操作menu */
  handleConditionMenuShow: (triggerDom: HTMLElement, conditionMenuTarget: ActiveConditionMenuTarget) => void;
  /** 点击展示 span | trace 详情抽屉页 */
  handleSliderShowChange: (mode: 'span' | 'trace', id: string) => void;
  /** 点击排序回调 */
  handleSortChange: (sortEvent: TableSort) => void;
  /** 表头单元格渲染 */
  tableHeaderCellRender: (title: string, tipText: string, column: ExploreTableColumn) => () => SlotReturnValue;
}

/**
 * @method useExploreColumnConfig column 组装 hook
 * @description 检索表格列配置column组装逻辑 hook
 */
export const useExploreColumnConfig = ({
  appName,
  canSortFieldTypes,
  displayFields,
  enabledClickMenu,
  sourceFieldConfigs,
  fieldsWidthConfig,
  mode,
  rowKeyField,
  sortContainer,
  renderContext,
  tableHeaderCellRender,
  tableCellRender,
  handleConditionMenuShow,
  handleSliderShowChange,
  handleSortChange,
}: UseExploreTableColumnConfig) => {
  /** table 默认配置项 */
  const { tableConfig: defaultTableConfig, traceConfig, spanConfig } = TABLE_DEFAULT_CONFIG;
  const { t } = useI18n();
  const traceStore = useTraceStore();

  /** 支持排序的字段类型(Set 结构) */
  const canSortFieldTypesSet = computed(() => {
    return new Set(get(canSortFieldTypes) ?? CAN_TABLE_SORT_FIELD_TYPES);
  });
  /** table 所有列字段信息(字段设置使用) */
  const tableColumns = computed(() => {
    return (get(sourceFieldConfigs) ?? []).reduce(
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
  });
  /** table 显示列Column配置 */
  const tableDisplayColumns = computed<ExploreTableColumn[]>(() => {
    const fieldMap = tableColumns.value.fieldMap;
    const columnMap = getTableColumnMapByVisualMode();
    const defaultDisplayFields = get(mode) === 'span' ? spanConfig : traceConfig;
    return (get(displayFields) ?? defaultDisplayFields.displayFields)
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
        column.sorter = column.sorter != null ? column.sorter : get(canSortFieldTypesSet).has(fieldItem?.type);
        column.width = get(fieldsWidthConfig)?.[colKey] || column.width;
        // 表格列表头渲染方法
        const tableHeaderTitle = tableHeaderCellRender(column.title as string, tipText, column);
        // 表格单元格渲染方法
        const tableCell = (_, { row }) => tableCellRender(row, column, renderContext);

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
                    let sortBy = get(sortContainer).sortBy;
                    let descending = get(sortContainer).descending;
                    if (sortBy === column.colKey) {
                      const sortDescValueList = [false, true, null];
                      const sortIndex = sortDescValueList.indexOf(descending);
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
   * @method getTableColumnMapByVisualMode 拼接 APM-概览 页面地址
   * @description 获取新开页跳转至apm页 概览tab 的 LINK 类型表格列所需数据格式
   * @param {any} row 行数据
   * @param {ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>} column 列配置
   */
  const getJumpToApmLinkItem = (
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>
  ): GetTableCellRenderValue<ExploreTableColumnTypeEnum.LINK> => {
    const alias = row?.[column.colKey];
    const hash = `#/apm/service?filter-service_name=${alias}&filter-app_name=${get(appName)}`;
    let url = '';
    if (alias) {
      url = location.href.replace(location.hash, hash);
    }
    return {
      alias: alias,
      url: url,
    };
  };

  /**
   * @method getTableColumnMapByVisualMode 拼接 APM-接口 页面地址
   * @description 获取新开页跳转至 apm 页 接口tab 的 LINK 类型表格列所需数据格式
   * @param {any} row 行数据
   * @param {ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>} column 列配置
   */
  const getJumpToApmApplicationLinkItem = (
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>
  ): GetTableCellRenderValue<ExploreTableColumnTypeEnum.LINK> => {
    const service = row?.root_service;
    const alias = row?.[column.colKey];
    const hash = `#/apm/application?filter-service_name=${service}&filter-app_name=${get(appName)}&sceneId=apm_application&sceneType=detail&dashboardId=endpoint&filter-endpoint_name=${alias}`;
    let url = '';
    if (alias && service) {
      url = location.href.replace(location.hash, hash);
    }
    return {
      alias: alias,
      url: url,
    };
  };

  /**
   * @method handleServiceOrApiColumnClick 服务 或 接口 列点击后回调
   * @param row 行数据
   * @param {ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>} column 列配置
   * @param {MouseEvent} e 事件对象
   * @param {ExploreConditionMenuItem[]} customMenu 自定义菜单列表
   */
  const handleServiceOrApiColumnClick = (
    row,
    column: ExploreTableColumn<ExploreTableColumnTypeEnum.CLICK>,
    e: MouseEvent,
    customMenu: ExploreConditionMenuItem[]
  ) => {
    if (!get(enabledClickMenu)) {
      for (const menuItem of customMenu ?? []) {
        if (['api-link', 'service-link'].includes(menuItem.id)) {
          menuItem?.onClick?.(e);
        }
      }
      return;
    }
    const colKey = column.colKey;
    handleConditionMenuShow(e.target as HTMLElement, {
      rowId: row?.[get(rowKeyField)] || '',
      colId: colKey,
      conditionValue: row[colKey],
      customMenuList: customMenu,
    });
  };

  /**
   * @method handleLink 新开页跳转
   * @description 查看详情 回调
   * @param {string} linkUrl 链接地址
   */
  const handleLink = linkUrl => {
    if (!linkUrl) {
      return;
    }
    window.open(linkUrl, '_blank');
  };

  /**
   * @method getTableColumnMapByVisualMode 获取table表格列配置
   * @description 根据当前激活的视角(trace/span)获取对应的table表格列配置
   */
  const getTableColumnMapByVisualMode = (): Record<string, ExploreTableColumn> => {
    if (get(mode) === 'span') {
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
                onClick={() => {
                  // 记录“需要在 trace 侧滑中定位/高亮的 span”
                  traceStore.setExternalLocateSpan(row.trace_id, row.span_id);
                  // 打开 trace 侧滑
                  handleSliderShowChange('trace', row.trace_id);
                }}
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
          width: 200,
        },
        start_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
          colKey: 'start_time',
          title: t('开始时间'),
          minWidth: 230,
        },
        end_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
          colKey: 'end_time',
          title: t('结束时间'),
          minWidth: 230,
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
            const customMenu: ExploreConditionMenuItem[] = [
              {
                id: 'service-link',
                name: t('查看服务详情'),
                icon: 'icon-chakan',
                onClick: () => handleLink(item.url),
                suffixRender: () => (<i class={'icon-monitor icon-mc-goto'} />) as unknown as SlotReturnValue,
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
          clickCallback: row => {
            // 记录“需要在 trace 侧滑中定位/高亮的 span”
            traceStore.setExternalLocateSpan(row.trace_id, row.span_id);
            // 打开 trace 侧滑
            handleSliderShowChange('trace', row.trace_id);
          },
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
          const customMenu: ExploreConditionMenuItem[] = [
            {
              id: 'api-link',
              name: t('查看接口详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => (<i class={'icon-monitor icon-mc-goto'} />) as unknown as SlotReturnValue,
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
          const customMenu: ExploreConditionMenuItem[] = [
            {
              id: 'api-link',
              name: t('查看服务详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => (<i class={'icon-monitor icon-mc-goto'} />) as unknown as SlotReturnValue,
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
          const customMenu: ExploreConditionMenuItem[] = [
            {
              id: 'api-link',
              name: t('查看接口详情'),
              icon: 'icon-chakan',
              onClick: () => handleLink(item.url),
              suffixRender: () => (<i class={'icon-monitor icon-mc-goto'} />) as unknown as SlotReturnValue,
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
            tagColor: '#4D4F56',
            tagBgColor: '#F0F1F5',
          }));
        },
      },
    };
  };

  return {
    tableColumns,
    tableDisplayColumns,
  };
};
