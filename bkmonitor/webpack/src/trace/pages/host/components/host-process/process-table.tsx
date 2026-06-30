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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import { type BkUiSettings, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { useResizeObserver } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import {
  type IProcessColumnConfig,
  formatMemRss,
  formatUptime,
  getProcessMemColor,
  PROCESS_LIST_COLUMNS,
  PROCESS_PORT_STATUS_MAP,
} from '../../constants/process';

import type { ProcessItem } from '../../types/process';

import './process-table.scss';

export default defineComponent({
  name: 'ProcessTable',
  props: {
    /** 进程数据 */
    data: {
      type: Array as PropType<ProcessItem[]>,
      default: () => [],
    },
    /** 展示列 id 列表 */
    visibleColumns: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 排序（`-key` 倒序 / `key` 正序） */
    sort: {
      type: String,
      default: '',
    },
  },
  emits: {
    sortChange: (_v: string) => true,
    columnsChange: (_cols: string[]) => true,
    rowClick: (_row: ProcessItem) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const bodyRef = useTemplateRef<HTMLElement>('body');
    /** 表格体最大高度（自适应屏幕，表内滚动） */
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
      fields: PROCESS_LIST_COLUMNS.map(column => ({
        label: t(column.name),
        field: column.id,
        disabled: column.disabled,
      })),
      checked: props.visibleColumns,
    }));

    // --- 单元格渲染器 ---
    const renderNameCell = (row: ProcessItem) => (
      <span
        class='process-table-link'
        onClick={() => emit('rowClick', row)}
      >
        {row.name || '--'}
      </span>
    );

    const renderPortCell = (row: ProcessItem) => {
      const config = PROCESS_PORT_STATUS_MAP[row.portStatus];
      return (
        <div class='process-table-port'>
          <span
            style={{ backgroundColor: config?.color || '#c4c6cc' }}
            class='process-table-port__dot'
          />
          <span class='process-table-port__text'>{`${row.protocol} ${row.bindIp}:${row.port}`}</span>
        </div>
      );
    };

    const renderHostCell = (row: ProcessItem) => <span class='process-table-link'>{row.hostIp || '--'}</span>;

    const renderCpuCell = (row: ProcessItem) => <span>{row.cpuUsage >= 0 ? `${row.cpuUsage}%` : '--'}</span>;

    const renderMemoryCell = (row: ProcessItem) => {
      if (!(row.memRss > 0)) {
        return <span class='process-table-memory__empty'>--</span>;
      }
      return (
        <div class='process-table-memory'>
          <div class='process-table-memory__row'>
            <span class='process-table-memory__value'>{formatMemRss(row.memRss)}</span>
            <span class='process-table-memory__percent'>{`${row.memUsage}%`}</span>
          </div>
          <div class='process-table-memory__bar'>
            <div
              style={{ width: `${Math.min(row.memUsage, 100)}%`, backgroundColor: getProcessMemColor(row.memUsage) }}
              class='process-table-memory__bar-inner'
            />
          </div>
        </div>
      );
    };

    const renderUptimeCell = (row: ProcessItem) => <span>{formatUptime(row.uptime)}</span>;

    /** 构建某一列的 tdesign 配置 */
    const buildColumn = (config: IProcessColumnConfig) => {
      const base: Record<string, unknown> = {
        colKey: config.id,
        title: t(config.name),
        minWidth: config.minWidth,
        sorter: config.sortable,
        ellipsis: config.type === 'text' || config.type === 'port',
      };
      base.cell = (_: unknown, { row }: { row: ProcessItem }) => {
        switch (config.type) {
          case 'name':
            return renderNameCell(row);
          case 'port':
            return renderPortCell(row);
          case 'host':
            return renderHostCell(row);
          case 'cpu':
            return renderCpuCell(row);
          case 'memory':
            return renderMemoryCell(row);
          case 'uptime':
            return renderUptimeCell(row);
          default:
            return <span>{(row[config.id as keyof ProcessItem] ?? '--') as string}</span>;
        }
      };
      return base;
    };

    const tableColumns = computed(() =>
      props.visibleColumns
        .map(id => PROCESS_LIST_COLUMNS.find(column => column.id === id))
        .filter((column): column is IProcessColumnConfig => !!column)
        .map(buildColumn)
    );

    const handleSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      emit('sortChange', target?.sortBy ? `${target.descending ? '-' : ''}${target.sortBy}` : '');
    };

    return () => (
      <div
        ref='body'
        class='process-table'
      >
        <PrimaryTable
          bkUiSettings={tableSettings.value}
          columns={tableColumns.value}
          data={props.data}
          disableDataPage={true}
          hover={true}
          maxHeight={bodyHeight.value}
          needCustomScroll={false}
          resizable={true}
          rowKey='id'
          showSortColumnBgColor={true}
          size='small'
          sort={tableSort.value}
          tableLayout='fixed'
          onDisplayColumnsChange={(cols: string[]) => emit('columnsChange', cols)}
          onSortChange={handleSortChange}
        />
      </div>
    );
  },
});
