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
import { Alert, Button, Dialog, Exception, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionExecution } from '../../composables/use-collection-execution';
import { useCollectionResults } from '../../composables/use-collection-results';
import { collectionTypeLabels, formatCollectionTime } from '../../utils/collection';
import { createHistoryFilters } from '../../utils/collection-history';
import {
  canViewHostResult,
  resultExecutionKey,
  resultRowKey,
  resultSelection,
  resultUnavailableReason,
} from '../../utils/collection-results';
import { createViewState } from '../../utils/query';
import emptyIllustration from './assets/collection-results-empty.svg';
import CollectionExecutionAction from './collection-execution-action';
import CollectionExecutionDetail from './collection-execution-detail';
import CollectionExecutionStatus from './collection-execution-status';
import CollectionFilters from './collection-filters';
import CollectionResultDetail from './collection-result-detail';
import EmptyStatus from '@/components/empty-status/empty-status';
import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

import type { SelectionRange } from '../../types';
import type { CollectionQueryState } from '../../types/collection';
import type { CollectionResultSelection } from '../../types/collection-history';
import type { CollectionHostResult, CollectionResultsState } from '../../types/collection-results';

import './collection-history.scss';
import './collection-results.scss';

const skeletonRows = Array.from({ length: 10 }, (_, index) => ({ resultKey: `loading-${index}` }));

export default defineComponent({
  name: 'CollectionResults',
  props: {
    bizId: { type: Number, required: true },
    state: { type: Object as PropType<CollectionResultsState>, required: true },
    selection: { type: Object as PropType<CollectionResultSelection>, default: null },
    range: { type: Array as unknown as PropType<SelectionRange>, default: null },
    rangeError: { type: String, default: '' },
    revision: { type: Number, required: true },
    timezone: { type: String, required: true },
    readonly: Boolean,
  },
  emits: {
    change: (_value: Partial<CollectionQueryState>) => true,
    created: () => true,
    create: () => true,
    share: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const scrollContainer = shallowRef<HTMLElement>();
    const h = useCollectionResults({
      bizId: computed(() => props.bizId),
      state: computed(() => props.state),
      range: computed(() => props.range),
      revision: computed(() => props.revision),
      readonly: computed(() => props.readonly),
      onCreated: () => emit('created'),
    });
    const c = useCollectionExecution({
      bizId: computed(() => props.bizId),
      readonly: computed(() => props.readonly),
      revision: computed(() => props.revision),
      onUpdated: h.refresh,
      onCreated: () => {
        Message({ theme: 'success', message: t('采集任务已创建') });
        emit('created');
      },
    });
    const tableRows = computed(() => h.rows.value.map(row => ({ ...row, resultKey: resultRowKey(row) })));
    const selectedRow = computed(() =>
      h.records.value.find(
        row =>
          props.selection?.scope === 'host' &&
          row.bk_host_id === props.selection.bk_host_id &&
          row.scheduled_at === props.selection.scheduled_at &&
          row.task.schedule_type === props.selection.schedule_type &&
          row.task.task_id === props.selection.task_id
      )
    );
    const filtered = computed(() => {
      const value = props.state.filters;
      return !!(
        value.ips.length ||
        value.task_name ||
        value.process_names.length ||
        value.process_pids.length ||
        value.status
      );
    });
    function patch(value: Partial<CollectionResultsState>) {
      emit('change', { results: { ...props.state, ...value } });
    }
    function open(row: CollectionHostResult) {
      if (!canViewHostResult(row)) return;
      emit('change', {
        result: resultSelection(row),
        results: { ...props.state, dataType: '', view: createViewState() },
      });
    }
    function openExecution(row: CollectionHostResult) {
      c.open({ ...resultExecutionKey(row), task_name: row.task.name, execution_status: 'unknown' });
    }
    function loadVisiblePage() {
      const element = scrollContainer.value;
      if (element && !h.error.value && element.scrollHeight - element.scrollTop - element.clientHeight < 80)
        h.loadMore();
    }
    function reset() {
      patch({ filters: createHistoryFilters() });
    }
    watch([h.loading, h.hasMore], () => nextTick(loadVisiblePage));
    watch(
      [h.loading, h.busy, c.loading, c.busy],
      () => emit('busy', h.loading.value || h.busy.value || c.loading.value || c.busy.value),
      { immediate: true }
    );
    return {
      t,
      h,
      c,
      tableRows,
      selectedRow,
      filtered,
      scrollContainer,
      patch,
      open,
      openExecution,
      loadVisiblePage,
      reset,
    };
  },
  render() {
    const { h, c } = this;
    const showSkeleton = h.loading.value && !h.rows.value.length;
    const columns: TableProps['columns'] = [
      { colKey: 'ip', title: this.t('目标 IP'), minWidth: 160, cell: 'ip' },
      { colKey: 'processes', title: this.t('采集进程'), minWidth: 180, cell: 'processes' },
      {
        colKey: 'collection_type',
        title: this.t('采集类型'),
        minWidth: 150,
        cell: (_, { row }) => collectionTypeLabels[row.collection_type] || '--',
      },
      {
        colKey: 'started_at',
        title: this.t('采集时间'),
        width: 190,
        cell: (_, { row }) => formatCollectionTime(row.started_at, this.timezone),
      },
      { colKey: 'task', title: this.t('采集任务名'), minWidth: 220, ellipsis: true, cell: 'task' },
      {
        colKey: 'status',
        title: this.t('状态'),
        width: 130,
        cell: (_, { row }) => (
          <CollectionExecutionStatus
            status={row.status}
            result
          />
        ),
      },
      { colKey: 'row-operation', title: this.t('操作'), width: 176, fixed: 'right', cell: 'operations' },
    ];
    const resultLink = (row: CollectionHostResult, text: string) => (
      <span v-tippy={this.t(canViewHostResult(row) ? '查看当前主机的采集结果' : resultUnavailableReason(row))}>
        <Button
          disabled={!canViewHostResult(row)}
          theme='primary'
          text
          onClick={() => this.open(row)}
        >
          {text}
        </Button>
      </span>
    );
    return (
      <section class='collection-tab-panel collection-history-panel collection-results-panel'>
        <CollectionFilters
          candidates={h.candidates.value}
          filters={this.state.filters}
          loading={h.candidateLoading.value}
          results
          onChange={filters => this.patch({ filters })}
          onRefresh={h.refresh}
        />
        {this.state.execution && (
          <div class='collection-results-scope'>
            <span>{this.t('当前仅显示本次任务执行的采集结果')}</span>
            <Button
              v-tippy={this.t('取消当前执行范围，查看所选时间内的全部采集结果')}
              theme='primary'
              text
              onClick={() =>
                this.$emit('change', {
                  result: null,
                  results: { ...this.state, execution: null, filters: createHistoryFilters() },
                })
              }
            >
              {this.t('查看全部采集结果')}
            </Button>
          </div>
        )}
        {h.candidateError.value && (
          <Alert
            theme='warning'
            title={h.candidateError.value}
          >
            <Button
              v-tippy={this.t('重新加载筛选候选项')}
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
          {!showSkeleton && !h.rows.value.length && !h.error.value && !this.rangeError ? (
            this.filtered ? (
              <EmptyStatus
                type='search-empty'
                onOperation={this.reset}
              />
            ) : (
              <Exception
                class='collection-results-empty'
                scene='page'
                type='empty'
              >
                {{
                  type: () => (
                    <img
                      alt=''
                      src={emptyIllustration}
                    />
                  ),
                  default: () => (
                    <>
                      <h3>{this.t('暂无采集结果')}</h3>
                      <p>{this.t('请前往任务管理新建采集任务')}</p>
                      <Button
                        v-tippy={this.t(this.readonly ? '暂无采集操作权限' : '新建 Profiling 采集任务')}
                        disabled={this.readonly}
                        theme='primary'
                        outline
                        onClick={() => this.$emit('create')}
                      >
                        {this.t('去新建任务')}
                      </Button>
                    </>
                  ),
                }}
              </Exception>
            )
          ) : (
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
              bkUiSettings={{ disabled: ['ip'], rowSize: 'mini' }}
              data={showSkeleton ? skeletonRows : this.tableRows}
              hover={!showSkeleton}
              rowKey='resultKey'
              size='small'
            >
              {{
                empty: () => null,
                ip: ({ row }: { row: CollectionHostResult }) => resultLink(row, row.ip),
                processes: ({ row }: { row: CollectionHostResult }) => (
                  <span
                    class='collection-result-processes'
                    title={row.processes.map(item => `${item.process_name} (${item.pid})`).join('，')}
                  >
                    {row.processes.map(item => `${item.process_name} (${item.pid})`).join('，') || '--'}
                  </span>
                ),
                task: ({ row }: { row: CollectionHostResult }) => (
                  <Button
                    v-tippy={this.t('查看本次任务执行详情')}
                    theme='primary'
                    text
                    onClick={() => this.openExecution(row)}
                  >
                    {row.task.name}
                  </Button>
                ),
                operations: ({ row }: { row: CollectionHostResult }) => (
                  <div class='collection-row-actions'>
                    {resultLink(row, this.t('查看详情'))}
                    <span
                      v-tippy={this.t(
                        this.readonly
                          ? '暂无采集操作权限'
                          : h.busy.value
                            ? '正在提交采集任务'
                            : row.status === 'running'
                              ? '采集中，暂不能重新采集'
                              : '使用历史配置重新采集当前主机'
                      )}
                    >
                      <Button
                        disabled={this.readonly || h.busy.value || row.status === 'running'}
                        theme='primary'
                        text
                        onClick={() => h.requestRerun(row)}
                      >
                        {this.t('重新采集')}
                      </Button>
                    </span>
                  </div>
                ),
              }}
            </PrimaryTable>
          )}
          {h.error.value && (
            <div class='collection-history-error'>
              <Alert
                theme='danger'
                title={h.error.value}
              />
              <Button
                v-tippy={this.t('重新加载采集结果')}
                onClick={h.rows.value.length ? h.loadMore : h.refresh}
              >
                {this.t('重试')}
              </Button>
            </div>
          )}
          {!!h.rows.value.length && (
            <div class='collection-history-more'>
              {h.hasMore.value ? (
                <Button
                  v-tippy={this.t('加载下一批采集结果')}
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
        {this.selection?.scope === 'host' && (
          <CollectionResultDetail
            key={JSON.stringify(this.selection)}
            bizId={this.bizId}
            busy={h.busy.value}
            readonly={this.readonly}
            selection={this.selection}
            source={this.selectedRow}
            state={this.state}
            timezone={this.timezone}
            onChange={this.patch}
            onClose={() => this.$emit('change', { result: null })}
            onExecution={this.openExecution}
            onRerun={h.requestRerun}
            onShare={() => this.$emit('share')}
          />
        )}
        {c.selected.value && (
          <CollectionExecutionDetail
            controller={c}
            readonly={this.readonly}
            timezone={this.timezone}
            onResult={value => {
              c.close();
              this.$emit('result', value, false);
            }}
          />
        )}
        <CollectionExecutionAction
          controller={c}
          readonly={this.readonly}
        />
        <Dialog
          beforeClose={() => !h.busy.value}
          isShow={!!h.pending.value}
          quickClose={false}
          title={this.t('确认重新采集？')}
          transfer={false}
          onClosed={() => {
            if (!h.busy.value) h.pending.value = null;
          }}
        >
          {{
            default: () => (
              <>
                <p>{h.pending.value?.ip}</p>
                <p>{this.t('仅使用本次执行的历史配置重新采集当前主机，原有执行计划保持不变。')}</p>
                {h.actionError.value && (
                  <Alert
                    theme='danger'
                    title={h.actionError.value}
                  />
                )}
              </>
            ),
            footer: () => (
              <div class='collection-dialog-footer'>
                <Button
                  v-tippy={this.t('确认重新采集当前主机')}
                  disabled={this.readonly}
                  loading={h.busy.value}
                  theme='primary'
                  onClick={h.confirmRerun}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  v-tippy={this.t('取消本次操作')}
                  disabled={h.busy.value}
                  onClick={() => {
                    h.pending.value = null;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </div>
            ),
          }}
        </Dialog>
      </section>
    );
  },
});
