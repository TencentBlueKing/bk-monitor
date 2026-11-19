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
import { type PropType, computed, defineComponent, nextTick, onScopeDispose, shallowRef, watch } from 'vue';

import { type SortInfo, type TableProps, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionExecution } from '../../composables/use-collection-execution';
import { useCollectionHistory } from '../../composables/use-collection-history';
import { getCollectionExecution } from '../../services/collection-history';
import {
  collectionMethodLabels,
  collectionTypeLabels,
  formatCollectionTime,
  scheduleLabels,
} from '../../utils/collection';
import {
  canViewExecution,
  createHistoryFilters,
  executionConfiguration,
  executionRowKey,
  executionSelection,
  executionStatusLabels,
  formatExecutionDuration,
  hostErrorTypeMessage,
  taskColumnMinWidth,
} from '../../utils/collection-history';
import CollectionExecutionAction from './collection-execution-action';
import CollectionExecutionDetail from './collection-execution-detail';
import CollectionExecutionStatus from './collection-execution-status';
import CollectionFilters from './collection-filters';
import EmptyStatus from '@/components/empty-status/empty-status';
import { useTableColumnsCache } from '@/hooks/use-table-columns-cache';
import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

import type { SelectionRange } from '../../types';
import type { CollectionPayload } from '../../types/collection';
import type {
  CollectionExecution,
  CollectionHistoryFilters,
  CollectionResultSelection,
  CollectionTaskColumn,
} from '../../types/collection-history';

import './collection-history.scss';

const skeletonRows = Array.from({ length: 10 }, (_, index) => ({ executionKey: `loading-${index}` }));

/** 表格固定配置项（表头吸顶、横向滚动条吸底），滚动容器为任务历史列表 .collection-history-scroll */
const historyTableAffixed = { container: '.collection-history-scroll' };

// 距底部多少像素内视为触底，触发加载下一页
const SCROLL_END_THRESHOLD = 80;
// 触底加载后视口上移的像素，需大于触底阈值才能跳出触底区间
const SCROLL_BACK_DISTANCE = 120;

// 列表存在过渡态行时静默刷新的间隔，静默刷新不展示 loading
const SILENT_REFRESH_INTERVAL = 5000;
// 同一列表连续静默刷新的上限：采集时长最长 300s（60 轮），结束后还会进入 parsing，
// 取 90 轮（450s）覆盖整段过渡态，避免采集未结束就停止轮询
const SILENT_REFRESH_LIMIT = 90;
// 需要轮询刷新的过渡态：采集中、解析中；到终态后停止
const pendingExecutionStatuses = ['running', 'parsing'];

// 未下发 task_columns 时回退的默认列，列名在渲染时翻译
const fallbackTaskColumns: CollectionTaskColumn[] = [
  { field: 'task_name', name: 'trace-任务名称', type: 'text' },
  { field: 'collection_type', name: '采集进程', type: 'text' },
  { field: 'hosts', name: '目标', type: 'text' },
  { field: 'schedule_type', name: '执行方式', type: 'text' },
  { field: 'started_at', name: '开始时间', type: 'datetime' },
  { field: 'duration_ms', name: '耗时', type: 'duration' },
  { field: 'execution_status', name: '采集结果', type: 'status' },
];

// 任务历史默认展示列，其余列可在列设置中开启；用户调整后走本地缓存
const defaultHistoryFields = [
  'task_name',
  'schedule_type',
  'collection_method',
  'collection_type',
  'creator',
  'scheduled_at',
  'started_at',
  'execution_status',
  'operations',
];

// 任务历史显示列与列宽的本地缓存 key
const historyColumnsStorageKey = 'trace_profiling_collection_history_columns';

// 有专属插槽的字段，其余字段按列类型渲染；用 Map 避免后端字段命中原型属性
const taskColumnSlots = new Map<string, string>([
  ['execution_status', 'status'],
  ['hosts', 'targets'],
  ['target_count', 'targets'],
  ['task_name', 'name'],
]);

export default defineComponent({
  name: 'CollectionHistory',
  props: {
    bizId: { type: Number, required: true },
    filters: { type: Object as PropType<CollectionHistoryFilters>, required: true },
    range: { type: Array as unknown as PropType<SelectionRange>, required: true },
    statusFilters: {
      type: Array as PropType<string[]>,
      default: () => Object.keys(executionStatusLabels).filter(status => status !== 'outdate'),
    },
    rangeError: { type: String, default: '' },
    // 按任务 ID 筛选时的任务名，用于筛选面板回显
    taskName: { type: String, default: '' },
    revision: { type: Number, required: true },
    // 每次查询重新解析时间表达式，使「近 N 分钟/小时」取最新边界
    resolveRange: { type: Function as PropType<() => SelectionRange>, default: undefined },
    timezone: { type: String, required: true },
    readonly: { type: Boolean, default: false },
  },
  emits: {
    change: (_value: CollectionHistoryFilters) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
    share: (_value?: CollectionResultSelection | null) => true,
    prefill: (_value: Omit<CollectionPayload, 'bk_biz_id'>) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const scrollContainer = shallowRef<HTMLElement>();
    const h = useCollectionHistory({
      bizId: computed(() => props.bizId),
      filters: computed(() => props.filters),
      range: computed(() => props.range),
      revision: computed(() => props.revision),
      resolveRange: () => props.resolveRange?.(),
    });
    const c = useCollectionExecution({
      bizId: computed(() => props.bizId),
      readonly: computed(() => props.readonly),
      revision: computed(() => props.revision),
      onUpdated: () => {
        Message({ theme: 'success', message: t('终止请求已提交') });
        h.refresh();
      },
      onCreated: () => {
        Message({ theme: 'success', message: t('采集任务已创建') });
        emit('created');
      },
    });
    // 回填需要执行配置快照，列表行不带配置，单独拉取后交给上层打开新建采集
    let prefillController: AbortController | undefined;
    async function prefill(execution: CollectionExecution) {
      c.dismissAction();
      prefillController?.abort();
      const current = new AbortController();
      prefillController = current;
      try {
        const snapshot = await getCollectionExecution(props.bizId, execution, current.signal);
        if (current.signal.aborted) return;
        emit('prefill', executionConfiguration(snapshot));
      } catch (e) {
        if (!current.signal.aborted)
          Message({ theme: 'error', message: (e as Error)?.message || t('配置快照加载失败，请重试') });
      }
    }
    onScopeDispose(() => prefillController?.abort());
    function reset() {
      emit('change', createHistoryFilters());
    }
    function loadVisiblePage() {
      const element = scrollContainer.value;
      if (!element || h.error.value) return;
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      if (distance < SCROLL_END_THRESHOLD) h.loadMore();
    }
    // 自动补页只在本页有进展时继续，避免重复页空转；用户滚动与「加载更多」不受此限制
    watch([h.loading, h.hasMore], async () => {
      await nextTick();
      const element = scrollContainer.value;
      if (!element || h.loading.value) return;
      const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
      // 新数据渲染后仍停在触底区间时把视口上移一段，避免滚动条留在最底部连续触发下一页
      if (h.canAutoFill.value && distance >= 0 && distance < SCROLL_END_THRESHOLD) {
        element.scrollTop = Math.max(0, element.scrollTop - SCROLL_BACK_DISTANCE);
      }
      if (h.canAutoFill.value) loadVisiblePage();
    });
    // 列表存在采集中/解析中的行时静默轮询刷新，不展示 loading；
    // 同一列表刷新 SILENT_REFRESH_LIMIT 次仍处于过渡态则视为超时并停止
    const hasPendingExecution = computed(() =>
      h.rows.value.some(row => pendingExecutionStatuses.includes(row.execution_status))
    );
    let silentRefreshCount = 0;
    let silentRefreshStopped = false;
    let silentRefreshTimer: null | ReturnType<typeof setTimeout> = null;
    function stopSilentRefresh() {
      if (!silentRefreshTimer) return;
      clearTimeout(silentRefreshTimer);
      silentRefreshTimer = null;
    }
    function scheduleSilentRefresh() {
      if (silentRefreshStopped) return;
      stopSilentRefresh();
      // 主动加载中、查询失败、无过渡态行或已达刷新上限时不再轮询
      if (h.loading.value || h.error.value || !hasPendingExecution.value) return;
      if (silentRefreshCount >= SILENT_REFRESH_LIMIT) return;
      silentRefreshTimer = setTimeout(async () => {
        silentRefreshTimer = null;
        if (silentRefreshStopped) return;
        silentRefreshCount += 1;
        await h.silentRefresh();
        if (silentRefreshStopped) return;
        // 过渡态行消失时 watch 会结束轮询，这里负责继续下一轮
        scheduleSilentRefresh();
      }, SILENT_REFRESH_INTERVAL);
    }
    watch(
      [h.loading, h.error, hasPendingExecution],
      () => {
        // 重新查询会先清空列表，此时重新计时；滚动加载更多不重置，避免同一列表超时后又被续期
        if (!h.rows.value.length || !hasPendingExecution.value) silentRefreshCount = 0;
        scheduleSilentRefresh();
      },
      { immediate: true }
    );
    onScopeDispose(() => {
      silentRefreshStopped = true;
      stopSilentRefresh();
    });
    // 执行详情内重新采集的提交状态也纳入 busy，避免提交期间触发自动刷新；
    // 详情关闭后不再计入，防止卸载时漏发复位导致 busy 卡住
    const executionBusy = shallowRef(false);
    watch(
      [h.loading, c.loading, c.busy, c.selected, executionBusy],
      () =>
        emit('busy', h.loading.value || c.loading.value || c.busy.value || (!!c.selected.value && executionBusy.value)),
      { immediate: true }
    );
    // 面板与表格列任一筛选生效时，空态区分无匹配结果与暂无数据
    const filtered = computed(
      () =>
        !!props.filters.task_id ||
        !!props.filters.task_name ||
        !!props.filters.status.length ||
        props.filters.schedule_types.length ||
        props.filters.ips.length ||
        props.filters.process_names.length ||
        props.filters.process_pids.length
    );
    // 列定义优先取后端下发的 task_columns，缺失时回退默认列并翻译列名
    const taskColumns = computed(() => {
      const columns = h.taskColumns.value.length
        ? h.taskColumns.value
        : fallbackTaskColumns.map(column => ({ ...column, name: t(column.name) }));
      const seenFields = new Set<string>();
      return columns.filter(column => {
        if (!column.field || column.field === 'operations' || seenFields.has(column.field)) return false;
        seenFields.add(column.field);
        return true;
      });
    });
    // 已生效筛选的摘要：key 优先取表格列标题，值优先取别名
    const filterSummary = computed(() => {
      const conditions: string[] = [];
      const append = (label: string, values: string[]) => {
        if (values.length) conditions.push(`${label}：${values.join(',')}`);
      };
      const columnTitle = (field: string, fallback: string) =>
        taskColumns.value.find(column => column.field === field)?.name || t(fallback);
      const taskName = props.filters.task_id
        ? props.taskName || String(props.filters.task_id)
        : props.filters.task_name;
      append('IP', props.filters.ips);
      append(t('任务'), taskName ? [taskName] : []);
      // 进程名与 PID 共用面板里的「进程」入口，摘要也合并到一项
      append(t('进程'), [...props.filters.process_names, ...props.filters.process_pids]);
      append(
        columnTitle('schedule_type', '执行方式'),
        props.filters.schedule_types.map(value => t((scheduleLabels as Record<string, string>)[value] || value))
      );
      append(
        columnTitle('execution_status', '采集结果'),
        props.filters.status.map(value => t((executionStatusLabels as Record<string, string>)[value] || value))
      );
      return conditions.join('; ');
    });
    // 有筛选且已拿到结果总数时展示摘要行；无结果交给空态，避免占住表格首行
    const showFilterSummary = computed(() => !!filterSummary.value && h.total.value !== null && !!h.rows.value.length);
    // 可配置的列 key：业务列 + 表格追加的操作列
    const columnKeys = computed(() => [...taskColumns.value.map(column => column.field), 'operations']);
    // 锁定列：任务名称与操作列是行入口，列设置中置灰且始终显示
    const lockedColumns = computed(() => ['task_name', 'operations'].filter(field => columnKeys.value.includes(field)));
    // 默认列取固定字段而非当前可用列，避免后端列未下发时把默认列写死在缓存里
    const { storageColumns, fieldsWidthConfig } = useTableColumnsCache({
      storageKey: historyColumnsStorageKey,
      defaultColumns: () => defaultHistoryFields,
      validColumnKeys: () => columnKeys.value,
    });
    // 列设置显示列：过滤掉后端已下线的列，并补回缓存里缺失的锁定列（旧缓存没有操作列）
    const displayColumns = computed(() => {
      const valid = new Set(columnKeys.value);
      return [...new Set([...storageColumns.value.filter(field => valid.has(field)), ...lockedColumns.value])];
    });
    // 列设置关闭时回写显示列，已下线的列不进入缓存
    function changeColumns(value: string[]) {
      const valid = new Set(columnKeys.value);
      storageColumns.value = [...new Set([...value.filter(field => valid.has(field)), ...lockedColumns.value])];
    }
    // 列宽拖拽后回写缓存
    function changeColumnWidths(value: Record<string, number>) {
      fieldsWidthConfig.value = value;
    }
    // tdesign 的 sorter: true 只负责图标与事件，本地排序需自行按 sortInfo 排序
    const sortInfo = shallowRef<null | SortInfo>(null);
    const tableRows = computed(() => {
      const rows = h.rows.value.map(row => ({ ...row, executionKey: executionRowKey(row) }));
      const info = sortInfo.value;
      const field = info?.sortBy;
      if (field !== 'started_at' && field !== 'finished_at') return rows;
      // 执行中的结束时间为 null，空值不参与数值比较、固定排在末尾
      return rows.sort((a, b) => {
        const av = typeof a[field] === 'number' ? a[field] : null;
        const bv = typeof b[field] === 'number' ? b[field] : null;
        if (av === null || bv === null) return av === bv ? 0 : av === null ? 1 : -1;
        return info?.descending ? bv - av : av - bv;
      });
    });
    function changeSort(value: TableSort) {
      const info = Array.isArray(value) ? value[0] : value;
      sortInfo.value = info?.sortBy ? info : null;
    }
    return {
      t,
      h,
      c,
      filtered,
      filterSummary,
      showFilterSummary,
      scrollContainer,
      taskColumns,
      displayColumns,
      lockedColumns,
      fieldsWidthConfig,
      tableRows,
      executionBusy,
      prefill,
      reset,
      loadVisiblePage,
      changeSort,
      changeColumns,
      changeColumnWidths,
    };
  },
  render() {
    const { h, c } = this;
    const showSkeleton = h.loading.value && !h.rows.value.length;
    // 已知业务字段保留原有渲染形态，其余按列类型兜底
    const renderTaskCell = (column: CollectionTaskColumn, row: CollectionExecution) => {
      const value = (row as unknown as Record<string, unknown>)[column.field];
      if (column.field === 'collection_type') return collectionTypeLabels[row.collection_type] || '--';
      if (column.field === 'collection_method') return collectionMethodLabels[row.collection_method] || '--';
      if (column.field === 'schedule_type') return this.t(scheduleLabels[row.schedule_type]);
      if (column.type === 'datetime') return formatCollectionTime(typeof value === 'number' ? value : 0, this.timezone);
      if (column.type === 'duration') return formatExecutionDuration(typeof value === 'number' ? value : null);
      return value === null || value === undefined || value === '' ? '--' : String(value);
    };
    const baseColumns: TableProps['columns'] = [
      ...this.taskColumns.map<NonNullable<TableProps['columns']>[number]>(column => {
        // 初始列宽优先取缓存值，minWidth 作为拖拽下限
        const minWidth = taskColumnMinWidth(column);
        const width = this.fieldsWidthConfig[column.field] || minWidth;
        return {
          colKey: column.field,
          title: column.name || column.field,
          width,
          minWidth,
          resizable: true,
          ellipsis: column.type === 'text',
          // 任务名称吸附在最左侧；固定列需排在列首，故同时调整列顺序
          ...(column.field === 'task_name' ? { fixed: 'left' as const } : {}),
          cell:
            taskColumnSlots.get(column.field) || ((_, { row }) => renderTaskCell(column, row as CollectionExecution)),
          ...(column.field === 'schedule_type'
            ? {
                filter: {
                  type: 'multiple',
                  resetValue: [],
                  showConfirmAndReset: true,
                  list: Object.keys(scheduleLabels).map(value => ({ value, label: this.t(scheduleLabels[value]) })),
                },
              }
            : {}),
          ...(column.field === 'started_at' || column.field === 'finished_at' ? { sorter: true } : {}),
          ...(column.field === 'execution_status'
            ? {
                filter: {
                  type: 'multiple',
                  resetValue: [],
                  showConfirmAndReset: true,
                  list: this.statusFilters
                    .filter(value => Object.hasOwn(executionStatusLabels, value))
                    .map(value => ({ value, label: this.t(executionStatusLabels[value]) })),
                },
              }
            : {}),
        };
      }),
      {
        colKey: 'operations',
        title: this.t('操作'),
        width: 180,
        fixed: 'right',
        resizable: false,
        cell: 'operations',
      },
    ];
    // 任务名称吸附在最左侧，不在首位时前置到列首
    const taskNameColumn = baseColumns.find(column => column.colKey === 'task_name');
    const columns = taskNameColumn
      ? [taskNameColumn, ...baseColumns.filter(column => column !== taskNameColumn)]
      : baseColumns;
    return (
      <section class='collection-tab-panel collection-history-panel'>
        <CollectionFilters
          bizId={this.bizId}
          filters={this.filters}
          range={this.range}
          taskName={this.taskName}
          autoQuery
          onChange={value => this.$emit('change', value)}
          onRefresh={h.refresh}
        />
        {this.rangeError && (
          <Alert
            theme='danger'
            title={this.rangeError}
          />
        )}
        <div
          ref='scrollContainer'
          class='collection-history-scroll'
          aria-busy={h.loading.value}
          onScroll={this.loadVisiblePage}
        >
          {/* 表格内置的列筛选与外部 filters 保持同步，任一列变更都整体回传 */}
          <PrimaryTable
            v-slots={{
              // 请求失败与筛选无结果统一在空态中展示
              empty: () => {
                const error = h.error.value;
                return (
                  <EmptyStatus
                    textMap={{ 500: error || this.t('数据获取异常') }}
                    type={error ? '500' : this.filtered ? 'search-empty' : 'empty'}
                    onOperation={error ? h.refresh : this.reset}
                  />
                );
              },
              name: ({ row }: { row: CollectionExecution }) => (
                <span
                  class='collection-history-task-name'
                  v-tippy={this.t('查看本次任务执行详情')}
                  onClick={() => c.open(row)}
                >
                  <span>{row.task_name}</span>
                </span>
              ),
              targets: ({ row }: { row: CollectionExecution }) => (
                <span v-tippy={{ content: (row.hosts || []).map(host => host.ip).join('，'), allowHTML: false }}>
                  {this.t('共 {n} 台主机', { n: row.target_count ?? row.hosts?.length ?? 0 })}
                </span>
              ),
              status: ({ row }: { row: CollectionExecution }) => {
                const message = hostErrorTypeMessage(row.error_type);
                return (
                  <CollectionExecutionStatus
                    message={message ? this.t(message) : ''}
                    status={row.execution_status}
                  />
                );
              },
              operations: ({ row }: { row: CollectionExecution }) => (
                <div class='collection-row-actions'>
                  {/* 禁用按钮不派发鼠标事件，tooltip 需挂在外层元素上 */}
                  <span
                    v-tippy={this.t(
                      canViewExecution(row) ? '查看本次执行各主机的采集结果' : '本次采集暂无可查看的结果'
                    )}
                  >
                    <Button
                      disabled={!canViewExecution(row)}
                      theme='primary'
                      text
                      onClick={() => this.$emit('result', executionSelection(row), false)}
                    >
                      {this.t('查看结果')}
                    </Button>
                  </span>
                  <span
                    v-tippy={this.t(
                      this.readonly
                        ? '暂无采集操作权限'
                        : row.execution_status === 'running'
                          ? '仅终止本次采集，保留原有执行计划'
                          : '使用历史配置重新执行本次采集'
                    )}
                  >
                    <Button
                      disabled={this.readonly || c.busy.value}
                      theme='primary'
                      text
                      onClick={() => c.requestAction(row.execution_status === 'running' ? 'cancel' : 'rerun', row)}
                    >
                      {this.t(row.execution_status === 'running' ? '终止' : '重新执行')}
                    </Button>
                  </span>
                </div>
              ),
              // 面板筛选与列筛选统一在这里汇总，覆盖表格内置的筛选结果行
              firstFullRow: () =>
                this.showFilterSummary ? (
                  <div class='t-table__row-filter-inner'>
                    <div class='t-table__filter-result'>
                      <span>
                        {this.t('搜索“{result}”，找到 {count} 条结果', {
                          result: this.filterSummary,
                          count: this.h.total.value ?? 0,
                        })}
                      </span>
                      <Button
                        theme='primary'
                        text
                        onClick={this.reset}
                      >
                        {this.t('清空筛选')}
                      </Button>
                    </div>
                  </div>
                ) : null,
            }}
            bkUiSettings={{
              checked: this.displayColumns,
              disabled: this.lockedColumns,
              rowSize: 'mini',
            }}
            columns={columns.map(column =>
              showSkeleton
                ? {
                    ...column,
                    cell: (render, { rowIndex }) =>
                      render(TraceCellSkeleton, { field: column.colKey, index: rowIndex }),
                  }
                : column
            )}
            filterValue={{
              execution_status: this.filters.status,
              schedule_type: this.filters.schedule_types,
            }}
            data={showSkeleton ? skeletonRows : this.tableRows}
            // 常关内置筛选结果行：筛选结果统一由 firstFullRow 渲染，空态仍由 empty 插槽接管
            filterRow={() => null}
            headerAffixedTop={historyTableAffixed}
            horizontalScrollAffixedBottom={historyTableAffixed}
            hover={!showSkeleton}
            needCustomScroll={false}
            resizable={true}
            rowKey='executionKey'
            size='small'
            onBkUiSettingsChange={value => this.changeColumns(value.columns)}
            onColumnResizeChange={context => this.changeColumnWidths(context.columnsWidth)}
            onFilterChange={value =>
              this.$emit('change', {
                ...this.filters,
                status: (value.execution_status || []) as string[],
                schedule_types: (value.schedule_type || []) as string[],
              })
            }
            onSortChange={this.changeSort}
          />
          {/* 已有数据时追加加载失败，表格保留数据，仅保留重试入口 */}
          {!!h.error.value && !!h.rows.value.length && (
            <div class='collection-history-error'>
              <Button
                v-tippy={this.t('重新加载采集任务历史')}
                onClick={h.loadMore}
              >
                {this.t('重试')}
              </Button>
            </div>
          )}
          {!!h.rows.value.length && (
            <div class='collection-history-more'>
              {h.hasMore.value ? (
                <Button
                  v-tippy={this.t('加载下一批任务执行记录')}
                  loading={h.loading.value}
                  theme='primary'
                  text
                  onClick={h.loadMore}
                >
                  {this.t('加载更多')}
                </Button>
              ) : (
                this.t('已加载全部记录')
              )}
            </div>
          )}
        </div>
        {c.selected.value && (
          <CollectionExecutionDetail
            bizId={this.bizId}
            controller={c}
            readonly={this.readonly}
            timezone={this.timezone}
            onBusy={value => {
              this.executionBusy = value;
            }}
            onCreated={() => this.$emit('created')}
            onRenamed={() => {
              // 改名只影响这一次执行，重新查询让列表名称同步
              h.refresh();
            }}
            onResult={value => this.$emit('result', value, true)}
            onShare={value => this.$emit('share', value)}
          />
        )}
        <CollectionExecutionAction
          controller={c}
          readonly={this.readonly}
          onPrefill={this.prefill}
        />
      </section>
    );
  },
});
