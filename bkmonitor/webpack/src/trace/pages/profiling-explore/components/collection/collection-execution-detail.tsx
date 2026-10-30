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

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Dialog, Input, Loading, Message, Sideslider, Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { saveCollectionTask } from '../../services/collection';
import { getCollectionExecution, renameCollectionExecution } from '../../services/collection-history';
import { collectionTypeLabels, formatCollectionTime, processSelectorText } from '../../utils/collection';
import {
  canRetryExecution,
  canViewExecution,
  executionConfiguration,
  executionHostMessage,
  executionSelection,
  formatExecutionDuration,
  hostColumnMinWidths,
} from '../../utils/collection-history';
import {
  buildHostCollectionPayload,
  createCollectionResultsState,
  executionResultRows,
  resultExecutionKey,
} from '../../utils/collection-results';
import CollectionConfiguration from './collection-configuration';
import CollectionExecutionSkeleton from './collection-execution-skeleton';
import CollectionExecutionStatus from './collection-execution-status';
import CollectionResultDetail from './collection-result-detail';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { UseCollectionExecutionReturn } from '../../composables/use-collection-execution';
import type {
  CollectionExecutionColumn,
  CollectionExecutionHost,
  CollectionResultSelection,
} from '../../types/collection-history';
import type { CollectionHostResult, CollectionResultsState } from '../../types/collection-results';

import './collection-execution-detail.scss';

// 详情加载完成前先用接口文档的默认列表撑起骨架
const fallbackHostColumns: CollectionExecutionColumn[] = [
  { field: 'ip', name: '目标 IP', type: 'text' },
  { field: 'processes', name: '采集进程', type: 'process_list' },
  { field: 'status', name: '状态', type: 'status' },
  { field: 'message', name: '执行信息', type: 'text' },
  { field: 'started_at', name: '开始时间', type: 'datetime' },
  { field: 'finished_at', name: '结束时间', type: 'datetime' },
  { field: 'duration_ms', name: '耗时', type: 'duration' },
];

export default defineComponent({
  name: 'CollectionExecutionDetail',
  props: {
    bizId: { type: Number, required: true },
    controller: { type: Object as PropType<UseCollectionExecutionReturn>, required: true },
    readonly: { type: Boolean, default: false },
    timezone: { type: String, required: true },
  },
  emits: {
    result: (_value: CollectionResultSelection) => true,
    share: (_value?: CollectionResultSelection | null) => true,
    created: () => true,
    renamed: () => true,
    busy: (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const diagnosis = shallowRef<CollectionExecutionHost | null>(null);
    // 采集结果详情直接叠加在执行详情之上，不再跳转结果页
    const resultSelection = shallowRef<CollectionResultSelection | null>(null);
    const resultState = shallowRef<CollectionResultsState>(createCollectionResultsState());
    const rerunHost = shallowRef<CollectionHostResult | null>(null);
    const rerunBusy = shallowRef(false);
    const rerunError = shallowRef('');
    let rerunController: AbortController;
    // 执行任务名就地编辑：只改这一次执行，计划任务名不受影响
    const renameInput = shallowRef<null | { $el?: HTMLElement }>(null);
    const renaming = shallowRef(false);
    const renameName = shallowRef('');
    const renameBusy = shallowRef(false);
    let renameController: AbortController;
    const resultSource = computed(() => {
      const selection = resultSelection.value;
      const detail = props.controller.detail.value;
      if (!selection?.bk_host_id || !detail) return undefined;
      return executionResultRows(detail).find(host => host.bk_host_id === selection.bk_host_id);
    });
    watch(
      () => props.controller.selected.value,
      () => {
        diagnosis.value = null;
        resultSelection.value = null;
        rerunHost.value = null;
        rerunError.value = '';
        renaming.value = false;
        renameName.value = '';
      }
    );
    // 重新采集与改名的提交状态上报，父级据此暂停自动刷新；同步上报避免关闭详情卸载组件后丢失复位
    watch([rerunBusy, renameBusy], ([rerun, rename]) => emit('busy', rerun || rename), {
      immediate: true,
      flush: 'sync',
    });
    onScopeDispose(() => {
      rerunController?.abort();
      renameController?.abort();
      // 提交中途被卸载时请求随之中止，finally 不再复位，这里兜底
      emit('busy', false);
    });
    function openResult(host: CollectionExecutionHost) {
      const detail = props.controller.detail.value;
      if (!detail) return;
      resultState.value = createCollectionResultsState();
      rerunError.value = '';
      resultSelection.value = executionSelection(detail, host);
    }
    function closeResult() {
      if (rerunBusy.value) return;
      resultSelection.value = null;
      rerunHost.value = null;
      rerunError.value = '';
    }
    function patchResult(value: Partial<CollectionResultsState>) {
      resultState.value = { ...resultState.value, ...value };
    }
    function requestRerun(row: CollectionHostResult) {
      if (props.readonly || rerunBusy.value || row.status === 'running') return;
      rerunHost.value = row;
      rerunError.value = '';
    }
    async function confirmRerun() {
      const row = rerunHost.value;
      if (props.readonly || rerunBusy.value || !row) return;
      rerunController?.abort();
      const current = new AbortController();
      rerunController = current;
      rerunBusy.value = true;
      rerunError.value = '';
      try {
        // 提交前重新拉取执行详情，避免使用页面上可能已过期的快照
        const detail = await getCollectionExecution(props.bizId, resultExecutionKey(row), current.signal);
        if (current.signal.aborted || props.readonly) return;
        await saveCollectionTask(
          buildHostCollectionPayload(detail, row.bk_host_id, props.bizId),
          undefined,
          current.signal
        );
        if (current.signal.aborted) return;
        // 重新采集已提交：先复位 busy（同步上报），再关采集结果侧弹与任务执行详情
        rerunHost.value = null;
        resultSelection.value = null;
        rerunError.value = '';
        rerunBusy.value = false;
        Message({ theme: 'success', message: t('采集任务已创建') });
        props.controller.close();
        emit('created');
      } catch (e) {
        if (!current.signal.aborted) rerunError.value = t((e as Error)?.message || '重新采集失败，请重试');
      } finally {
        if (!current.signal.aborted) rerunBusy.value = false;
      }
    }
    function startRename() {
      const execution = props.controller.detail.value || props.controller.selected.value;
      if (props.readonly || renameBusy.value || !execution) return;
      renameName.value = execution.task_name;
      renaming.value = true;
      nextTick(() => renameInput.value?.$el?.querySelector<HTMLInputElement>('input')?.focus());
    }
    async function submitRename() {
      if (renameBusy.value) return;
      const execution = props.controller.detail.value || props.controller.selected.value;
      const name = renameName.value.trim();
      // 名称未变或为空时直接退出编辑，不提交空名称
      if (!execution || !name || name === execution.task_name) {
        renaming.value = false;
        return;
      }
      renameController?.abort();
      const current = new AbortController();
      renameController = current;
      renameBusy.value = true;
      try {
        await renameCollectionExecution(props.bizId, execution, name, current.signal);
        if (current.signal.aborted) return;
        props.controller.renameExecution(name);
        renaming.value = false;
        Message({ theme: 'success', message: t('任务名修改成功') });
        emit('renamed');
      } catch (e) {
        if (!current.signal.aborted)
          Message({ theme: 'error', message: (e as Error)?.message || t('任务名修改失败，请重试') });
      } finally {
        if (!current.signal.aborted) renameBusy.value = false;
      }
    }
    return {
      t,
      diagnosis,
      resultSelection,
      resultState,
      resultSource,
      rerunHost,
      rerunBusy,
      rerunError,
      openResult,
      closeResult,
      patchResult,
      requestRerun,
      confirmRerun,
      renameInput,
      renaming,
      renameName,
      renameBusy,
      startRename,
      submitRename,
    };
  },
  render() {
    const c = this.controller;
    const detail = c.detail.value;
    // 详情未返回前先用列表行撑起头部
    const execution = detail || c.selected.value;
    // 目标进程只在配置快照就绪后展示，旧数据可能没有配置
    const processSelector = detail?.config?.process_selector;
    const processTag = processSelector ? processSelectorText(processSelector, this.t) : '';
    const resultSelection = this.resultSelection;
    // 优先使用后端下发的列定义，旧接口无该字段时回退默认列并翻译列名
    const hostColumns = detail?.host_columns?.length
      ? detail.host_columns
      : fallbackHostColumns.map(column => ({ ...column, name: this.t(column.name) }));
    const renderHostProcesses = (row: CollectionExecutionHost) =>
      row.processes.length ? (
        <div class='collection-execution-processes'>
          {row.processes.map(process => (
            <span
              key={`${process.pid}:${process.process_name}`}
              title={`${process.process_name} (${process.pid})`}
            >
              {process.process_name} ({process.pid})
            </span>
          ))}
        </div>
      ) : (
        '--'
      );
    // 按后端声明的列类型渲染单元格，未知类型统一按文本处理
    const renderHostCell = (column: CollectionExecutionColumn, row: CollectionExecutionHost) => {
      const value = (row as unknown as Record<string, unknown>)[column.field];
      if (column.type === 'process_list') return renderHostProcesses(row);
      // 执行信息优先展示失败原因类型对应的文案，无 error_type 时沿用后端下发的 message
      if (column.field === 'message') {
        const message = executionHostMessage(row);
        return message ? this.t(message) : '--';
      }
      if (column.type === 'status')
        return (
          <CollectionExecutionStatus
            class={{ 'has-failure-message': !!row.message && ['failed', 'timeout'].includes(row.status) }}
            message={row.message}
            status={String(value ?? '')}
          />
        );
      if (column.type === 'datetime') return value ? formatCollectionTime(value as number, this.timezone) : '--';
      if (column.type === 'duration') return formatExecutionDuration(typeof value === 'number' ? value : null);
      return value ? String(value) : '--';
    };
    const columns: TableProps['columns'] = [
      ...hostColumns.map<NonNullable<TableProps['columns']>[number]>(column => ({
        colKey: column.field,
        title: column.name,
        minWidth: hostColumnMinWidths[column.type],
        cell: (_, { row }) => renderHostCell(column, row as CollectionExecutionHost),
        ...(column.type === 'status' ? { sorter: true } : {}),
        ...(column.type === 'text' ? { ellipsis: true } : {}),
      })),
      { colKey: 'operations', title: this.t('操作'), width: 120, fixed: 'right', cell: 'operations' },
    ];
    return (
      <Sideslider
        width='min(960px, 100vw)'
        class='collection-execution-detail'
        beforeClose={() => {
          // 逐层关闭：叠加采集结果详情时先关结果面板
          if (this.resultSelection) {
            this.closeResult();
            return false;
          }
          // 取消或改名的提交未完成时禁止关闭，避免请求被中止后列表仍显示旧名称
          return !c.busy.value && !this.renameBusy;
        }}
        isShow={true}
        transfer={false}
        onClosed={c.close}
      >
        {{
          header: () => (
            <div class='collection-execution-detail-header'>
              <span>{this.t('任务执行详情')}</span>
              <span
                class='collection-execution-title-divider'
                aria-hidden='true'
              />
              {/* 任务名就地编辑：回车或失焦提交，只改这一次执行 */}
              {this.renaming ? (
                <Loading
                  class='collection-execution-rename'
                  loading={this.renameBusy}
                  size='small'
                >
                  {/* change 是原生 change 事件，回车早于它触发，改名必须用 input 实时同步 */}
                  <Input
                    ref='renameInput'
                    class='collection-execution-rename-input'
                    behavior='simplicity'
                    maxlength={128}
                    modelValue={this.renameName}
                    onBlur={this.submitRename}
                    onEnter={this.submitRename}
                    onInput={value => {
                      this.renameName = String(value ?? '');
                    }}
                  />
                </Loading>
              ) : (
                <>
                  <span
                    class='collection-execution-detail-name'
                    title={execution.task_name}
                  >
                    {execution.task_name}
                  </span>
                  {!this.readonly && (
                    <i
                      class='icon-monitor icon-bianji collection-execution-rename-icon'
                      v-tippy={this.t('修改执行任务名')}
                      onClick={this.startRename}
                    />
                  )}
                </>
              )}
              <CollectionExecutionStatus
                status={execution.execution_status}
                tag
              />
              <div class='collection-execution-detail-actions'>
                <Button
                  class='collection-execution-result-action'
                  v-tippy={this.t('查看本次执行各主机的采集结果')}
                  disabled={!detail || c.loading.value || !!c.error.value || !canViewExecution(detail)}
                  text
                  onClick={() => this.$emit('result', executionSelection(detail))}
                >
                  <span class='collection-execution-result-label'>
                    <span
                      class='collection-execution-profiling-icon'
                      aria-hidden='true'
                    >
                      <i />
                    </span>
                    {this.t('查看全部结果')}
                  </span>
                </Button>
              </div>
            </div>
          ),
          default: () => (
            <>
              <Tab
                class='collection-execution-tabs'
                active={c.tab.value}
                labelHeight={40}
                type='card-grid'
                onChange={value => {
                  c.tab.value = String(value);
                }}
              >
                <Tab.TabPanel
                  v-slots={{
                    label: () => (
                      <span class='collection-execution-tab-label'>
                        <i
                          class='collection-execution-icon is-results'
                          aria-hidden='true'
                        />
                        {this.t('执行结果')}
                      </span>
                    ),
                  }}
                  name='results'
                />
                <Tab.TabPanel
                  v-slots={{
                    label: () => (
                      <span class='collection-execution-tab-label'>
                        <i
                          class='collection-execution-icon is-snapshot'
                          aria-hidden='true'
                        />
                        {this.t('配置快照')}
                      </span>
                    ),
                  }}
                  name='snapshot'
                />
              </Tab>
              {c.error.value ? (
                <div class='collection-execution-content'>
                  <Alert
                    theme='danger'
                    title={c.error.value}
                  />
                  <Button
                    v-tippy={this.t('重新加载任务执行详情')}
                    onClick={c.refresh}
                  >
                    {this.t('重试')}
                  </Button>
                </div>
              ) : c.loading.value ? (
                <CollectionExecutionSkeleton
                  columns={columns}
                  snapshot={c.tab.value === 'snapshot'}
                />
              ) : (
                detail &&
                (c.tab.value === 'snapshot' ? (
                  <CollectionConfiguration
                    hosts={detail.hosts.map(host => ({ host_id: host.bk_host_id, ip: host.ip }))}
                    task={executionConfiguration(detail)}
                    snapshot
                  />
                ) : (
                  <div class='collection-execution-content'>
                    <dl class='collection-execution-summary'>
                      <div>
                        <dt>{this.t('执行时间')}：</dt>
                        <dd>
                          {formatCollectionTime(detail.started_at, this.timezone)} ～{' '}
                          {formatCollectionTime(detail.finished_at, this.timezone)}{' '}
                          <span class='collection-execution-duration'>
                            <i
                              class='collection-execution-icon is-duration'
                              aria-hidden='true'
                            />
                            {formatExecutionDuration(detail.duration_ms)}
                          </span>
                        </dd>
                      </div>
                      <div>
                        <dt>{this.t('采集配置')}：</dt>
                        <dd>
                          {collectionTypeLabels[detail.collection_type]}
                          {detail.config.collector_config.frequency_hz !== undefined &&
                            ` · ${detail.config.collector_config.frequency_hz} Hz`}
                          {detail.config.collector_config.stack_unwind &&
                            ` · ${detail.config.collector_config.stack_unwind}`}
                        </dd>
                      </div>
                      <div>
                        <dt>{this.t('目标进程')}：</dt>
                        <dd>{processTag || '--'}</dd>
                      </div>
                    </dl>
                    <div class='collection-execution-toolbar'>
                      <Button
                        v-tippy={this.t(
                          this.readonly
                            ? '暂无采集操作权限'
                            : detail.execution_status === 'running'
                              ? '采集中，暂不能重试失败项'
                              : canRetryExecution(detail)
                                ? '仅重新采集失败和超时主机'
                                : '没有可重试的失败主机'
                        )}
                        disabled={this.readonly || c.busy.value || !canRetryExecution(detail)}
                        theme='primary'
                        onClick={() => c.requestAction('retry', detail)}
                      >
                        {this.t('仅重试失败项')}
                      </Button>
                      {/* 状态计数条：点击按主机状态过滤下方表格 */}
                      <div class='collection-execution-counts'>
                        <button
                          class={['collection-execution-count-all', { 'is-active': !c.hostStatus.value }]}
                          type='button'
                          onClick={() => {
                            c.hostStatus.value = '';
                          }}
                        >
                          {this.t('全部')}
                        </button>
                        {Object.entries(detail.status_summary)
                          .filter(([, count]) => count > 0)
                          .map(([status, count]) => (
                            <button
                              key={status}
                              class={{ 'is-active': c.hostStatus.value === status }}
                              type='button'
                              onClick={() => {
                                c.hostStatus.value = c.hostStatus.value === status ? '' : status;
                              }}
                            >
                              <CollectionExecutionStatus status={status} /> ({count})
                            </button>
                          ))}
                      </div>
                      <Input
                        class='collection-execution-search'
                        aria-label={this.t('搜索 IP、进程名或 PID')}
                        modelValue={c.keyword.value}
                        placeholder={this.t('搜索')}
                        clearable
                        onChange={value => {
                          c.keyword.value = String(value);
                        }}
                      >
                        {{
                          suffix: () => (
                            <i
                              style={{ color: '#979ba5', margin: 'auto 6px' }}
                              class='collection-execution-icon is-search'
                              aria-hidden='true'
                            />
                          ),
                        }}
                      </Input>
                    </div>
                    <PrimaryTable
                      columns={columns}
                      data={c.hosts.value}
                      needCustomScroll={false}
                      rowKey='bk_host_id'
                      size='small'
                      sort={c.hostSort.value ? { sortBy: 'status', descending: c.hostSort.value === 'desc' } : null}
                      onSortChange={value => {
                        const sort = Array.isArray(value) ? value[0] : value;
                        c.hostSort.value = sort?.sortBy ? (sort.descending ? 'desc' : 'asc') : '';
                      }}
                    >
                      {{
                        empty: () => (
                          <EmptyStatus
                            type={c.keyword.value || c.hostStatus.value ? 'search-empty' : 'empty'}
                            onOperation={() => {
                              c.keyword.value = '';
                              c.hostStatus.value = '';
                            }}
                          />
                        ),
                        operations: ({ row }: { row: CollectionExecutionHost }) =>
                          ['failed', 'timeout'].includes(row.status) ? (
                            <Button
                              v-tippy={this.t('查看当前主机的采集失败信息')}
                              theme='primary'
                              text
                              onClick={() => {
                                this.diagnosis = row;
                              }}
                            >
                              {this.t('诊断')}
                            </Button>
                          ) : (
                            <Button
                              v-tippy={this.t(
                                row.status === 'succeed' && row.started_at != null && row.finished_at != null
                                  ? '查看当前主机的采集结果'
                                  : '本次采集暂无可查看的结果'
                              )}
                              disabled={row.status !== 'succeed' || row.started_at == null || row.finished_at == null}
                              theme='primary'
                              text
                              onClick={() => this.openResult(row)}
                            >
                              {this.t('查看结果')}
                            </Button>
                          ),
                      }}
                    </PrimaryTable>
                  </div>
                ))
              )}
              <Dialog
                width={640}
                isShow={!!this.diagnosis}
                title={this.t('失败信息')}
                transfer={false}
                onClosed={() => {
                  this.diagnosis = null;
                }}
              >
                {{
                  default: () => (
                    <>
                      <p>{this.diagnosis?.ip}</p>
                      <pre class='collection-execution-message'>{this.diagnosis?.message || '--'}</pre>
                    </>
                  ),
                  footer: () => (
                    <Button
                      v-tippy={this.t('关闭失败信息')}
                      onClick={() => {
                        this.diagnosis = null;
                      }}
                    >
                      {this.t('关闭')}
                    </Button>
                  ),
                }}
              </Dialog>
              {resultSelection && (
                <CollectionResultDetail
                  key={JSON.stringify(resultSelection)}
                  bizId={this.bizId}
                  busy={c.busy.value || this.rerunBusy}
                  readonly={this.readonly}
                  selection={resultSelection}
                  source={this.resultSource}
                  state={this.resultState}
                  timezone={this.timezone}
                  transfer
                  onChange={this.patchResult}
                  onClose={this.closeResult}
                  onExecution={this.closeResult}
                  onRerun={this.requestRerun}
                  onShare={() => this.$emit('share', resultSelection)}
                />
              )}
              <Dialog
                beforeClose={() => !this.rerunBusy}
                isShow={!!this.rerunHost}
                quickClose={false}
                title={this.t('确认重新采集？')}
                onClosed={() => {
                  if (!this.rerunBusy) this.rerunHost = null;
                }}
              >
                {{
                  default: () => (
                    <>
                      <p>{this.rerunHost?.ip}</p>
                      <p>{this.t('仅使用本次执行的历史配置重新采集当前主机，原有执行计划保持不变。')}</p>
                      {this.rerunError && (
                        <Alert
                          theme='danger'
                          title={this.rerunError}
                        />
                      )}
                    </>
                  ),
                  footer: () => (
                    <div class='collection-dialog-footer'>
                      <Button
                        v-tippy={this.t('确认重新采集当前主机')}
                        disabled={this.readonly}
                        loading={this.rerunBusy}
                        theme='primary'
                        onClick={this.confirmRerun}
                      >
                        {this.t('确定')}
                      </Button>
                      <Button
                        v-tippy={this.t('取消本次操作')}
                        disabled={this.rerunBusy}
                        onClick={() => {
                          this.rerunHost = null;
                        }}
                      >
                        {this.t('取消')}
                      </Button>
                    </div>
                  ),
                }}
              </Dialog>
            </>
          ),
        }}
      </Sideslider>
    );
  },
});
