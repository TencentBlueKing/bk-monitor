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
import { type PropType, computed, defineComponent } from 'vue';

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Dialog, Input, Pagination, Switcher, Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useProfilingCollection } from '../../composables/use-profiling-collection';
import { formatCollectionTime, scheduleLabels } from '../../utils/collection';
import CollectionCrontab from './collection-crontab';
import CollectionHistory from './collection-history';
import CollectionOnboarding from './collection-onboarding';
import CollectionResults from './collection-results';
import CollectionSkeleton from './collection-skeleton';
import CollectionTaskDetail from './collection-task-detail';
import CollectionTaskForm from './collection-task-form';
import EmptyStatus from '@/components/empty-status/empty-status';
import { useAppStore } from '@/store/modules/app';

import type { SelectionRange } from '../../types';
import type { CollectionQueryState, CollectionTask, ScheduleType } from '../../types/collection';
import type { CollectionResultSelection } from '../../types/collection-history';

import './profiling-collection.scss';

const collectionTabs = [
  { name: 'results', label: 'Profiling 结果', icon: 'icon-Profiling' },
  { name: 'history', label: '采集任务历史', icon: 'icon-History' },
  { name: 'tasks', label: '任务管理', icon: 'icon-shezhi1' },
] as const;

/** 表格固定配置项（表头吸顶、横向滚动条吸底），滚动容器为任务列表面板 .collection-task-panel */
const taskTableAffixed = { container: '.collection-task-panel' };

export default defineComponent({
  name: 'ProfilingCollection',
  props: {
    state: { type: Object as PropType<CollectionQueryState>, required: true },
    timezone: { type: String, required: true },
    range: { type: Array as unknown as PropType<SelectionRange>, default: null },
    rangeError: { type: String, default: '' },
    revision: { type: Number, default: 0 },
    // 采集任务历史列表每次查询都重新解析时间，使相对时间取最新边界
    resolveRange: { type: Function as PropType<() => SelectionRange>, default: undefined },
  },
  emits: {
    change: (_value: Partial<CollectionQueryState>) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
    share: (_value?: CollectionResultSelection | null) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useAppStore();
    const bizId = computed(() => Number(store.bizId));
    const patch = (value: Partial<CollectionQueryState>) => emit('change', value);
    const collection = useProfilingCollection(
      bizId,
      computed(() => props.state),
      patch
    );
    return { t, bizId, patch, collection };
  },
  render() {
    const c = this.collection;
    const state = this.state;
    if (!c.meta.value) {
      return (
        <section class='profiling-collection'>
          <div
            class={['collection-meta-state', { 'is-loading': c.loading.value }]}
            aria-busy={c.loading.value}
          >
            {c.loading.value ? (
              <CollectionSkeleton variant='page' />
            ) : (
              c.error.value && (
                <div class='collection-meta-error'>
                  <Alert
                    theme='danger'
                    title={c.error.value}
                  />
                  <Button
                    loading={c.loading.value}
                    onClick={c.refresh}
                  >
                    {this.t('重试')}
                  </Button>
                </div>
              )
            )}
          </div>
        </section>
      );
    }
    const columns: TableProps['columns'] = [
      { colKey: 'name', title: this.t('定时任务名称'), minWidth: 240, ellipsis: true, cell: 'taskName' },
      {
        colKey: 'schedule_type',
        title: this.t('定期类型'),
        width: 160,
        filter: {
          type: 'multiple' as const,
          list: ['once_at', 'cron'].map(value => ({ value, label: this.t(scheduleLabels[value]) })),
        },
        cell: (_, { row }) => this.t(scheduleLabels[row.schedule.type]),
      },
      { colKey: 'schedule', title: this.t('执行时间'), minWidth: 220, sorter: true, cell: 'schedule' },
      {
        colKey: 'task_status',
        title: this.t('启 / 停'),
        width: 100,
        filter: {
          type: 'multiple' as const,
          list: [
            { value: 'enabled', label: this.t('启用') },
            { value: 'disabled', label: this.t('停用') },
          ],
        },
        cell: 'taskStatus',
      },
      { colKey: 'operations', title: this.t('操作'), width: 295, fixed: 'right', cell: 'operations' },
    ];
    const tableSlots = {
      // 空态类型必须经 this.state 走 props 代理读取：slot 在表格渲染时执行，
      // 闭包捕获的 state 是脱壳后的原生对象，读了不会被订阅
      empty: () => {
        const { keyword, scheduleTypes, statuses } = this.state;
        return (
          <div class='collection-task-empty'>
            <EmptyStatus
              textMap={{ empty: this.t('暂无定时任务'), 'search-empty': this.t('暂无匹配任务') }}
              type={keyword || scheduleTypes.length || statuses.length ? 'search-empty' : 'empty'}
              onOperation={() => this.patch({ keyword: '', scheduleTypes: [], statuses: [] })}
            />
          </div>
        );
      },
      taskName: ({ row }: { row: CollectionTask }) => (
        <Button
          theme='primary'
          text
          onClick={() => {
            c.detailId.value = row.task_id;
          }}
        >
          {row.name}
        </Button>
      ),
      schedule: ({ row }: { row: CollectionTask }) =>
        row.schedule.type === 'cron' ? (
          <CollectionCrontab
            timezone={row.schedule.timezone}
            value={row.schedule.cron_expression}
            readonly
          />
        ) : (
          <span v-tippy={row.schedule.timezone}>
            {formatCollectionTime(row.schedule.execute_at, row.schedule.timezone)}
          </span>
        ),
      taskStatus: ({ row }: { row: CollectionTask }) => (
        <Switcher
          disabled={c.readonly || !!c.busy.value}
          modelValue={row.task_status === 'enabled'}
          size='small'
          theme='primary'
          onChange={() => c.runAction(row, 'switch')}
        />
      ),
      operations: ({ row }: { row: CollectionTask }) => (
        <div class='collection-row-actions'>
          <span v-tippy={{ content: this.t('指定时间无执行记录'), onShow: () => row.schedule.type !== 'cron' }}>
            <Button
              disabled={row.schedule.type !== 'cron'}
              theme='primary'
              text
              onClick={() => c.openHistory(row)}
            >
              {this.t('执行记录')}
            </Button>
          </span>
          <Button
            disabled={c.readonly || !!c.busy.value || !c.meta.value}
            theme='primary'
            text
            onClick={() => c.openEditor(row)}
          >
            {this.t('编辑')}
          </Button>
          <Button
            disabled={c.readonly || !!c.busy.value}
            theme='primary'
            text
            onClick={() => {
              c.executing.value = row;
            }}
          >
            {this.t('立即执行')}
          </Button>
          <span v-tippy={{ content: this.t('请先停用任务后再删除'), onShow: () => row.task_status !== 'disabled' }}>
            <Button
              disabled={c.readonly || !!c.busy.value || row.task_status !== 'disabled'}
              theme='primary'
              text
              onClick={() => {
                c.deleting.value = row;
              }}
            >
              {this.t('删除')}
            </Button>
          </span>
        </div>
      ),
    };
    return (
      <section
        class={[
          'profiling-collection',
          {
            'has-tabs': c.meta.value.enabled,
            'is-history': c.meta.value.enabled && state.tab === 'history',
            'is-results': c.meta.value.enabled && state.tab === 'results',
          },
        ]}
      >
        {!c.meta.value.enabled ? (
          <CollectionOnboarding
            disabled={c.readonly || c.loading.value}
            loading={c.loading.value}
            onStart={() => c.openEditor()}
          />
        ) : (
          <>
            <Tab
              class='collection-tabs'
              active={state.tab}
              labelHeight={40}
              type='card-grid'
              onChange={tab => this.patch({ tab: tab as CollectionQueryState['tab'] })}
            >
              {collectionTabs.map(tab => (
                <Tab.TabPanel
                  key={tab.name}
                  v-slots={{
                    label: () => (
                      <span class='collection-tab-label'>
                        <i class={['icon-monitor', 'collection-tab-icon', tab.icon, `is-${tab.name}`]} />
                        {this.t(tab.label)}
                      </span>
                    ),
                  }}
                  name={tab.name}
                />
              ))}
            </Tab>
            {state.tab === 'tasks' ? (
              <div class='collection-tab-panel collection-task-panel'>
                <Alert
                  class='collection-task-guide'
                  v-slots={{
                    title: () => (
                      <i18n-t keypath='新建任务：如果选择 <{0}> 提交后将马上进入<采集任务历史>；如果选择 <{1} / {2}> 将进入下方的 <定时任务列表>。'>
                        <b>{this.t('立即执行')}</b>
                        <b>{this.t('指定时间')}</b>
                        <b>{this.t('周期执行')}</b>
                      </i18n-t>
                    ),
                  }}
                  theme='info'
                />
                <div class='collection-task-toolbar'>
                  <Button
                    class='collection-task-toolbar-btn'
                    disabled={c.readonly || !c.meta.value}
                    theme='primary'
                    onClick={() => c.openEditor()}
                  >
                    <span class='collection-task-toolbar-btn-inner'>
                      <i class='icon-monitor icon-a-1jiahao' />
                      {this.t('新建任务')}
                    </span>
                  </Button>
                  <Input
                    class='collection-task-search'
                    modelValue={state.keyword}
                    placeholder={this.t('搜索任务名称')}
                    type='search'
                    clearable
                    onClear={() => this.patch({ keyword: '' })}
                    onInput={keyword => this.patch({ keyword })}
                  />
                  <Button
                    loading={c.loading.value}
                    onClick={c.refresh}
                  >
                    {this.t('刷新')}
                  </Button>
                </div>
                {c.error.value && (
                  <Alert
                    class='collection-inline-alert'
                    theme='danger'
                    title={c.error.value}
                  />
                )}
                <div class={['collection-task-table', { 'is-empty': !c.loading.value && !c.rows.value.length }]}>
                  {c.loading.value ? (
                    <CollectionSkeleton />
                  ) : (
                    <PrimaryTable
                      v-slots={tableSlots}
                      columns={columns}
                      data={c.rows.value}
                      filterValue={{ schedule_type: state.scheduleTypes, task_status: state.statuses }}
                      headerAffixedTop={taskTableAffixed}
                      needCustomScroll={false}
                      rowKey='task_id'
                      size='small'
                      sort={state.sort || undefined}
                      onFilterChange={value =>
                        this.patch({
                          scheduleTypes: (value.schedule_type || []) as ScheduleType[],
                          statuses: (value.task_status || []) as string[],
                        })
                      }
                      onSortChange={sort => this.patch({ sort: (Array.isArray(sort) ? sort[0] : sort) || null })}
                    />
                  )}
                </div>
                {!c.loading.value && !!c.rows.value.length && (
                  <Pagination
                    class='collection-task-pagination'
                    align='right'
                    count={c.filtered.value.length}
                    layout={['total', 'limit', 'list']}
                    limit={c.pageSize.value}
                    limitList={[10, 20, 50, 100]}
                    location='right'
                    modelValue={c.page.value}
                    small
                    onChange={value => {
                      c.page.value = value;
                    }}
                    onLimitChange={value => {
                      c.pageSize.value = value;
                    }}
                  />
                )}
              </div>
            ) : state.tab === 'history' ? (
              <CollectionHistory
                key={this.bizId}
                bizId={this.bizId}
                filters={state.history}
                range={this.range}
                rangeError={this.rangeError}
                readonly={c.readonly}
                resolveRange={this.resolveRange}
                revision={this.revision}
                statusFilters={c.meta.value.execution_status_filters}
                timezone={this.timezone}
                onBusy={value => this.$emit('busy', value)}
                onChange={history => this.patch({ history, historyTaskName: history.task_name, historyTaskId: null })}
                onCreated={() => this.$emit('created')}
                onResult={(value, newPage) => this.$emit('result', value, newPage)}
                onShare={value => this.$emit('share', value)}
              />
            ) : (
              <CollectionResults
                key={this.bizId}
                bizId={this.bizId}
                range={this.range}
                rangeError={this.rangeError}
                readonly={c.readonly}
                revision={this.revision}
                selection={state.result}
                state={state.results}
                timezone={this.timezone}
                onBusy={value => this.$emit('busy', value)}
                onChange={this.patch}
                onCreate={() => {
                  this.patch({ tab: 'tasks' });
                  c.openEditor();
                }}
                onCreated={() => this.$emit('created')}
                onResult={(value, newPage) => this.$emit('result', value, newPage)}
                onShare={value => this.$emit('share', value)}
              />
            )}
          </>
        )}
        {c.editorOpen.value && c.meta.value && (
          <CollectionTaskForm
            key={`${this.bizId}:${c.editing.value?.task_id || 'new'}`}
            bizId={this.bizId}
            meta={c.meta.value}
            task={c.editing.value}
            timezone={this.timezone}
            onClose={() => {
              c.editorOpen.value = false;
            }}
            onSaved={c.saved}
          />
        )}
        {c.detail.value && (
          <CollectionTaskDetail
            busy={!!c.busy.value}
            hostError={c.detailHostError.value}
            hostLoading={c.detailHostLoading.value}
            hosts={c.detailHosts.value}
            readonly={c.readonly}
            task={c.detail.value}
            onClose={() => {
              c.detailId.value = undefined;
            }}
            onDelete={() => {
              c.deleting.value = c.detail.value;
            }}
            onEdit={() => c.openEditor(c.detail.value)}
            onHistory={() => c.openHistory(c.detail.value)}
            onRetryHosts={c.loadDetailHosts}
          />
        )}
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.deleting.value}
          quickClose={false}
          title={this.t('确认删除任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.deleting.value = undefined;
          }}
        >
          {{
            default: () => <p>{c.deleting.value?.name}</p>,
            footer: () => (
              <div class='collection-dialog-footer'>
                <Button
                  v-tippy={this.t('确认删除当前任务')}
                  loading={!!c.busy.value}
                  theme='danger'
                  onClick={() => c.runAction(c.deleting.value, 'delete')}
                >
                  {this.t('删除')}
                </Button>
                <Button
                  v-tippy={this.t('取消本次操作')}
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.deleting.value = undefined;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </div>
            ),
          }}
        </Dialog>
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.executing.value}
          quickClose={false}
          title={this.t('确认立即执行任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.executing.value = undefined;
          }}
        >
          {{
            default: () => (
              <>
                <p>{c.executing.value?.name}</p>
                <p>{this.t('将使用当前配置发起一次采集，原有执行计划保持不变。')}</p>
                <p>{this.t('立即执行仅支持 Linux 主机，提交后可在采集任务历史查看进度')}</p>
              </>
            ),
            footer: () => (
              <div class='collection-dialog-footer'>
                <Button
                  v-tippy={this.t('使用当前配置立即执行一次采集')}
                  loading={!!c.busy.value}
                  theme='primary'
                  onClick={() => c.runAction(c.executing.value, 'execute')}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  v-tippy={this.t('取消本次操作')}
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.executing.value = undefined;
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
