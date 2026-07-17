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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef, ref, watch } from 'vue';

import { type BkUiSettings, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { useResizeObserver } from '@vueuse/core';
import { Pagination, Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import {
  type IHostColumnConfig,
  HOST_LIST_COLUMNS,
  HOST_LIST_PAGE_SIZE_LIST,
  HOST_STATUS_MAP,
} from '../../constants/host-list';

import type { EHostAggMethod, IHostListRow } from '../../types/host-list';
import AcrossPageSelection, {
  SelectType,
  type SelectTypeEnum,
} from '../../../../components/across-page-selection/across-page-selection';
import BkCheckbox from 'bkui-vue/lib/checkbox';

import './host-list-table.scss';

/** 告警等级 → 色块背景色 */
const ALARM_LEVEL_COLOR: Record<number, string> = {
  1: '#ea3636',
  2: '#F59500',
  3: '#DCDEE5',
};

/** 指标进度条颜色阈值 */
const getProgressColor = (value: number) => {
  if (value > 80) return '#EA3636';
  return '#2CAF5E';
};

/** 取告警色块背景色：取有告警数且等级最高（level 最小）的颜色，否则灰色 */
const getAlarmColor = (row: IHostListRow) => {
  if (!row.totalAlarmCount) {
    return '#dcdee5';
  }
  const top = (row.alarm_count || []).reduce<null | { color: string; level: number }>((min, cur) => {
    return cur.count && (!min || cur.level < min.level)
      ? { color: ALARM_LEVEL_COLOR[cur.level], level: cur.level }
      : min;
  }, null);
  return top?.color || '#dcdee5';
};

export default defineComponent({
  name: 'HostListTable',
  props: {
    /** 当前页数据 */
    data: {
      type: Array as PropType<IHostListRow[]>,
      default: () => [],
    },
    /** 展示列 id 列表 */
    visibleColumns: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 总条数 */
    total: {
      type: Number,
      default: 0,
    },
    /** 当前页码 */
    page: {
      type: Number,
      default: 1,
    },
    /** 每页条数 */
    pageSize: {
      type: Number,
      default: 50,
    },
    /** 排序（`-key` 倒序 / `key` 正序） */
    sort: {
      type: String,
      default: '',
    },
    /** 选中行 key */
    selectedRowKeys: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /** 指标数据加载中（指标列展示骨架） */
    metricLoading: {
      type: Boolean,
      default: false,
    },
    /** 指标列聚合方式 */
    aggMethodMap: {
      type: Object as PropType<Record<string, EHostAggMethod>>,
      default: () => ({}),
    },
    /** 聚合方式候选 */
    aggMethodList: {
      type: Array as PropType<{ id: EHostAggMethod; name: string }[]>,
      default: () => [],
    },
  },
  emits: {
    sortChange: (_v: string) => true,
    pageChange: (_v: number) => true,
    pageSizeChange: (_v: number) => true,
    selectChange: (_keys: (number | string)[], _isAcrossPage: boolean) => true,
    columnsChange: (_cols: string[]) => true,
    aggMethodChange: (_metricKey: string, _method: EHostAggMethod) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const bodyRef = useTemplateRef<HTMLElement>('body');

    const totalSelected = ref<SelectTypeEnum>(SelectType.UN_SELECTED);
    const checkedRowsMap = ref<Record<string, boolean>>({});
    /** 表格体最大高度（自适应屏幕，表内滚动，表头/分页不滚走） */
    const bodyHeight = shallowRef(400);
    useResizeObserver(bodyRef, entries => {
      const height = entries[0]?.contentRect?.height;
      if (height) {
        bodyHeight.value = height;
      }
    });

    /** 排序转换为 tdesign 数组形式 */
    const tableSort = computed<TableSort>(() => {
      if (!props.sort) return [];
      const descending = props.sort.startsWith('-');
      return [{ sortBy: descending ? props.sort.slice(1) : props.sort, descending }];
    });

    /** 字段设置：全部字段 + 当前展示字段 */
    const tableSettings = computed<BkUiSettings>(() => ({
      fields: HOST_LIST_COLUMNS.map(column => ({ label: t(column.name), field: column.id, disabled: column.disabled })),
      checked: props.visibleColumns,
    }));

    watch(
      () => [totalSelected.value, checkedRowsMap.value],
      () => {
        if (totalSelected.value === SelectType.ALL_SELECTED) {
          // 跨页全选
          emit('selectChange', [], true);
          return;
        }

        const checkedIps = Object.entries(checkedRowsMap.value).reduce<string[]>((acc, [id, isChecked]) => {
          if (isChecked) {
            acc.push(id);
          }
          return acc;
        }, []);
        emit('selectChange', checkedIps, false);
      },
      {
        deep: true,
      }
    );

    // --- 单元格渲染器 ---
    const renderIpCell = (row: IHostListRow) => (
      <span
        class='host-table-ip'
        v-bk-tooltips={{ content: t('详情页开发中'), delay: 300 }}
      >
        {row.display_name || row.bk_host_innerip || '--'}
      </span>
    );

    const renderStatusCell = (row: IHostListRow) => {
      if (props.metricLoading && row.status === undefined) {
        return <div class='host-table-skeleton' />;
      }
      const config = HOST_STATUS_MAP[row.status];
      if (!config) {
        return <span>--</span>;
      }
      return (
        <div class='host-table-status'>
          <div
            class='host-table-status__dot-wrapper'
            style={{ backgroundColor: config.backgroundColor }}
          >
            <div
              style={{ backgroundColor: config.color }}
              class='host-table-status__dot'
            />
          </div>

          <span>{t(config.name)}</span>
        </div>
      );
    };

    const renderAlarmCell = (row: IHostListRow) => {
      if (props.metricLoading && !row.alarm_count) {
        return <div class='host-table-skeleton' />;
      }
      return (
        <span
          style={{ backgroundColor: getAlarmColor(row) }}
          class='host-table-alarm'
        >
          {row.totalAlarmCount >= 0 ? row.totalAlarmCount : '--'}
        </span>
      );
    };

    const renderMetricCell = (row: IHostListRow, key: string) => {
      if (props.metricLoading) {
        return <div class='host-table-skeleton' />;
      }
      const value = Number(row[key as keyof IHostListRow] ?? 0);
      if (!(value > 0)) {
        return <span class='host-table-metric__empty'>--</span>;
      }
      return (
        <div class='host-table-metric'>
          <span class='host-table-metric__value'>{`${+value.toFixed(2)}%`}</span>
          <div class='host-table-metric__bar'>
            <div
              style={{ width: `${Math.min(value, 100)}%`, backgroundColor: getProgressColor(value) }}
              class='host-table-metric__bar-inner'
            />
          </div>
        </div>
      );
    };

    const renderProcessCell = (row: IHostListRow) => {
      const components = row.component || [];
      if (!components.length) {
        return <span class='host-table-process__empty'>--</span>;
      }
      return (
        <div class='host-table-process'>
          {components.map((item, index) => (
            <span
              key={`${item.display_name}_${index}`}
              class={['host-table-process__tag', item.status === 1 ? 'is-abnormal' : 'is-normal']}
            >
              {item.display_name}
            </span>
          ))}
        </div>
      );
    };

    /** 指标列表头：聚合方式（蓝字可点切换）+ 标题 */
    const renderMetricHeader = (column: IHostColumnConfig) => {
      const aggMethod = props.aggMethodMap[column.id] || 'avg';
      return (
        <div class='host-table-metric-header'>
          <Popover
            extCls='host-table-agg-popover'
            placement='bottom-start'
            theme='light padding-0'
            trigger='click'
          >
            {{
              default: () => <i class='icon-monitor icon-avg host-table-metric-header__agg' />,
              content: () => (
                <div class='host-table-agg-menu'>
                  {props.aggMethodList.map(method => (
                    <div
                      key={method.id}
                      class={['host-table-agg-menu__item', { 'is-active': method.id === aggMethod }]}
                      onClick={() => emit('aggMethodChange', column.id, method.id)}
                    >
                      {method.name}
                    </div>
                  ))}
                </div>
              ),
            }}
          </Popover>
          <span class='host-table-metric-header__title'>{t(column.name)}</span>
        </div>
      );
    };

    /** 渲染 checkbox 头 */
    const renderCheckboxHeader = () => {
      return (
        <AcrossPageSelection
          value={totalSelected.value}
          onChange={handleTotalSelectedChange}
        />
      );
    };

    /** 处理全选变化 */
    const handleTotalSelectedChange = (value: SelectTypeEnum) => {
      console.log('value = ', value);
      totalSelected.value = value;
      if (value === SelectType.SELECTED || value === SelectType.ALL_SELECTED) {
        // 全选
        for (const row of props.data) {
          checkedRowsMap.value[row.id] = true;
        }
        return;
      }

      if (value === SelectType.UN_SELECTED) {
        // 取消全选
        checkedRowsMap.value = {};
      }
    };

    /** 渲染 checkbox 单元格 */
    const renderCheckboxCell = (row: IHostListRow) => {
      return (
        <BkCheckbox
          checked={checkedRowsMap.value[row.id] || false}
          onChange={(isChecked: boolean) => handleCheckboxChange(row.id, isChecked)}
        />
      );
    };

    /** 处理单个 checkbox 变化 */
    const handleCheckboxChange = (id: string, isChecked: boolean) => {
      checkedRowsMap.value[id] = isChecked;
      const checkedCount = Object.values(checkedRowsMap.value).filter(Boolean).length;
      if (checkedCount === props.data.length) {
        totalSelected.value = SelectType.SELECTED;
      } else if (checkedCount === 0) {
        totalSelected.value = SelectType.UN_SELECTED;
      } else {
        totalSelected.value = SelectType.HALF_SELECTED;
      }
    };

    /** 普通文本单元格 */
    const renderTextCell = (row: IHostListRow, key: string) => {
      const value = row[key as keyof IHostListRow];
      return <span>{value === 0 || value ? value : '--'}</span>;
    };

    /** 构建某一列的 tdesign 配置 */
    const buildColumn = (config: IHostColumnConfig) => {
      let title = () => <span>{t(config.name)}</span>;
      if (config.type === 'checkbox') {
        title = () => renderCheckboxHeader();
      } else if (config.type === 'metric') {
        title = () => renderMetricHeader(config);
      }
      const base: Record<string, unknown> = {
        colKey: config.id,
        title,
        minWidth: config.minWidth,
        width: config.width,
        sorter: config.sortable,
        ellipsis: ['text', 'cluster', 'module'].includes(config.type),
      };
      base.cell = (_: unknown, { row }: { row: IHostListRow }) => {
        switch (config.type) {
          case 'ip':
            return renderIpCell(row);
          case 'status':
            return renderStatusCell(row);
          case 'alarm':
            return renderAlarmCell(row);
          case 'metric':
            return renderMetricCell(row, config.id);
          case 'process':
            return renderProcessCell(row);
          case 'cluster':
            return <span>{row.clusterNames || '--'}</span>;
          case 'module':
            return <span>{row.moduleNames || '--'}</span>;
          case 'checkbox':
            return renderCheckboxCell(row);
          default:
            return renderTextCell(row, config.id);
        }
      };
      return base;
    };

    /** 表格列：选择列 + 展示列 */
    const tableColumns = computed(() => {
      const dataColumns = props.visibleColumns
        .map(id => HOST_LIST_COLUMNS.find(column => column.id === id))
        .filter((column): column is IHostColumnConfig => !!column)
        .map(buildColumn);
      return dataColumns;
      // return [selectionColumn, ...dataColumns];
    });

    const handleSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      emit('sortChange', target?.sortBy ? `${target.descending ? '-' : ''}${target.sortBy}` : '');
    };

    return () => (
      <div class='host-list-table'>
        <div
          ref='body'
          class='host-list-table__body'
        >
          <PrimaryTable
            bkUiSettings={tableSettings.value}
            columns={tableColumns.value}
            data={props.data}
            disableDataPage={true}
            hover={true}
            maxHeight={bodyHeight.value}
            needCustomScroll={false}
            reserveSelectedRowOnPaginate={true}
            resizable={true}
            rowKey='id'
            selectedRowKeys={props.selectedRowKeys}
            showSortColumnBgColor={true}
            size='small'
            sort={tableSort.value}
            tableLayout='fixed'
            onDisplayColumnsChange={(cols: string[]) => emit('columnsChange', cols)}
            // onSelectChange={(keys: (number | string)[]) => emit('selectChange', keys)}
            onSortChange={handleSortChange}
          />
        </div>
        <Pagination
          class='host-list-table__pagination'
          align='left'
          count={props.total}
          layout={['total', 'limit', 'list']}
          limit={props.pageSize}
          limitList={HOST_LIST_PAGE_SIZE_LIST}
          modelValue={props.page}
          onChange={(v: number) => emit('pageChange', v)}
          onLimitChange={(v: number) => emit('pageSizeChange', v)}
        />
      </div>
    );
  },
});
