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

import { computed, defineComponent, onMounted, shallowRef, watch } from 'vue';

import { Button, SearchSelect } from 'bkui-vue';
import { listApplication, listApplicationAsync } from 'monitor-api/modules/rum_meta';
import { random } from 'monitor-common/utils';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import CommonHeader from '../../components/common-header/common-header';
import { type TimeRangeType, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone, updateTimezone } from '../../i18n/dayjs';
import CommonTable from '../alarm-center/components/alarm-table/components/common-table/common-table';
import CreateApp from './components/create-app/create-app';
import SDKReport from './components/sdk-report/sdk-report';
import { type MetricMap, buildRumAppRows } from './rum-controller';
import { METRIC_COLUMN_TITLES, SORTABLE_METRIC_KEYS } from './typings/home';

import type { BaseTableColumn } from '../trace-explore/components/trace-explore-table/typing';
import type { MetricTier, RumApplicationAsyncItem, RumAppRow, RumTableItem, SortableMetricKey } from './typings';
import type { IRumAppConfig } from './typings/rum-app-config';
import type { FilterValue } from '@blueking/tdesign-ui';
import type { BkUiSettings } from '@blueking/tdesign-ui';
import type { GetMenuListFunc, ICommonItem, ISearchValue } from 'bkui-vue/lib/search-select/utils';

import './rum.scss';

type RumCriteriaKey = 'appAlias' | 'appName' | 'appStatus' | 'dataStatus';

type RumFilterCriteria = Partial<Record<RumCriteriaKey, string[]>>;

/** 顶部 SearchSelect 支持的维度（与表头筛选项共用 rumCriteria，双向联动） */
const SEARCH_DIMENSION_KEYS: RumCriteriaKey[] = ['appName', 'appAlias', 'appStatus'];

/** 表头带筛选的列字段（含 dataStatus；与 criteriaToFilterValue 一致） */
const TABLE_FILTER_KEYS: RumCriteriaKey[] = ['appName', 'appAlias', 'appStatus', 'dataStatus'];

const uniqSorted = (arr: string[]) => [...new Set(arr)].sort((a, b) => a.localeCompare(b));

const mergeSearchValuesIntoCriteria = (prev: RumFilterCriteria, values: ISearchValue[]): RumFilterCriteria => {
  const next: RumFilterCriteria = { ...prev };
  for (const key of SEARCH_DIMENSION_KEYS) {
    delete next[key];
  }
  for (const sv of values) {
    const id = sv.id as RumCriteriaKey;
    if (!SEARCH_DIMENSION_KEYS.includes(id) || !sv.values?.length) continue;
    next[id] = sv.values.map(x => x.id);
  }
  return next;
};

const mergeTableFilterIntoCriteria = (prev: RumFilterCriteria, value: FilterValue): RumFilterCriteria => {
  const next: RumFilterCriteria = { ...prev };
  for (const key of TABLE_FILTER_KEYS) {
    if (!Object.hasOwn(value as object, key)) continue;
    const v = value[key];
    if (Array.isArray(v) && v.length) {
      next[key] = v as string[];
    } else {
      delete next[key];
    }
  }
  return next;
};

const criteriaToSearchValues = (
  criteria: RumFilterCriteria,
  labelOf: (k: RumCriteriaKey) => string
): ISearchValue[] => {
  const result: ISearchValue[] = [];
  for (const key of SEARCH_DIMENSION_KEYS) {
    const vals = criteria[key];
    if (!vals?.length) continue;
    result.push({
      id: key,
      name: labelOf(key),
      values: vals.map(id => ({ id, name: id })),
    });
  }
  return result;
};

const criteriaToFilterValue = (criteria: RumFilterCriteria): FilterValue => {
  const fv: FilterValue = {};
  for (const key of TABLE_FILTER_KEYS) {
    const vals = criteria[key];
    if (vals?.length) fv[key] = vals;
  }
  return fv;
};

const rowMatchesCriteria = (row: RumAppRow, c: RumFilterCriteria): boolean => {
  const keys = Object.keys(c) as RumCriteriaKey[];
  for (const key of keys) {
    const vals = c[key];
    if (!vals?.length) continue;
    const rv = row[key];
    if (typeof rv === 'string' && !vals.includes(rv)) return false;
  }
  return true;
};

const RUM_TIME_RANGE: TimeRangeType = ['now-15m', 'now'];

const metricClass = (tier: MetricTier) => {
  if (tier === 'good') return 'rum-metric rum-metric--good';
  if (tier === 'warn') return 'rum-metric rum-metric--warn';
  if (tier === 'bad') return 'rum-metric rum-metric--bad';
  return 'rum-metric rum-metric--empty';
};

export default defineComponent({
  name: 'RumPage',
  directive: {
    OverflowTips,
  },
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const timeRange = shallowRef<TimeRangeType>(RUM_TIME_RANGE);
    const timezone = shallowRef(getDefaultTimezone());
    const refreshImmediate = shallowRef('');
    const refreshInterval = shallowRef(-1);
    const rumCriteria = shallowRef<RumFilterCriteria>({});
    const appListResource = shallowRef<RumTableItem[]>([]);
    const appAsyncResource = shallowRef<MetricMap>({});
    const tableSort = shallowRef<string | undefined>(undefined);
    /** 与 CommonTable 一致：disableDataPage 下需自行按页切片 data，total 须与当前列表条数一致 */
    const pageState = shallowRef({ currentPage: 1, pageSize: 10 });
    const showCreateApp = shallowRef(false);
    const showSdkReport = shallowRef(false);
    const sdkReportAppInfo = shallowRef<Partial<IRumAppConfig>>(null);
    const loading = shallowRef(false);

    const searchLabel = (k: RumCriteriaKey) => {
      const map: Record<RumCriteriaKey, string> = {
        appName: t('应用名称'),
        appAlias: t('展示名称'),
        appStatus: t('应用状态'),
        dataStatus: t('数据状态'),
      };
      return map[k];
    };

    const searchSelectDataSource = computed(() =>
      SEARCH_DIMENSION_KEYS.map(id => ({
        id,
        name: searchLabel(id),
        async: true,
      }))
    );

    const getMenuList: GetMenuListFunc = async (item, keyword) => {
      const kw = keyword.trim().toLowerCase();
      const list = searchSelectDataSource.value;
      if (!item?.id) {
        return list
          .filter(d => !kw || d.name.toLowerCase().includes(kw) || String(d.id).toLowerCase().includes(kw))
          .map(d => ({ ...d }));
      }
      const rowKey = item.id as keyof RumAppRow;
      const names = uniqSorted(tableData.value.map(r => String(r[rowKey])).filter(Boolean));
      const children: ICommonItem[] = names
        .filter(n => !kw || n.toLowerCase().includes(kw))
        .map(n => ({ id: n, name: n }));
      const meta = list.find(d => d.id === item.id);
      if (!meta) return [];
      return children;
    };

    const tableData = computed(() => {
      return buildRumAppRows(appListResource.value, appAsyncResource.value);
    });

    /**
     * 根据 tableSort 解析排序字段与方向
     * 格式：'-field' 降序 / 'field' 升序 / 空字符串 不排序
     */
    const parseSort = (sortStr: string | undefined): null | { desc: boolean; field: SortableMetricKey } => {
      if (!sortStr) return null;
      const desc = sortStr.startsWith('-');
      const field = (desc ? sortStr.slice(1) : sortStr) as SortableMetricKey;
      if (!SORTABLE_METRIC_KEYS.includes(field)) return null;
      return { field, desc };
    };

    const filteredTableData = computed(() => {
      let list = tableData.value;

      // 1. 筛选
      const c = rumCriteria.value;
      if (Object.keys(c).length) {
        list = list.filter(r => rowMatchesCriteria(r, c));
      }

      // 2. 排序（按 tableSort）
      const sort = parseSort(tableSort.value);
      if (sort) {
        const { field, desc } = sort;
        const sign = desc ? -1 : 1;
        list = [...list].sort((a: RumAppRow, b: RumAppRow) => {
          const va = a?.[field]?.value ?? null;
          const vb = b?.[field]?.value ?? null;
          // null/undefined 排到最后
          if (va == null && vb == null) return 0;
          if (va == null) return 1;
          if (vb == null) return -1;
          return (va - vb) * sign;
        });
      }

      return list;
    });

    watch(
      () => rumCriteria.value,
      () => {
        pageState.value = { ...pageState.value, currentPage: 1 };
      },
      { deep: true }
    );

    watch(
      () => filteredTableData.value.length,
      len => {
        const { pageSize, currentPage } = pageState.value;
        const maxPage = Math.max(1, Math.ceil(len / pageSize) || 1);
        if (currentPage > maxPage) {
          pageState.value = { ...pageState.value, currentPage: maxPage };
        }
      }
    );

    // const tablePageData = computed(() => {
    //   const list = filteredTableData.value;
    //   const total = list.length;
    //   const { currentPage, pageSize } = pageState.value;
    //   const start = (currentPage - 1) * pageSize;
    //   return {
    //     rows: list.slice(start, start + pageSize),
    //     pagination: { currentPage, pageSize, total },
    //   };
    // });

    const getRumList = async () => {
      loading.value = true;
      const { data } = await listApplication().catch(() => ({ columns: [], total: 0, data: [] }));
      appListResource.value = data;
      loading.value = false;
      getRumAsyncResource();
    };

    const getRumAsyncResource = () => {
      const [start, end] = handleTransformToTimestamp(timeRange.value);
      const apis = ['lcp_p75', 'js_error_rate', 'api_fail_rate'].map(key => {
        return listApplicationAsync({
          column: key,
          application_ids: appListResource.value.map(item => item.application_id),
          start_time: start,
          end_time: end,
        }).then((data: RumApplicationAsyncItem[]) => {
          return {
            data,
            key,
          };
        });
      });
      Promise.all(apis).then(res => {
        appAsyncResource.value = res.reduce((pre, cur) => {
          pre[cur.key] = cur.data;
          return pre;
        }, {});
      });
    };

    onMounted(() => {
      getRumList();
    });

    const handleConfigure = (row: RumAppRow) => {
      router.push({
        name: 'rumAppConfig',
        params: {
          appName: row.appName,
        },
      });
    };

    const handleSearchSelectUpdate = (v: ISearchValue[]) => {
      rumCriteria.value = mergeSearchValuesIntoCriteria(rumCriteria.value, v);
    };

    const handleTableFilterChange = (value: FilterValue) => {
      rumCriteria.value = mergeTableFilterIntoCriteria(rumCriteria.value, value);
    };

    const columns = computed<BaseTableColumn[]>(() => {
      // const appNameFilters = uniqSorted(tableData.value.map(r => r.appName)).map(v => ({ label: v, value: v }));
      // const appAliasFilters = uniqSorted(tableData.value.map(r => r.appAlias)).map(v => ({ label: v, value: v }));
      const appStatusFilters = uniqSorted(tableData.value.map(r => r.appStatus)).map(v => ({ label: v, value: v }));
      const dataStatusFilters = [
        { label: t('正常'), value: 'normal' },
        { label: t('无数据'), value: 'no_data' },
        { label: t('已禁用'), value: 'disabled' },
      ];
      return [
        {
          colKey: 'appName',
          title: () => (
            <span
              class='rum-table-header-title'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {t('应用名称')}
            </span>
          ),
          ellipsis: false,
          ellipsisTitle: false,
          thClassName: 'rum-th--filter',
          minWidth: 220,
          // ellipsis: false,
          // filter: {
          //   type: 'multiple',
          //   list: appNameFilters,
          //   resetValue: [],
          //   showConfirmAndReset: true,
          // },
          cellRenderer: (row => {
            const r = row as RumAppRow;
            return (
              <div class='rum-app-name-cell'>
                <div class='rum-app-icon'>
                  <i class='icon-monitor icon-mc-global' />
                </div>
                <div class='rum-app-name-text'>
                  <div
                    class='rum-app-domain'
                    v-overflow-tips={{
                      placement: 'top',
                    }}
                  >
                    {r.appAlias}
                  </div>
                  <div
                    class='rum-app-alias'
                    v-overflow-tips={{
                      placement: 'top',
                    }}
                  >
                    {r.appName}
                  </div>
                </div>
              </div>
            );
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
        {
          colKey: 'appAlias',
          title: () => (
            <span
              class='rum-table-header-title'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {t('展示名称')}
            </span>
          ),
          thClassName: 'rum-th--filter',
          width: 140,
          ellipsis: false,
          ellipsisTitle: false,
          // filter: {
          //   type: 'multiple',
          //   list: appAliasFilters,
          //   resetValue: [],
          //   showConfirmAndReset: true,
          // },
          cellRenderer: (row => {
            const r = row as RumAppRow;
            return (
              <span
                class='rum-table-content-cell'
                v-overflow-tips={{
                  placement: 'top',
                }}
              >
                {r.appAlias}
              </span>
            );
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
        {
          colKey: 'appStatus',
          title: t('应用状态'),
          thClassName: 'rum-th--filter',
          width: 100,
          ellipsis: false,
          ellipsisTitle: true,
          filter: {
            type: 'multiple',
            list: appStatusFilters,
            resetValue: [],
            showConfirmAndReset: true,
          },
          cellRenderer: (row => {
            const r = row as RumAppRow;
            return <span>{r.appStatus}</span>;
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
        {
          colKey: 'description',
          title: () => (
            <span
              class='rum-table-header-title'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {t('描述')}
            </span>
          ),
          minWidth: 160,
          ellipsis: false,
          ellipsisTitle: false,
          cellRenderer: (row => {
            const r = row as RumAppRow;
            return <span>{r.description || '--'}</span>;
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
        ...SORTABLE_METRIC_KEYS.map(key => ({
          colKey: key,
          title: () => (
            <span
              class='rum-table-header-title'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {t(METRIC_COLUMN_TITLES[key])}
            </span>
          ),
          thClassName: 'rum-th--dotted',
          width: 110,
          sorter: true,
          ellipsis: false,
          ellipsisTitle: false,
          cellRenderer: (row => {
            const r = row as RumAppRow;
            const metric = r[key];
            return <span class={metricClass(metric.tier)}>{metric.display}</span>;
          }) as unknown as BaseTableColumn['cellRenderer'],
        })),
        {
          colKey: 'dataStatus',
          title: t('数据状态'),
          thClassName: 'rum-th--filter',
          width: 160,
          ellipsis: false,
          ellipsisTitle: true,
          filter: {
            type: 'multiple',
            list: dataStatusFilters,
            resetValue: [],
            showConfirmAndReset: true,
          },
          cellRenderer: (row => {
            const r = row as RumAppRow;
            if (r.dataStatus === 'normal') {
              return (
                <span class='rum-data-status-text rum-data-status-text--ok'>
                  <i class='icon-monitor icon-duihao rum-data-status rum-data-status--ok' />
                  {r.dataStatusText}
                </span>
              );
            }
            if (r.dataStatus === 'no_data') {
              return (
                <span class='rum-data-status-text rum-data-status-text--warn'>
                  <i class='icon-monitor icon-warning rum-data-status rum-data-status--warn' />
                  {r.dataStatusText}
                </span>
              );
            }
            return (
              <span class='rum-data-status-text rum-data-status-text--danger'>
                <i class='icon-monitor icon-remind rum-data-status rum-data-status--danger' />
                {r.dataStatusText}
              </span>
            );
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
        {
          colKey: 'operations',
          title: () => (
            <span
              class='rum-table-header-title'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {t('操作')}
            </span>
          ),
          width: 180,
          ellipsis: false,
          ellipsisTitle: false,
          cellRenderer: (row => {
            const r = row as RumAppRow;
            return (
              <Button
                class='rum-op-link'
                theme='primary'
                text
                onClick={() => handleConfigure(r)}
              >
                {t('配置')}
              </Button>
            );
          }) as unknown as BaseTableColumn['cellRenderer'],
        },
      ];
    });

    const tableSettings = computed<BkUiSettings>(() => ({
      fields: [
        { label: t('应用名称'), field: 'appName' },
        { label: t('展示名称'), field: 'appAlias' },
        { label: t('应用状态'), field: 'appStatus' },
        { label: t('描述'), field: 'description' },
        ...SORTABLE_METRIC_KEYS.map(key => ({ label: t(METRIC_COLUMN_TITLES[key]), field: key, disabled: true })),
        { label: t('数据状态'), field: 'dataStatus', disabled: true },
        { label: t('操作'), field: 'operations', disabled: true },
      ],
      checked: ['appName', 'appAlias', 'appStatus', 'description', ...SORTABLE_METRIC_KEYS, 'dataStatus', 'operations'],
    }));

    const handleTimeRangeChange = (value: TimeRangeType) => {
      timeRange.value = value;
      getRumList();
    };

    const handleTimezoneChange = (value: string) => {
      timezone.value = value;
      updateTimezone(value);
    };

    const handleImmediateRefreshChange = () => {
      refreshImmediate.value = random(5).toString();
      getRumList();
    };

    const handleRefreshIntervalChange = (value: number) => {
      refreshInterval.value = value;
    };

    const handleSortChange = (sort: string | string[]) => {
      tableSort.value = Array.isArray(sort) ? sort[0] : sort;
    };

    const handleCurrentPageChange = (page: number) => {
      pageState.value = { ...pageState.value, currentPage: page };
    };

    const handlePageSizeChange = (pageSize: number) => {
      pageState.value = { ...pageState.value, pageSize, currentPage: 1 };
    };

    const handleCreateApp = () => {
      /** 接入创建应用流程（接口联调时补充） */
      handleCreateAppShowChange(true);
    };

    const handleCreateAppShowChange = (show: boolean) => {
      showCreateApp.value = show;
    };
    const handleCreateAppSuccess = params => {
      sdkReportAppInfo.value = params;
      handleCreateAppShowChange(false);
      handleSdkReportShowChange(true);
      getRumList();
    };
    const handleSdkReportShowChange = (show: boolean) => {
      showSdkReport.value = show;
    };

    return () => (
      <div class='rum-page'>
        <div class='rum-nav-title'>
          <CommonHeader
            hideFeature={['gotoOld']}
            refreshImmediate={refreshImmediate.value}
            refreshInterval={refreshInterval.value}
            timeRange={timeRange.value}
            timezone={timezone.value}
            onImmediateRefreshChange={handleImmediateRefreshChange}
            onRefreshIntervalChange={handleRefreshIntervalChange}
            onTimeRangeChange={handleTimeRangeChange}
            onTimezoneChange={handleTimezoneChange}
          >
            {{
              left: () => <div class='rum-page-title'>{t('route-RUM')}</div>,
            }}
          </CommonHeader>
        </div>

        <div class='rum-content'>
          <div class='rum-card'>
            <div class='rum-toolbar'>
              <Button
                theme='primary'
                onClick={handleCreateApp}
              >
                <span class='rum-toolbar-btn-inner'>
                  <i class='icon-monitor icon-mc-plus-fill' />
                  {t('新建应用')}
                </span>
              </Button>
              <div class='rum-search'>
                <SearchSelect
                  class='rum-search-select'
                  data={searchSelectDataSource.value}
                  getMenuList={getMenuList}
                  modelValue={criteriaToSearchValues(rumCriteria.value, searchLabel)}
                  placeholder={t('搜索 应用名称、展示名称、应用状态')}
                  clearable
                  onUpdate:modelValue={handleSearchSelectUpdate}
                />
              </div>
            </div>

            <div class='rum-table-wrap'>
              <CommonTable
                columns={columns.value}
                // data={tablePageData.value.rows as unknown as Record<string, unknown>[]}
                data={filteredTableData.value as unknown as Record<string, unknown>[]}
                filterValue={criteriaToFilterValue(rumCriteria.value)}
                loading={loading.value}
                // pagination={tablePageData.value.pagination}
                rowKey='id'
                sort={tableSort.value}
                tableSettings={tableSettings.value}
                autoFillSpace
                onCurrentPageChange={handleCurrentPageChange}
                onFilterChange={handleTableFilterChange}
                onPageSizeChange={handlePageSizeChange}
                onSortChange={handleSortChange}
              />
            </div>
          </div>
        </div>

        <CreateApp
          show={showCreateApp.value}
          onShowChange={handleCreateAppShowChange}
          onSuccess={handleCreateAppSuccess}
        />
        <SDKReport
          appInfo={sdkReportAppInfo.value}
          show={showSdkReport.value}
          onShowChange={handleSdkReportShowChange}
        />
      </div>
    );
  },
});
