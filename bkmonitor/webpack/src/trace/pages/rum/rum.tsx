/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { computed, defineComponent, ref, shallowRef, watch } from 'vue';

import { useStorage } from '@vueuse/core';
import { Button, Input, Message } from 'bkui-vue';
import { useRouter } from 'vue-router';

import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import CommonTable from '../alarm-center/components/alarm-table/components/common-table/common-table';
import RumPageHeader from './components/rum-page-header';
import { type RumAppRow, buildRumDemoRows } from './rum-mock-data';
import {
  buildRumTableColumnMap,
  pickRumColumns,
  RUM_DEFAULT_VISIBLE_FIELDS,
  RUM_TABLE_FIELD_META,
} from './rum-table-columns';

import type { TimeRangeType } from '../../components/time-range/utils';
import type { FilterValue } from 'tdesign-vue-next';

import './rum.scss';

const RUM_TIME_DEFAULT: TimeRangeType = ['now-15m', 'now'];

function applySort(rows: RumAppRow[], sort: string): RumAppRow[] {
  if (!sort) return rows;
  const desc = sort.startsWith('-');
  const key = desc ? sort.slice(1) : sort;
  const mul = desc ? -1 : 1;
  const list = [...rows];
  list.sort((a, b) => {
    switch (key) {
      case 'lcpP75':
        return compareNullableNumber(a.lcpP75Sec, b.lcpP75Sec, mul);
      case 'jsErrorRate':
        return compareNullableNumber(a.jsErrorRate, b.jsErrorRate, mul);
      case 'apiFailRate':
        return compareNullableNumber(a.apiFailRate, b.apiFailRate, mul);
      case 'updatedAt':
        return (a.updatedAt - b.updatedAt) * mul;
      case 'createdAt':
        return (a.createdAt - b.createdAt) * mul;
      default:
        return 0;
    }
  });
  return list;
}

function applyTableFilters(rows: RumAppRow[], fv: FilterValue): RumAppRow[] {
  if (!fv || typeof fv !== 'object') return rows;
  let list = rows;
  const acc = fv.accessStatus;
  if (Array.isArray(acc) && acc.length) {
    list = list.filter(r => acc.includes(r.accessStatus));
  }
  const st = fv.appStatus;
  if (Array.isArray(st) && st.length) {
    list = list.filter(r => st.includes(r.appStatus));
  }
  return list;
}

function compareNullableNumber(a: null | number, b: null | number, mul: number) {
  const aNull = a == null || Number.isNaN(a);
  const bNull = b == null || Number.isNaN(b);
  if (aNull && bNull) return 0;
  if (aNull) return mul > 0 ? 1 : -1;
  if (bNull) return mul > 0 ? -1 : 1;
  if (a === b) return 0;
  return (a < b ? -1 : 1) * mul;
}

export default defineComponent({
  name: 'RumPage',
  setup() {
    const router = useRouter();
    const sourceRows = shallowRef(buildRumDemoRows());
    const searchKeyword = ref('');
    const tableFilterValue = ref<FilterValue>({});
    const sortStr = ref('');
    const currentPage = ref(1);
    const pageSize = ref(10);
    const loading = ref(false);

    const timeRange = ref<TimeRangeType>(RUM_TIME_DEFAULT);
    const timezone = ref(
      typeof window !== 'undefined' ? (window as Window & { timezone?: string }).timezone || '' : ''
    );
    const refreshImmediate = ref('');
    const refreshInterval = ref(-1);

    const storageColumns = useStorage<string[]>('rum-app-list-table-fields-v1', [...RUM_DEFAULT_VISIBLE_FIELDS]);

    const handleConfigure = (row: RumAppRow) => {
      router.push({ name: 'rumAppConfig', params: { appId: row.id } });
    };

    const columnMap = buildRumTableColumnMap(handleConfigure);

    const tableColumns = computed(() => pickRumColumns(storageColumns.value, columnMap));

    const allFields = computed(() => RUM_TABLE_FIELD_META.map(({ field, label }) => ({ field, label })));

    const lockedFields = computed(() => RUM_TABLE_FIELD_META.filter(i => i.locked).map(i => i.field));

    const tableSettings = computed(() => ({
      checked: storageColumns.value,
      fields: allFields.value,
      disabled: lockedFields.value,
    }));

    const filteredRows = computed(() => {
      let list = sourceRows.value;
      const kw = searchKeyword.value.trim().toLowerCase();
      if (kw) {
        list = list.filter(row =>
          [row.domain, row.alias, row.accessStatus, row.appStatus, row.creator, row.updater].some(v =>
            String(v).toLowerCase().includes(kw)
          )
        );
      }
      list = applyTableFilters(list, tableFilterValue.value);
      return applySort(list, sortStr.value);
    });

    const total = computed(() => filteredRows.value.length);

    const pagedData = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value;
      return filteredRows.value.slice(start, start + pageSize.value);
    });

    watch(
      [searchKeyword, tableFilterValue],
      () => {
        currentPage.value = 1;
      },
      { deep: true }
    );

    function handleCreateApp() {
      Message({ theme: 'primary', message: '新建应用（待对接接口）' });
    }

    function handleDisplayColFieldsChange(fields: string[]) {
      storageColumns.value = fields;
    }

    function handleFilterChange(fv: FilterValue) {
      tableFilterValue.value = { ...fv };
    }

    function handleSortChange(sort: string | string[]) {
      sortStr.value = Array.isArray(sort) ? sort[0] || '' : sort || '';
    }

    function handleCurrentPageChange(page: number) {
      currentPage.value = page;
    }

    function handlePageSizeChange(size: number) {
      pageSize.value = size;
      currentPage.value = 1;
    }

    function handleImmediateRefreshChange(v: string) {
      refreshImmediate.value = v;
      loading.value = true;
      window.setTimeout(() => {
        sourceRows.value = buildRumDemoRows();
        loading.value = false;
      }, 400);
    }

    return {
      searchKeyword,
      timeRange,
      timezone,
      refreshImmediate,
      refreshInterval,
      tableFilterValue,
      sortStr,
      currentPage,
      pageSize,
      loading,
      tableColumns,
      tableSettings,
      total,
      pagedData,
      handleCreateApp,
      handleDisplayColFieldsChange,
      handleFilterChange,
      handleSortChange,
      handleCurrentPageChange,
      handlePageSizeChange,
      handleImmediateRefreshChange,
    };
  },
  render() {
    return (
      <div class='rum-page'>
        <RumPageHeader
          class='rum-page__header'
          refreshImmediate={this.refreshImmediate}
          refreshInterval={this.refreshInterval}
          timeRange={this.timeRange.length ? this.timeRange : DEFAULT_TIME_RANGE}
          timezone={this.timezone}
          onImmediateRefreshChange={this.handleImmediateRefreshChange}
          onRefreshIntervalChange={(v: number) => {
            this.refreshInterval = v;
          }}
          onTimeRangeChange={(v: TimeRangeType) => {
            this.timeRange = v;
          }}
          onTimezoneChange={(v: string) => {
            this.timezone = v;
          }}
        />
        <div class='rum-page__main'>
          <div class='rum-page__card'>
            <div class='rum-page__toolbar'>
              <Button
                class='rum-page__create-btn'
                theme='primary'
                onClick={this.handleCreateApp}
              >
                <span class='rum-page__create-btn-inner'>
                  <i class='icon-monitor icon-plus-line' />
                  新建应用
                </span>
              </Button>
              <div class='rum-page__search-wrap'>
                <Input
                  class='rum-page__search'
                  v-model={this.searchKeyword}
                  clearable={true}
                  placeholder='搜索 应用名称（域名）、应用别名、接入状态、应用状态、创建人、最近更新人'
                  type='search'
                />
                <i class='icon-monitor icon-mc-search rum-page__search-icon' />
              </div>
            </div>
            <div class='rum-page__table'>
              <CommonTable
                pagination={{
                  currentPage: this.currentPage,
                  pageSize: this.pageSize,
                  total: this.total,
                }}
                autoFillSpace={true}
                columns={this.tableColumns}
                data={this.pagedData as unknown as Record<string, unknown>[]}
                filterValue={this.tableFilterValue}
                loading={this.loading}
                rowKey='id'
                sort={this.sortStr}
                stripe={true}
                tableSettings={this.tableSettings}
                onCurrentPageChange={this.handleCurrentPageChange}
                onDisplayColFieldsChange={this.handleDisplayColFieldsChange}
                onFilterChange={this.handleFilterChange}
                onPageSizeChange={this.handlePageSizeChange}
                onSortChange={this.handleSortChange}
              />
            </div>
          </div>
        </div>
      </div>
    );
  },
});
