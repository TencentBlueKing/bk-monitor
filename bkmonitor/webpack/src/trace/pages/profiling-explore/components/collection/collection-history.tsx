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
import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Dialog, Message, Radio, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionExecution } from '../../composables/use-collection-execution';
import { useCollectionHistory } from '../../composables/use-collection-history';
import { collectionTypeLabels, formatCollectionTime, scheduleLabels } from '../../utils/collection';
import {
  canViewExecution,
  createHistoryFilters,
  executionRowKey,
  executionSelection,
  executionStatusLabels,
  formatExecutionDuration,
  parseProcessSelection,
  processCandidateOptions,
  restoreProcessSelection,
} from '../../utils/collection-history';
import CollectionExecutionDetail from './collection-execution-detail';
import CollectionExecutionStatus from './collection-execution-status';
import EmptyStatus from '@/components/empty-status/empty-status';
import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

import type { SelectionRange } from '../../types';
import type {
  CollectionExecution,
  CollectionHistoryFilters,
  CollectionResultSelection,
} from '../../types/collection-history';

import './collection-history.scss';

const skeletonRows = Array.from({ length: 10 }, (_, index) => ({ executionKey: `loading-${index}` }));

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
    revision: { type: Number, required: true },
    timezone: { type: String, required: true },
    readonly: { type: Boolean, default: false },
  },
  emits: {
    change: (_value: CollectionHistoryFilters) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const draft = shallowRef(createHistoryFilters());
    const processSelection = shallowRef<string[]>([]);
    const scrollContainer = shallowRef<HTMLElement>();
    const h = useCollectionHistory({
      bizId: computed(() => props.bizId),
      filters: computed(() => props.filters),
      range: computed(() => props.range),
      revision: computed(() => props.revision),
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
    function syncDraft() {
      draft.value = { ...props.filters };
      processSelection.value = restoreProcessSelection(props.filters, processSelection.value);
    }
    function changeProcesses(values: string[]) {
      processSelection.value = values;
      draft.value = { ...draft.value, ...parseProcessSelection(values) };
    }
    function submit() {
      if (JSON.stringify(props.filters) === JSON.stringify(draft.value)) h.refresh();
      else emit('change', { ...draft.value });
    }
    function reset() {
      draft.value = createHistoryFilters();
      processSelection.value = [];
      submit();
    }
    function loadVisiblePage() {
      const element = scrollContainer.value;
      if (element && !h.error.value && element.scrollHeight - element.scrollTop - element.clientHeight < 80)
        h.loadMore();
    }
    watch(() => props.filters, syncDraft, { immediate: true });
    watch([h.loading, h.hasMore], () => nextTick(loadVisiblePage));
    watch([h.loading, c.loading, c.busy], () => emit('busy', h.loading.value || c.loading.value || c.busy.value), {
      immediate: true,
    });
    return { t, h, c, draft, processSelection, scrollContainer, changeProcesses, submit, reset, loadVisiblePage };
  },
  render() {
    const { h, c, draft } = this;
    const showSkeleton = h.loading.value && !h.rows.value.length;
    const options = (field: 'target' | 'task_name') =>
      (h.candidates.value[field] || []).map((item, index) => (
        <Select.Option
          id={String(item.value)}
          key={`${field}:${index}`}
          name={item.alias || String(item.value)}
        />
      ));
    const processOptions = processCandidateOptions(h.candidates.value, this.processSelection);
    const columns: TableProps['columns'] = [
      { colKey: 'task_name', title: this.t('任务名称'), minWidth: 220, ellipsis: true, cell: 'name' },
      {
        colKey: 'collection_type',
        title: this.t('采集进程'),
        width: 160,
        cell: (_, { row }) => collectionTypeLabels[row.collection_type] || '--',
      },
      { colKey: 'hosts', title: this.t('目标'), minWidth: 130, cell: 'targets' },
      {
        colKey: 'schedule_type',
        title: this.t('执行方式'),
        width: 140,
        cell: (_, { row }) => this.t(scheduleLabels[row.schedule_type]),
      },
      {
        colKey: 'started_at',
        title: this.t('开始时间'),
        width: 200,
        cell: (_, { row }) => formatCollectionTime(row.started_at, this.timezone),
      },
      {
        colKey: 'duration_ms',
        title: this.t('耗时'),
        width: 100,
        cell: (_, { row }) => formatExecutionDuration(row.duration_ms),
      },
      {
        colKey: 'execution_status',
        title: this.t('采集结果'),
        width: 140,
        cell: 'status',
        filter: {
          type: 'single',
          list: this.statusFilters
            .filter(value => Object.hasOwn(executionStatusLabels, value))
            .map(value => ({ value, label: this.t(executionStatusLabels[value]) })),
        },
      },
      { colKey: 'operations', title: this.t('操作'), width: 180, fixed: 'right', cell: 'operations' },
    ];
    const filtered =
      !!this.filters.task_name ||
      !!this.filters.status ||
      this.filters.ips.length ||
      this.filters.process_names.length ||
      this.filters.process_pids.length;
    return (
      <section class='collection-tab-panel collection-history-panel'>
        <div class='collection-history-filters'>
          <label>
            <span>IP</span>
            <Select
              loading={h.candidateLoading.value}
              modelValue={draft.ips}
              allowCreate
              collapseTags
              filterable
              multiple
              onChange={value => {
                this.draft = { ...draft, ips: value || [] };
              }}
            >
              {options('target')}
            </Select>
          </label>
          <label>
            <span v-tippy={this.t('任务名称按关键词匹配，可能包含同名或近似名称任务')}>{this.t('任务')}</span>
            <Select
              loading={h.candidateLoading.value}
              modelValue={draft.task_name}
              allowCreate
              filterable
              onChange={value => {
                this.draft = { ...draft, task_name: String(value || '') };
              }}
            >
              {options('task_name')}
            </Select>
          </label>
          <label>
            <span>{this.t('进程')}</span>
            <Select
              loading={h.candidateLoading.value}
              modelValue={this.processSelection}
              placeholder={this.t('进程名或 PID')}
              allowCreate
              collapseTags
              filterable
              multiple
              onChange={value => this.changeProcesses(value || [])}
            >
              {processOptions.map(option => (
                <Select.Option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </Select>
          </label>
          <div class='collection-history-status-filter'>
            <span>{this.t('状态')}</span>
            <Radio.Group
              class='collection-history-status-options'
              modelValue={draft.status}
              type='capsule'
              onChange={value => {
                this.draft = { ...draft, status: String(value) };
              }}
            >
              {['', 'running', 'succeed', 'partial_succeed', 'failed'].map(status => (
                <Radio.Button
                  key={status}
                  label={status}
                >
                  {status ? <CollectionExecutionStatus status={status} /> : this.t('全部')}
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>
          <div class='collection-history-query'>
            <Button
              theme='primary'
              onClick={this.submit}
            >
              {this.t('查询')}
            </Button>
            <Button onClick={this.reset}>{this.t('重置')}</Button>
          </div>
        </div>
        {h.candidateError.value && (
          <Alert
            theme='warning'
            title={h.candidateError.value}
          >
            <Button
              theme='primary'
              text
              onClick={h.loadCandidates}
            >
              {this.t('重试')}
            </Button>
          </Alert>
        )}
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
          <PrimaryTable
            columns={columns.map(column =>
              showSkeleton
                ? {
                    ...column,
                    cell: (render, { rowIndex }) =>
                      render(TraceCellSkeleton, { field: column.colKey, index: rowIndex }),
                  }
                : column
            )}
            data={
              showSkeleton ? skeletonRows : h.rows.value.map(row => ({ ...row, executionKey: executionRowKey(row) }))
            }
            filterValue={{ execution_status: this.filters.status }}
            hover={!showSkeleton}
            rowKey='executionKey'
            size='small'
            onFilterChange={value =>
              this.$emit('change', { ...this.filters, status: String(value.execution_status || '') })
            }
          >
            {{
              empty: () =>
                h.error.value ? null : (
                  <EmptyStatus
                    type={filtered ? 'search-empty' : 'empty'}
                    onOperation={this.reset}
                  />
                ),
              name: ({ row }: { row: CollectionExecution }) => (
                <Button
                  theme='primary'
                  text
                  onClick={() => c.open(row)}
                >
                  {row.task_name}
                </Button>
              ),
              targets: ({ row }: { row: CollectionExecution }) => (
                <span v-tippy={{ content: row.hosts.map(host => host.ip).join('，'), allowHTML: false }}>
                  {this.t('共 {n} 台主机', { n: row.target_count })}
                </span>
              ),
              status: ({ row }: { row: CollectionExecution }) => (
                <CollectionExecutionStatus status={row.execution_status} />
              ),
              operations: ({ row }: { row: CollectionExecution }) => (
                <div class='collection-row-actions'>
                  <Button
                    disabled={!canViewExecution(row)}
                    theme='primary'
                    text
                    onClick={() => this.$emit('result', executionSelection(row), false)}
                  >
                    {this.t('查看结果')}
                  </Button>
                  <Button
                    disabled={this.readonly || c.busy.value}
                    theme='primary'
                    text
                    onClick={() => c.requestAction(row.execution_status === 'running' ? 'cancel' : 'rerun', row)}
                  >
                    {this.t(row.execution_status === 'running' ? '终止' : '重新执行')}
                  </Button>
                </div>
              ),
            }}
          </PrimaryTable>
          {h.error.value && (
            <div class='collection-history-error'>
              <Alert
                theme='danger'
                title={h.error.value}
              />
              <Button onClick={h.rows.value.length ? h.loadMore : h.refresh}>{this.t('重试')}</Button>
            </div>
          )}
          {!!h.rows.value.length && (
            <div class='collection-history-more'>
              {h.hasMore.value ? (
                <Button
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
            controller={c}
            readonly={this.readonly}
            timezone={this.timezone}
            onResult={value => this.$emit('result', value, true)}
          />
        )}
        <Dialog
          title={this.t(
            c.pending.value?.action === 'cancel'
              ? '确认终止本次采集？'
              : c.pending.value?.action === 'retry'
                ? '确认仅重试失败项？'
                : '确认重新执行？'
          )}
          beforeClose={() => !c.busy.value}
          isShow={!!c.pending.value}
          quickClose={false}
          transfer={false}
          onClosed={c.dismissAction}
        >
          {{
            default: () => (
              <>
                <p>{c.pending.value?.execution.task_name}</p>
                <p>
                  {this.t(
                    c.pending.value?.action === 'cancel'
                      ? '仅终止当前执行轮次，不影响后续执行计划。'
                      : '将使用本次执行的历史配置创建一次立即采集，原有执行计划保持不变。'
                  )}
                </p>
                {c.pending.value?.action === 'retry' && <p>{this.t('只重新采集失败和超时主机。')}</p>}
                {c.actionError.value && (
                  <Alert
                    theme='danger'
                    title={c.actionError.value}
                  />
                )}
              </>
            ),
            footer: () => (
              <>
                <Button
                  disabled={this.readonly}
                  loading={c.busy.value}
                  theme='primary'
                  onClick={c.confirmAction}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  disabled={c.busy.value}
                  onClick={c.dismissAction}
                >
                  {this.t('取消')}
                </Button>
              </>
            ),
          }}
        </Dialog>
      </section>
    );
  },
});
